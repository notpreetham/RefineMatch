r"""Individualization-refinement (IR) temporal pattern matching.

The observed window is large (hundreds of hosts) and a pattern is small, so whole-graph colour
equality is the wrong question; we need *temporal subgraph containment*. RefineMatch uses the
subgraph analogue of colour refinement:

1. **Initial colouring.** Each pattern node p gets a candidate set C(p) of observed hosts whose
   role and local statistics satisfy p's constraints.
2. **Containment refinement.** Repeat to a fixpoint: v stays in C(p) only if, for every pattern
   edge p->q, v has qualifying events (type, count, bytes, periodicity) to some w in C(q), and
   symmetrically for q. Singletons are made mutually exclusive (injectivity). This is (dual)
   simulation refinement -- the containment counterpart of 1-WL.
3. **Individualization.** If ambiguity remains, pick the most constrained pattern node,
   individualise it to each remaining candidate (branch), and refine again. Branching is
   exhaustive up to ``max_individualizations`` levels and ``max_branches`` per level, greedy
   beyond; ``exhaustive`` / ``confidence`` report whether the answer is exact.
4. **Temporal verification.** A complete assignment is checked against the pattern's partial
   order of edges and maximum span (earliest-feasible-time sweep, optimal for chain orders).
5. **Relaxation.** If no complete embedding exists we score the best *partial* one by relaxing
   numeric thresholds and dropping edges, so similarity degrades gracefully (needed for stealthy
   variants and for robustness margins).

Every decision is recorded in ``trace`` so the explanation module can produce a certificate.
"""

from __future__ import annotations

import itertools
import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field, replace
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from src.core.config import (DEFAULT_MAX_BRANCHES, DEFAULT_MAX_EMBEDDINGS, DEFAULT_MAX_INDIVIDUALIZATIONS,
                             DEFAULT_SEARCH_BUDGET)
from src.core.models import EvidenceEdge, MatchResult
from src.graph.builder import GraphIndex
from src.matching.pattern import EdgeSpec, NodeSpec, Pattern


@dataclass
class Embedding:
    mapping: Dict[str, str]
    evidence: List[EvidenceEdge]
    edge_coverage: float
    temporal_score: float
    relaxation: float = 1.0               # 1.0 = exact constraints, <1 = thresholds relaxed
    kept_edges: Tuple[int, ...] = ()
    alternatives: Dict[str, int] = field(default_factory=dict)  # leaf pattern node -> #interchangeable hosts

    @property
    def score(self) -> float:
        return self.edge_coverage * self.temporal_score * self.relaxation

    def edge_keys(self):
        return {(ev.source, ev.destination, ev.event_type) for ev in self.evidence}


def _cv(times: List[float]) -> float:
    if len(times) < 3:
        return float("inf")
    gaps = [b - a for a, b in zip(times, times[1:])]
    m = sum(gaps) / len(gaps)
    if m <= 0:
        return float("inf")
    var = sum((g - m) ** 2 for g in gaps) / len(gaps)
    return math.sqrt(var) / m


def periodic_chain(times: List[float], tol: float, max_events: int = 400) -> List[int]:
    """Indices of the longest *periodic subsequence*: consecutive gaps within +-tol of a common period.

    Unlike a coefficient-of-variation test on all events, this is monotone under insertion:
    padding a beacon channel with extra, off-schedule requests cannot destroy an existing periodic
    subsequence, so periodicity becomes certifiable (see robustness.certify)."""
    ts = sorted(times)[:max_events]
    n = len(ts)
    if n < 2:
        return list(range(n))
    cands = set()
    for i in range(min(n, 12)):
        for j in range(i + 1, min(n, i + 5)):
            d = ts[j] - ts[i]
            if d > 0:
                cands.add(round(d, 3))
    best: List[int] = [0]
    for P in sorted(cands):
        lo, hi = P * (1 - tol), P * (1 + tol)
        for s0 in range(n):
            if n - s0 <= len(best):
                break
            chain, last = [s0], ts[s0]
            while True:
                a = bisect_left(ts, last + lo)
                b = bisect_right(ts, last + hi)
                if a >= b:
                    break
                k = min(range(a, b), key=lambda x: abs(ts[x] - (last + P)))
                chain.append(k)
                last = ts[k]
            if len(chain) > len(best):
                best = chain
    return best


