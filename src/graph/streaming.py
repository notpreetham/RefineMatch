"""Streaming detection with append-local temporal colour refinement.

Events are consumed one at a time. The incremental TCR update touches only the two endpoints of
each event (property P2), so the colour state is always current in O(K) per event. Pattern
matching is *triggered*: it runs only when an event of a type that some attack template uses
touches a host, and only every ``check_every`` triggering events (or at window close), which bounds
detection latency while keeping throughput high. Tumbling windows expire state in O(1) amortised
time (rebuild on rollover).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.core.config import DEFAULT_TEMPORAL_WINDOW_SECONDS
from src.core.models import EventRecord
from src.pipeline import RefineMatch, WindowReport
from src.refinement.temporal import TemporalColorRefiner, static_color_refinement


@dataclass
class StreamAlert:
    detected_at: float          # stream time of the event that triggered the detection
    report: WindowReport
    pattern: str
    nodes: List[str]
    score: float


class StreamingDetector:
    def __init__(self, engine: RefineMatch, window: float = DEFAULT_TEMPORAL_WINDOW_SECONDS, check_every: int = 25):
        self.engine = engine
        self.window = window
        self.check_every = check_every
        self.trigger_types = {t for p in engine.attack_patterns for e in p.edges for t in e.types}
        self.reset(None)
        self.alerts: List[StreamAlert] = []
        self.seen_alerts = set()
        self.stats = dict(events=0, checks=0, tcr_seconds=0.0, match_seconds=0.0)

    def reset(self, start: Optional[float]):
        self.win_start = start
        self.buffer: List[EventRecord] = []
        self.refiner = TemporalColorRefiner(self.engine.known_roles)
        self.pending = 0

    def _check(self, now: float):
        t = time.perf_counter()
        rep = self.engine.analyze_window(self.buffer, self.win_start, self.win_start + self.window)
        self.stats["match_seconds"] += time.perf_counter() - t
        self.stats["checks"] += 1
        self.pending = 0
        for d in rep.alerts:
            key = (self.win_start, d.pattern.name, tuple(d.nodes))
            if key not in self.seen_alerts:
                self.seen_alerts.add(key)
                self.alerts.append(StreamAlert(now, rep, d.pattern.name, d.nodes, d.score.contrastive_score))

    def process(self, e: EventRecord):
        if self.win_start is None:
            self.reset(e.ts)
        if e.ts >= self.win_start + self.window:
            if self.pending:
                self._check(e.ts)
            while e.ts >= self.win_start + self.window:
                self.win_start += self.window
            self.reset(self.win_start)
        self.buffer.append(e)
        t = time.perf_counter()
        self.refiner.add_event(e)
        self.stats["tcr_seconds"] += time.perf_counter() - t
        self.stats["events"] += 1
        if e.event_type in self.trigger_types:
            self.pending += 1
            if self.pending >= self.check_every:
                self._check(e.ts)

    def flush(self):
        if self.buffer and self.pending:
            self._check(self.buffer[-1].ts)

    def run(self, events: List[EventRecord]) -> List[StreamAlert]:
        for e in events:
            self.process(e)
        self.flush()
        return self.alerts


def benchmark_refinement_update(events: List[EventRecord], roles: Dict[str, str], depth: int = 3,
                                recompute_every: int = 1, max_events: int = 600) -> dict:
    """Per-event cost of keeping colours current: incremental TCR vs. recomputing static WL."""
    evs = events[:max_events]
    inc = TemporalColorRefiner(roles, depth=depth)
    t = time.perf_counter()
    for e in evs:
        inc.add_event(e)
    t_inc = (time.perf_counter() - t) / len(evs)
    t = time.perf_counter()
    n = 0
    for i in range(0, len(evs), recompute_every):
        static_color_refinement(evs[: i + 1], roles, depth=depth)
        n += 1
    t_static = (time.perf_counter() - t) / len(evs)
    return dict(events=len(evs), incremental_tcr_us=t_inc * 1e6, recompute_static_wl_us=t_static * 1e6,
                speedup=t_static / t_inc if t_inc else float("inf"))
