"""End-to-end RefineMatch engine: window -> temporal graph -> TCR -> IR matching -> contrastive
score -> certificate (explanation + robustness radius) -> campaign stitching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.core.config import (DEFAULT_BENIGN_LAMBDA, DEFAULT_MATCH_THRESHOLD, DEFAULT_MAX_INDIVIDUALIZATIONS,
                             DEFAULT_NOVELTY_ALPHA, DEFAULT_TEMPORAL_WINDOW_SECONDS)
from src.core.models import EventRecord, TemporalGraph
from src.graph.builder import GraphIndex, build_temporal_graph, infer_roles, windows
from src.matching.matcher import PatternMatcher
from src.matching.pattern import Pattern
from src.matching.templates import template_library
from src.scoring.campaign import Campaign, stitch_campaigns
from src.scoring.contrastive import BenignProfile, ContrastiveScorer, Detection


@dataclass
class WindowReport:
    start: float
    end: float
    detections: List[Detection]                 # best detection per attack template, highest first
    threshold: float
    graph: TemporalGraph = None
    index: GraphIndex = None

    @property
    def score(self) -> float:
        return max((d.score.contrastive_score for d in self.detections), default=0.0)

    @property
    def alerts(self) -> List[Detection]:
        return [d for d in self.detections if d.score.contrastive_score >= self.threshold]

    def node_scores(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for d in self.detections:
            for v in d.nodes:
                out[v] = max(out.get(v, 0.0), d.score.contrastive_score)
        return out


class RefineMatch:
    def __init__(self, known_roles: Optional[Dict[str, str]] = None, library: Optional[Dict[str, Pattern]] = None,
                 threshold: float = DEFAULT_MATCH_THRESHOLD, lam: float = DEFAULT_BENIGN_LAMBDA,
                 alpha: float = DEFAULT_NOVELTY_ALPHA, use_benign: bool = True, use_temporal: bool = True,
                 max_individualizations: int = DEFAULT_MAX_INDIVIDUALIZATIONS, use_novelty: bool = True):
        self.known_roles = known_roles or {}
        self.library = library or template_library()
        self.threshold = threshold
        self.use_temporal = use_temporal
        self.max_ind = max_individualizations
        self.use_novelty = use_novelty
        self.profile = BenignProfile()
        self.scorer = ContrastiveScorer(self.library, self.profile if use_novelty else None, lam=lam,
                                        alpha=alpha if use_novelty else 1.0, use_benign=use_benign)

    @property
    def attack_patterns(self) -> List[Pattern]:
        return [p for p in self.library.values() if p.kind == "attack"]

    def roles_for(self, events: List[EventRecord]) -> Dict[str, str]:
        return infer_roles(events, known=self.known_roles)

    def fit_baseline(self, benign_windows: List[List[EventRecord]]) -> "RefineMatch":
        """Learn colour frequencies from historical traffic (no attack labels needed)."""
        for evs in benign_windows:
            tg = build_temporal_graph(evs, self.roles_for(evs))
            roles = {n: d["role"] for n, d in tg.graph.nodes(data=True)}
            self.profile.add(self.profile.window_colors(tg, roles))
        return self

    def analyze_window(self, events: List[EventRecord], start: Optional[float] = None,
                       end: Optional[float] = None, patterns: Optional[List[Pattern]] = None) -> WindowReport:
        roles = self.roles_for(events)
        tg = build_temporal_graph(events, roles, start, end)
        ix = GraphIndex(tg)
        matcher = PatternMatcher(ix, max_individualizations=self.max_ind, use_temporal=self.use_temporal)
        levels = self.profile.window_colors(tg, ix.roles) if (self.use_novelty and self.profile.n_windows) else None
        cache: dict = {}
        dets = []
        for p in patterns or self.attack_patterns:
            d = self.scorer.score_pattern(matcher, p, levels, cache)
            if d is not None:
                dets.append(d)
        dets.sort(key=lambda d: -d.score.contrastive_score)
        s = start if start is not None else (events[0].ts if events else 0.0)
        e = end if end is not None else (events[-1].ts if events else 0.0)
        return WindowReport(s, e, dets, self.threshold, tg, ix)

    def analyze_stream(self, events: List[EventRecord], size: float = DEFAULT_TEMPORAL_WINDOW_SECONDS,
                       step: Optional[float] = None) -> List[WindowReport]:
        return [self.analyze_window(evs, s, e) for s, e, evs in windows(events, size, step)]

    def campaigns(self, reports: List[WindowReport], min_score: float = 0.3) -> List[Campaign]:
        roles: Dict[str, str] = dict(self.known_roles)
        for r in reports:
            roles.update(r.index.roles)
        return stitch_campaigns([(r.start, r.detections) for r in reports], roles, min_score=min_score)
