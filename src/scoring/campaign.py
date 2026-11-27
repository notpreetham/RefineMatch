"""Multi-stage campaign stitching across windows (kill-chain reasoning).

Detections from different windows are linked when they share an internal host, respect the
ATT&CK tactic order (command-and-control may appear anywhere) and are close in time. The best
chain is found by dynamic programming over this DAG. Evidence accumulates with a noisy-OR over
*distinct tactics*, so several individually sub-threshold stages on the same host can form a
high-confidence campaign -- this is how stealthy intrusions that never trip a single-window
threshold are still caught.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.scoring.contrastive import Detection

TACTIC_ORDER = {"discovery": 0, "credential-access": 1, "lateral-movement": 2, "collection": 3, "exfiltration": 4}
WILDCARD = {"command-and-control"}
EXTERNAL = {"external", "saas"}


@dataclass
class Alert:
    detection: Detection
    window_start: float
    hosts: frozenset

    @property
    def tactic(self) -> str:
        return self.detection.pattern.tactic

    @property
    def score(self) -> float:
        return self.detection.score.contrastive_score

    @property
    def time(self) -> float:
        t0, _ = self.detection.time_range
        return t0 if t0 is not None else self.window_start


@dataclass
class Campaign:
    alerts: List[Alert]
    score: float
    tactics: List[str]
    hosts: List[str]
    stages_covered: int = 0
    narrative: List[str] = field(default_factory=list)


STAGE_CAP = 0.9  # no single window is treated as conclusive on its own


def _noisy_or(alerts: List[Alert]) -> float:
    best_per_tactic: Dict[str, float] = {}
    for a in alerts:
        best_per_tactic[a.tactic] = max(best_per_tactic.get(a.tactic, 0.0), a.score)
    p = 1.0
    for s in best_per_tactic.values():
        p *= (1 - min(s, STAGE_CAP))
    return 1 - p


def _can_follow(a: Alert, b: Alert, max_gap: float) -> bool:
    if b.time < a.time or b.time - a.time > max_gap:
        return False
    if not (a.hosts & b.hosts):
        return False
    if a.tactic in WILDCARD or b.tactic in WILDCARD:
        return True
    return TACTIC_ORDER.get(a.tactic, 0) <= TACTIC_ORDER.get(b.tactic, 0)


def stitch_campaigns(window_detections: List[Tuple[float, List[Detection]]], roles: Dict[str, str],
                     min_score: float = 0.3, max_gap: float = 6 * 3600, top_k: int = 3) -> List[Campaign]:
    alerts: List[Alert] = []
    for wstart, dets in window_detections:
        for d in dets:
            if d.score.contrastive_score >= min_score:
                hosts = frozenset(v for v in (d.related_nodes or set(d.nodes)) if roles.get(v, "workstation") not in EXTERNAL
                                  and roles.get(v) not in ("dc", "dns", "fileserver"))  # shared infra links everything
                alerts.append(Alert(d, wstart, hosts))
    alerts.sort(key=lambda a: a.time)
    n = len(alerts)
    best: List[Tuple[float, List[int]]] = [(0.0, [])] * n
    for j in range(n):
        cand = [(_noisy_or([alerts[j]]), [j])]
        for i in range(j):
            if _can_follow(alerts[i], alerts[j], max_gap):
                chain = best[i][1] + [j]
                cand.append((_noisy_or([alerts[k] for k in chain]), chain))
        best[j] = max(cand, key=lambda x: (x[0], len(x[1])))
    camps: List[Campaign] = []
    used = set()
    for score, chain in sorted(best, key=lambda x: (-x[0], -len(x[1]))):
        if not chain or chain[-1] in used:
            continue
        used.update(chain)
        al = [alerts[k] for k in chain]
        tactics = []
        for a in al:
            if a.tactic not in tactics:
                tactics.append(a.tactic)
        hosts = sorted(set().union(*[a.hosts for a in al]))
        narrative = [f"{a.tactic}: {a.detection.pattern.name} on {', '.join(a.detection.nodes)} "
                     f"(score {a.score:.2f})" for a in al]
        camps.append(Campaign(al, score, tactics, hosts, len([t for t in tactics if t in TACTIC_ORDER]), narrative))
        if len(camps) >= top_k:
            break
    return camps
