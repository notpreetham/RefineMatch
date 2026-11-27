r"""Contrastive scoring: *is this structure explained by an attack template and NOT by a benign one?*

For every embedding m of an attack template A in the window:

    attack_sim(m)  = coverage(m) * temporal(m) * relaxation(m)
    benign_sim(m)  = max_{B in counterparts(A)} max_{m_B} score(m_B) * explain(m_B, m)
    novelty(m)     = 1 - (how common the matched hosts' TCR colours are in benign history)
    contrast(m)    = attack_sim(m) * (1 - lambda * benign_sim(m)) * (alpha + (1 - alpha) * novelty(m))

``explain(m_B, m)`` is the weighted fraction of m's evidence events (u -> v, tau) that the benign
embedding m_B *would also accept*: some edge spec of B starts at u under m_B, admits type tau, and
its destination constraint accepts v. The window score for A is the max contrast over embeddings,
so a sanctioned look-alike elsewhere in the window can never mask a real attack.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.core.config import (DEFAULT_BENIGN_LAMBDA, DEFAULT_MULTIPLICITY, DEFAULT_NOVELTY_ALPHA, DEFAULT_TCR_DEPTH,
                             RISK_LEVELS)
from src.core.models import EvidenceEdge, ScoreResult, TemporalGraph, make_event as _ev
from src.graph.builder import GraphIndex
from src.matching.matcher import Embedding, PatternMatcher
from src.matching.pattern import Pattern
from src.refinement.kernel import color_histogram, containment
from src.refinement.temporal import temporal_color_refinement


def risk_level(score: float) -> str:
    for thr, name in RISK_LEVELS:
        if score >= thr:
            return name
    return "low"


class BenignProfile:
    """Document frequency of low-level TCR colours across (mostly) benign history windows.

    Unsupervised: it only needs past traffic, never attack labels."""

    def __init__(self, levels=(1,), depth: int = DEFAULT_TCR_DEPTH, multiplicity: str = "set"):
        # Level-1 colours under set semantics ("which kinds of peers, via which event types, did this
        # host talk to") recur across benign windows (~1-6% novel) while attack hosts are mostly novel;
        # deeper/finer colours are unique per window and carry no frequency signal.
        self.levels = levels
        self.depth = depth
        self.mode = multiplicity
        self.df: Counter = Counter()
        self.n_windows = 0

    def window_colors(self, tg: TemporalGraph, roles: Dict[str, str]) -> List[Dict[str, int]]:
        _, lv = temporal_color_refinement(tg.events, roles, depth=max(self.levels), multiplicity=self.mode,
                                          return_levels=True)
        return lv

    def fit(self, graphs: List[Tuple[TemporalGraph, Dict[str, str]]]):
        for tg, roles in graphs:
            self.add(self.window_colors(tg, roles))
        return self

    def add(self, levels: List[Dict[str, int]]):
        seen = {(k, c) for k in self.levels for c in levels[k].values()}
        self.df.update(seen)
        self.n_windows += 1

    def novelty(self, levels: List[Dict[str, int]], nodes) -> float:
        if self.n_windows == 0:
            return 0.5
        vals = []
        for v in nodes:
            per = [1.0 - self.df.get((k, levels[k][v]), 0) / self.n_windows for k in self.levels if v in levels[k]]
            if per:
                vals.append(sum(per) / len(per))
        return max(vals) if vals else 0.5


def structural_score(pattern: Pattern, emb: Embedding) -> float:
    """Role-agnostic TCR kernel between the evidence subgraph and the pattern's prototype instance.

    Equals 1 iff the chosen evidence is temporally isomorphic to the pattern skeleton."""
    proto = []
    for i, e in enumerate(pattern.edges):
        if i in emb.kept_edges or not emb.kept_edges:
            proto.append(_ev(float(e.order), "P_" + e.src, "P_" + e.dst, sorted(e.types)[0]))
    obs = []
    rank = {t: r for r, t in enumerate(sorted({ev.timestamp for ev in emb.evidence}))}
    for ev in emb.evidence:
        types = next((sorted(e.types) for e in pattern.edges if e.src == ev.pattern_src and e.dst == ev.pattern_dst
                      and ev.event_type in e.types), [ev.event_type])
        obs.append(_ev(float(rank[ev.timestamp]), ev.source, ev.destination, types[0]))
    if not obs or not proto:
        return 0.0
    _, lp = temporal_color_refinement(sorted(proto, key=lambda x: x.ts), {}, depth=2, multiplicity="set", return_levels=True)
    _, lo = temporal_color_refinement(sorted(obs, key=lambda x: x.ts), {}, depth=2, multiplicity="set", return_levels=True)
    hp, ho = color_histogram(lp), color_histogram(lo)
    return min(containment(hp, ho), containment(ho, hp))


@dataclass
class Detection:
    pattern: Pattern
    embedding: Embedding
    score: ScoreResult
    benign_embedding: Optional[Embedding] = None
    match_confidence: float = 1.0
    exhaustive: bool = True
    candidates_considered: int = 0
    trace: List[dict] = field(default_factory=list)
    related_nodes: set = field(default_factory=set)   # nodes of all embeddings scoring >= half the best

    @property
    def nodes(self):
        return sorted(set(self.embedding.mapping.values()))

    @property
    def time_range(self):
        ts = [e.timestamp for e in self.embedding.evidence]
        return (min(ts), max(ts)) if ts else (None, None)


class ContrastiveScorer:
    def __init__(self, library: Dict[str, Pattern], profile: Optional[BenignProfile] = None,
                 lam: float = DEFAULT_BENIGN_LAMBDA, alpha: float = DEFAULT_NOVELTY_ALPHA, use_benign: bool = True):
        self.lib = library
        self.profile = profile
        self.lam = lam
        self.alpha = alpha
        self.use_benign = use_benign

    def explain_fraction(self, matcher: PatternMatcher, attack: Pattern, emb: Embedding,
                         benign: Pattern, bemb: Embedding) -> float:
        tot, cov = 0.0, 0.0
        wmap = {(e.src, e.dst): e.weight for e in attack.edges}
        for ev in emb.evidence:
            w = wmap.get((ev.pattern_src, ev.pattern_dst), 1.0)
            tot += w
            for be in benign.edges:
                if be.src not in bemb.mapping or bemb.mapping[be.src] != ev.source or ev.event_type not in be.types:
                    continue
                if be.dst in bemb.mapping and bemb.mapping[be.dst] == ev.destination:
                    cov += w
                    break
                role = matcher.ix.roles.get(ev.destination, "workstation")
                spec = benign.nodes[be.dst]
                if spec.accepts(role, lambda et: matcher.ix.out_distinct(ev.destination, et)) and \
                        matcher.qualifying_events(ev.source, ev.destination, be) is not None:
                    cov += w
                    break
        return cov / tot if tot else 0.0

    def benign_similarity(self, matcher: PatternMatcher, attack: Pattern, emb: Embedding, cache: dict):
        best, best_emb, best_name = 0.0, None, None
        nodes = set(emb.mapping.values())
        for bname in attack.benign_counterparts:
            b = self.lib.get(bname)
            if b is None:
                continue
            for p in b.nodes:
                for u in nodes:
                    key = (bname, p, u)
                    if key not in cache:
                        cache[key] = matcher.match(b, restrict={p: {u}}, with_trace=False).embeddings
                    for be in cache[key]:
                        s = be.score * self.explain_fraction(matcher, attack, emb, b, be)
                        if s > best:
                            best, best_emb, best_name = s, be, bname
        return best, best_emb, best_name

    def score_pattern(self, matcher: PatternMatcher, attack: Pattern, levels=None, cache=None) -> Optional[Detection]:
        cache = {} if cache is None else cache
        res = matcher.match(attack)
        if not res.embeddings:
            return None
        best: Optional[Detection] = None
        scored = []
        for emb in res.embeddings:
            a_sim = emb.score
            if a_sim <= 0:
                continue
            if self.use_benign:
                b_sim, b_emb, b_name = self.benign_similarity(matcher, attack, emb, cache)
            else:
                b_sim, b_emb, b_name = 0.0, None, None
            internal = [v for v in emb.mapping.values() if matcher.ix.roles.get(v) not in ("external", "saas")]
            nov = self.profile.novelty(levels, internal) if (self.profile and levels is not None) else 0.5
            mod = self.alpha + (1 - self.alpha) * nov
            contrast = a_sim * max(0.0, 1 - self.lam * b_sim) * mod
            sr = ScoreResult(structural_score=structural_score(attack, emb), temporal_score=emb.temporal_score,
                             frequency_score=nov, attack_similarity=a_sim, benign_similarity=b_sim,
                             contrastive_score=contrast, risk_level=risk_level(contrast), best_benign=b_name)
            det = Detection(attack, emb, sr, b_emb, res.confidence, res.exhaustive,
                            sum(len(e.mapping) for e in res.embeddings), res.trace)
            scored.append((contrast, emb))
            if best is None or contrast > best.score.contrastive_score:
                best = det
        if best is not None:
            thr = 0.5 * best.score.contrastive_score
            # actors: hosts that initiated evidence, plus hosts taken over by remote logon
            best.related_nodes = {x for c, e in scored if c >= thr and c > 0 for ev in e.evidence
                                  for x in ([ev.source] + ([ev.destination] if ev.event_type == "auth_remote" else []))}
        return best