class _Stats:
    def __init__(self, budget):
        self.nodes = 0
        self.budget = budget
        self.truncated = 0
        self.branches = 0
        self.individualizations = 0
        self.max_depth = 0


class PatternMatcher:
    def __init__(self, index: GraphIndex, max_individualizations: int = DEFAULT_MAX_INDIVIDUALIZATIONS,
                 max_branches: int = DEFAULT_MAX_BRANCHES, max_embeddings: int = DEFAULT_MAX_EMBEDDINGS,
                 budget: int = DEFAULT_SEARCH_BUDGET, use_temporal: bool = True):
        self.ix = index
        self.max_ind = max_individualizations
        self.max_branches = max_branches
        self.max_emb = max_embeddings
        self.budget = budget
        self.use_temporal = use_temporal
        self._edge_cache: Dict[tuple, Optional[List[Tuple[float, int, str]]]] = {}

    # ---------------------------------------------------------------- constraint checks
    def qualifying_events(self, v: str, w: str, e: EdgeSpec) -> Optional[List[Tuple[float, int, str]]]:
        """Events v->w satisfying edge spec e, or None if the pair does not qualify."""
        key = (v, w, tuple(sorted(e.types)), e.min_count, e.min_bytes, e.periodic, e.max_cv)
        if key in self._edge_cache:
            return self._edge_cache[key]
        evs = self.ix.events_between(v, w, e.types)
        res = None
        if len(evs) >= e.min_count and (e.min_bytes <= 0 or max(b for _, b, _ in evs) >= e.min_bytes):
            if e.min_bytes > 0:
                evs = [x for x in evs if x[1] >= e.min_bytes] if e.min_count <= 1 else evs
            if not e.periodic:
                res = evs
            else:
                chain = periodic_chain([t for t, _, _ in evs], e.max_cv)
                if len(chain) >= e.min_count:
                    srt = sorted(evs)
                    res = [srt[i] for i in chain]
        self._edge_cache[key] = res
        return res

    def initial_candidates(self, pattern: Pattern, restrict: Optional[Dict[str, Set[str]]] = None) -> Dict[str, Set[str]]:
        C = {}
        for p, spec in pattern.nodes.items():
            pool = restrict.get(p) if restrict and p in restrict else self.ix.nodes
            C[p] = {v for v in pool if v in self.ix.roles and
                    spec.accepts(self.ix.roles[v], lambda et, v=v: self.ix.out_distinct(v, et))}
        return C

    def refine(self, pattern: Pattern, C: Dict[str, Set[str]], trace: Optional[list] = None,
               edges: Optional[List[EdgeSpec]] = None) -> Optional[Dict[str, Set[str]]]:
        edges = pattern.edges if edges is None else edges
        C = {p: set(s) for p, s in C.items()}
        changed, it = True, 0
        while changed:
            changed, it = False, it + 1
            for e in edges:
                cq = C[e.dst]
                newp = set()
                for v in C[e.src]:
                    for w in self.ix.out_neighbors(v, e.types) & cq:
                        if w != v and self.qualifying_events(v, w, e) is not None:
                            newp.add(v)
                            break
                if len(newp) < len(C[e.src]):
                    if trace is not None:
                        trace.append({"iter": it, "node": e.src, "edge": f"{e.src}->{e.dst}", "types": sorted(e.types),
                                      "before": len(C[e.src]), "after": len(newp)})
                    C[e.src], changed = newp, True
                cp = C[e.src]
                newq = set()
                for w in C[e.dst]:
                    for v in self.ix.in_neighbors(w, e.types) & cp:
                        if w != v and self.qualifying_events(v, w, e) is not None:
                            newq.add(w)
                            break
                if len(newq) < len(C[e.dst]):
                    if trace is not None:
                        trace.append({"iter": it, "node": e.dst, "edge": f"{e.src}->{e.dst}", "types": sorted(e.types),
                                      "before": len(C[e.dst]), "after": len(newq)})
                    C[e.dst], changed = newq, True
            # injectivity on singletons
            singles = {p: next(iter(s)) for p, s in C.items() if len(s) == 1}
            for p, s in C.items():
                for q, v in singles.items():
                    if q != p and v in s and len(s) > 1:
                        s.discard(v)
                        changed = True
            if any(len(s) == 0 for s in C.values()):
                return None
            if len(set(singles.values())) < len(singles):
                return None
        return C

    # ---------------------------------------------------------------- temporal verification
    def verify_temporal(self, pattern: Pattern, mapping: Dict[str, str], edges_idx: List[int]):
        """Choose one event per pattern edge respecting order and span. Returns (score, evidence)."""
        edges = [(i, pattern.edges[i]) for i in edges_idx]
        lists = {i: self.qualifying_events(mapping[e.src], mapping[e.dst], e) for i, e in edges}
        if any(v is None for v in lists.values()):
            return 0.0, []
        total_w = sum(e.weight for _, e in edges) or 1.0
        if not self.use_temporal:
            ev = [EvidenceEdge(e.src, e.dst, mapping[e.src], mapping[e.dst], lists[i][0][2], lists[i][0][0], e.order)
                  for i, e in edges]
            return 1.0, ev
        groups: Dict[int, List[Tuple[int, EdgeSpec]]] = {}
        for i, e in edges:
            groups.setdefault(e.order, []).append((i, e))
        orders = sorted(groups)
        first = groups[orders[0]]
        starts = sorted({t for i, _ in first for t, _, _ in lists[i]})[:64]
        best = (-1.0, float("inf"), [])
        for s in starts:
            prev, inclusive = s, True   # first order group may start exactly at s
            sat_w, ev, t_first = 0.0, [], None
            for o in orders:
                gmax = prev
                for i, e in groups[o]:
                    times = [x[0] for x in lists[i]]
                    j = bisect_left(times, prev) if inclusive else bisect_right(times, prev)
                    if j >= len(times):
                        continue
                    t, _b, et = lists[i][j]
                    if t_first is not None and t - t_first > pattern.max_span:
                        continue
                    t_first = t if t_first is None else t_first
                    gmax = max(gmax, t)
                    sat_w += e.weight
                    ev.append(EvidenceEdge(e.src, e.dst, mapping[e.src], mapping[e.dst], et, t, e.order))
                prev, inclusive = gmax, False
            span = (max(x.timestamp for x in ev) - min(x.timestamp for x in ev)) if ev else float("inf")
            if sat_w > best[0] + 1e-12 or (abs(sat_w - best[0]) < 1e-12 and span < best[1]):
                best = (sat_w, span, ev)
            if sat_w >= total_w - 1e-12:
                break
        return best[0] / total_w, best[2]

    # ---------------------------------------------------------------- IR search
    def _search(self, pattern, C, edges, edges_idx, depth, stats, found: List[Embedding], seen: Set[FrozenSet],
                trace, coverage, relax):
        stats.nodes += 1
        if stats.nodes > stats.budget:
            stats.truncated += 1
            return
        C = self.refine(pattern, C, trace if depth == 0 else None, edges)
        if C is None:
            return
        open_nodes = [p for p, s in C.items() if len(s) > 1]
        if not open_nodes:
            mapping = {p: next(iter(s)) for p, s in C.items()}
            key = frozenset(mapping.items())
            if key in seen:
                return
            seen.add(key)
            ts, ev = self.verify_temporal(pattern, mapping, edges_idx)
            found.append(Embedding(mapping, ev, coverage, ts, relax, tuple(edges_idx)))
            return
        deg = {p: sum(1 for e in edges if p in (e.src, e.dst)) for p in C}
        # Leaf compression: if every open node is a pattern leaf hanging off an already-fixed node, its
        # candidates are interchangeable (e.g. the targets of a scan). Emit ONE representative embedding
        # and record how many alternatives exist instead of enumerating them -- this keeps fan-out
        # patterns from flooding the embedding budget and feeds the deletion certificate.
        nbr = {p: {e.dst if e.src == p else e.src for e in edges if p in (e.src, e.dst)} for p in C}
        if all(deg[p] == 1 and all(len(C[q]) == 1 for q in nbr[p]) for p in open_nodes):
            mapping = {p: next(iter(s)) for p, s in C.items() if len(s) == 1}
            for p in sorted(open_nodes):  # provisional injective choice for every leaf
                free = sorted(C[p] - set(mapping.values()))
                if not free:
                    return
                mapping[p] = free[0]
            alts = {}
            for p in sorted(open_nodes):
                taken = {v for q, v in mapping.items() if q != p}
                cands = sorted(C[p] - taken)
                best_v, best_s = mapping[p], -1.0
                for v in cands[: self.max_branches]:
                    mapping[p] = v
                    sc, _ = self.verify_temporal(pattern, mapping, edges_idx)
                    if sc > best_s:
                        best_v, best_s = v, sc
                    if sc >= 1.0:
                        break
                mapping[p] = best_v
                alts[p] = len(cands)
            key = frozenset(mapping.items())
            if key in seen:
                return
            seen.add(key)
            ts, ev = self.verify_temporal(pattern, mapping, edges_idx)
            found.append(Embedding(mapping, ev, coverage, ts, relax, tuple(edges_idx), alts))
            return
        # individualise the most constrained node (smallest candidate set, then highest pattern degree)
        p = min(open_nodes, key=lambda x: (len(C[x]), -deg[x], x))
        cands = sorted(C[p])
        stats.branches += len(cands)
        stats.individualizations += 1
        stats.max_depth = max(stats.max_depth, depth + 1)
        if depth >= self.max_ind:
            limit = 1
        else:
            limit = self.max_branches
        if len(cands) > limit:
            stats.truncated += len(cands) - limit
        if trace is not None and depth < 2:
            trace.append({"individualize": p, "depth": depth + 1, "candidates": len(cands), "explored": min(limit, len(cands))})
        for v in cands[:limit]:
            if len(found) >= self.max_emb * 4:
                stats.truncated += 1
                return
            C2 = {q: (set(s) - {v}) if q != p else {v} for q, s in C.items()}
            self._search(pattern, C2, edges, edges_idx, depth + 1, stats, found, seen, trace, coverage, relax)

    @staticmethod
    def relaxation_variants(pattern: Pattern):
        """(edge indices, threshold factor) of every relaxation tried by :meth:`match`, exact first."""
        all_idx = list(range(len(pattern.edges)))
        out = [(all_idx, 1.0), (all_idx, 0.75), (all_idx, 0.5)]
        n = len(pattern.edges)
        subsets = []
        for k in range(n - 1, max(0, (n + 1) // 2) - 1, -1):
            if k == 0:
                break
            subsets += list(itertools.combinations(all_idx, k))
        out += [(list(sset), 1.0) for sset in subsets[:40]]
        return out

    @staticmethod
    def subpattern(pattern: Pattern, edges_idx, relax: float) -> Pattern:
        sub_edges = [pattern.edges[i] for i in edges_idx]
        if relax < 1.0:
            sub_edges = [replace(e, min_count=max(1, int(math.ceil(e.min_count * relax))),
                                 min_bytes=int(e.min_bytes * relax),
                                 max_cv=e.max_cv / relax if e.periodic else e.max_cv) for e in sub_edges]
        nodes_used = {x for e in sub_edges for x in (e.src, e.dst)}
        sub_nodes = {}
        for n in nodes_used:
            spec = pattern.nodes[n]
            if relax < 1.0:
                spec = replace(spec, min_out_distinct={k: max(1, int(math.ceil(v * relax)))
                                                       for k, v in spec.min_out_distinct.items()})
            sub_nodes[n] = spec
        return replace(pattern, nodes=sub_nodes, edges=sub_edges)

    def match_variant(self, pattern: Pattern, edges_idx, relax: float):
        """Embeddings of one relaxation variant (used by the robustness certificate)."""
        stats = _Stats(self.budget)
        found = self._run(pattern, list(edges_idx), relax, None, None, stats)
        return self.subpattern(pattern, edges_idx, relax), found, stats.truncated == 0

    def _run(self, pattern, edges_idx, relax, restrict, trace, stats):
        sub = self.subpattern(pattern, edges_idx, relax)
        sub_edges = sub.edges
        C = self.initial_candidates(sub, restrict)
        if trace is not None:
            trace.append({"initial": {p: len(s) for p, s in C.items()}, "relaxation": relax,
                          "edges": [f"{e.src}->{e.dst}" for e in sub_edges]})
        found: List[Embedding] = []
        coverage = sum(e.weight for e in sub_edges) / pattern.total_weight
        # remap evidence/edge indices to the full pattern
        local_idx = list(range(len(sub_edges)))
        self._search(sub, C, sub_edges, local_idx, 0, stats, found, set(), trace, coverage, relax)
        for emb in found:
            emb.kept_edges = tuple(edges_idx)
        return found

    def match(self, pattern: Pattern, restrict: Optional[Dict[str, Set[str]]] = None,
              relax: bool = True, with_trace: bool = True) -> MatchResult:
        trace: Optional[list] = [] if with_trace else None
        stats = _Stats(self.budget)
        all_idx = list(range(len(pattern.edges)))
        found = self._run(pattern, all_idx, 1.0, restrict, trace, stats)
        if relax:
            # Threshold relaxation on the full edge set, then edge-subset relaxation. Always run: an
            # exact embedding elsewhere (e.g. a sanctioned look-alike) must not hide a partial match of
            # the real attack -- the contrastive scorer and the deletion certificate both rely on it.
            for idx, f in self.relaxation_variants(pattern)[1:]:
                found += self._run(pattern, idx, f, restrict, None, stats)
        # rank & deduplicate by mapping
        found.sort(key=lambda e: (-e.score, sorted(e.mapping.items())))
        uniq, seen = [], set()
        for f in found:
            k = frozenset(f.mapping.items())
            if k in seen:
                continue
            seen.add(k)
            uniq.append(f)
        uniq = uniq[: self.max_emb]
        exhaustive = stats.truncated == 0
        confidence = 1.0 if exhaustive else max(0.1, 1.0 - stats.truncated / max(1, stats.branches + stats.truncated))
        if not uniq:
            return MatchResult(similarity=0.0, node_mapping={}, matched_nodes=[], unmatched_observed_nodes=[],
                               unmatched_reference_nodes=sorted(pattern.nodes), individualization_count=stats.individualizations,
                               confidence=confidence, pattern_name=pattern.name, exhaustive=exhaustive, trace=trace or [])
        best = uniq[0]
        others = sorted({v for e in uniq[1:] for v in e.mapping.values()} - set(best.mapping.values()))
        return MatchResult(similarity=best.score, node_mapping=dict(best.mapping), matched_nodes=sorted(set(best.mapping.values())),
                           unmatched_observed_nodes=others,
                           unmatched_reference_nodes=sorted(set(pattern.nodes) - set(best.mapping)),
                           individualization_count=stats.individualizations, confidence=confidence,
                           pattern_name=pattern.name, evidence=best.evidence, edge_coverage=best.edge_coverage,
                           temporal_score=best.temporal_score, exhaustive=exhaustive, embeddings=uniq,
                           trace=trace or [])


def match_pattern(index: GraphIndex, pattern: Pattern, **kw) -> MatchResult:
    return PatternMatcher(index, **{k: v for k, v in kw.items() if k in
                                    ("max_individualizations", "max_branches", "max_embeddings", "budget", "use_temporal")}
                          ).match(pattern, **{k: v for k, v in kw.items() if k in ("restrict", "relax", "with_trace")})
