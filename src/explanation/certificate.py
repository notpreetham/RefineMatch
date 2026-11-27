"""Explainable-by-construction alerts: machine-checkable detection certificates.

A post-hoc explainer (GNNExplainer, SHAP, ...) approximates *why a model* fired and can be
unfaithful. RefineMatch's decision is a combinatorial fact, so the explanation is a **certificate**
an analyst (or a script) can verify independently in O(|pattern| * log |events|):

* the embedding (pattern node -> host) and the role / fan-out constraints each host satisfies;
* one concrete log event per pattern edge, in causal order and within the time span;
* the refinement trace (how candidate sets shrank) and individualization choices;
* the contrast: which benign look-alikes were tried and *which evidence they cannot explain*;
* a counterfactual: the minimal edits that would make the alert disappear (robustness module).

``verify_certificate`` re-checks every claim against the raw graph -- faithfulness is 1.0 by
construction, and tampering with the evidence is detected.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.core.models import EvidenceEdge
from src.graph.builder import GraphIndex
from src.matching.matcher import PatternMatcher
from src.matching.pattern import Pattern
from src.robustness.certify import RobustnessCertificate, max_benign_explanation
from src.scoring.contrastive import ContrastiveScorer, Detection


def _fmt_t(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class DetectionCertificate:
    pattern: str
    tactic: str
    techniques: List[str]
    mapping: Dict[str, str]
    roles: Dict[str, str]
    node_facts: List[str]
    evidence: List[dict]
    scores: dict
    refinement_trace: List[dict]
    individualizations: int
    exhaustive: bool
    benign_contrast: List[str]
    unexplained_evidence: List[str]
    robustness: Optional[dict] = None
    robustness_summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        L = [f"ALERT {self.pattern} [{self.tactic}; {', '.join(self.techniques)}]  "
             f"score={self.scores['contrastive_score']:.2f} ({self.scores['risk_level']})"]
        L.append("  hosts: " + ", ".join(f"{p}={v}({self.roles.get(v, '?')})" for p, v in sorted(self.mapping.items())))
        for f in self.node_facts:
            L.append(f"  fact: {f}")
        L.append("  evidence (causal order):")
        for e in sorted(self.evidence, key=lambda x: (x["order"], x["timestamp"])):
            L.append(f"    [{e['order']}] {_fmt_t(e['timestamp'])}  {e['source']} -> {e['destination']}  {e['event_type']}"
                     f"  (count={e.get('count', 1)})")
        L.append(f"  attack_sim={self.scores['attack_similarity']:.2f}  benign_sim={self.scores['benign_similarity']:.2f}"
                 f"  novelty={self.scores['frequency_score']:.2f}  temporal={self.scores['temporal_score']:.2f}"
                 f"  structural={self.scores['structural_score']:.2f}")
        for b in self.benign_contrast:
            L.append(f"  why not benign: {b}")
        for u in self.unexplained_evidence[:4]:
            L.append(f"  unexplained: {u}")
        L.append(f"  search: {self.individualizations} individualization(s), "
                 f"{'exhaustive' if self.exhaustive else 'budget-limited'}")
        if self.robustness_summary:
            L.append(f"  robustness: {self.robustness_summary}")
        return "\n".join(L)


def build_certificate(det: Detection, matcher: PatternMatcher, scorer: ContrastiveScorer,
                      robustness: Optional[RobustnessCertificate] = None) -> DetectionCertificate:
    p, emb, ix = det.pattern, det.embedding, matcher.ix
    facts = []
    for pn, v in sorted(emb.mapping.items()):
        spec = p.nodes.get(pn)
        if spec is None:
            continue
        for et, n in spec.min_out_distinct.items():
            facts.append(f"{v} contacted {ix.out_distinct(v, et)} distinct hosts via '{et}' (threshold {n})")
        if pn in emb.alternatives:
            facts.append(f"{emb.alternatives[pn]} interchangeable hosts fit pattern node '{pn}'")
    evidence = []
    for ev in emb.evidence:
        spec = next((e for e in p.edges if e.src == ev.pattern_src and e.dst == ev.pattern_dst and ev.event_type in e.types), None)
        q = matcher.qualifying_events(ev.source, ev.destination, spec) if spec else None
        d = asdict(ev)
        d["count"] = len(q) if q else 1
        if spec and spec.min_bytes:
            d["max_bytes"] = max(b for _, b, _ in q) if q else 0
        evidence.append(d)
    contrast = []
    if det.score.best_benign:
        contrast.append(f"closest benign template '{det.score.best_benign}' explains only "
                        f"{det.score.benign_similarity:.0%} of the weighted evidence")
    _, bname, missing = max_benign_explanation(scorer, matcher, p, emb)
    if not det.score.best_benign and p.benign_counterparts:
        contrast.append(f"no benign counterpart ({', '.join(p.benign_counterparts)}) matches these hosts")
    s = det.score
    return DetectionCertificate(
        pattern=p.name, tactic=p.tactic, techniques=list(p.techniques), mapping=dict(emb.mapping),
        roles={v: ix.roles.get(v, "?") for v in emb.mapping.values()}, node_facts=facts, evidence=evidence,
        scores=dict(structural_score=s.structural_score, temporal_score=s.temporal_score,
                    frequency_score=s.frequency_score, attack_similarity=s.attack_similarity,
                    benign_similarity=s.benign_similarity, contrastive_score=s.contrastive_score,
                    risk_level=s.risk_level),
        refinement_trace=det.trace[:30], individualizations=sum(1 for t in det.trace if "individualize" in t),
        exhaustive=det.exhaustive, benign_contrast=contrast, unexplained_evidence=missing,
        robustness=asdict(robustness) if robustness else None,
        robustness_summary=robustness.summary() if robustness else "")


def verify_certificate(cert: DetectionCertificate, index: GraphIndex, pattern: Pattern) -> Tuple[bool, List[str]]:
    """Independently re-check every claim of a certificate against the raw event index."""
    problems = []
    m = cert.mapping
    if len(set(m.values())) != len(m):
        problems.append("mapping is not injective")
    for pn, v in m.items():
        spec = pattern.nodes.get(pn)
        if spec is None:
            problems.append(f"unknown pattern node {pn}")
            continue
        role = index.roles.get(v)
        if role is None:
            problems.append(f"host {v} not in window")
        elif not spec.accepts(role, lambda et, v=v: index.out_distinct(v, et)):
            problems.append(f"host {v} ({role}) violates constraints of node {pn}")
    by_edge = {}
    for ev in cert.evidence:
        by_edge.setdefault((ev["pattern_src"], ev["pattern_dst"]), []).append(ev)
        if m.get(ev["pattern_src"]) != ev["source"] or m.get(ev["pattern_dst"]) != ev["destination"]:
            problems.append(f"evidence {ev['source']}->{ev['destination']} inconsistent with mapping")
        real = index.events_between(ev["source"], ev["destination"], {ev["event_type"]})
        if not any(abs(t - ev["timestamp"]) < 1e-6 for t, _, _ in real):
            problems.append(f"evidence event {ev['source']}->{ev['destination']}@{ev['timestamp']} does not exist")
    matcher = PatternMatcher(index)
    for e in pattern.edges:
        if e.src in m and e.dst in m:
            if (e.src, e.dst) not in by_edge:
                problems.append(f"no evidence for pattern edge {e.src}->{e.dst}")
            elif matcher.qualifying_events(m[e.src], m[e.dst], e) is None:
                problems.append(f"edge {e.src}->{e.dst} does not meet count/bytes/periodicity constraints")
    # causal order and span
    evs = sorted(cert.evidence, key=lambda x: x["order"])
    for a in evs:
        for b in evs:
            if a["order"] < b["order"] and not a["timestamp"] < b["timestamp"]:
                problems.append(f"order violated: {a['source']}->{a['destination']} !< {b['source']}->{b['destination']}")
    if evs:
        span = max(x["timestamp"] for x in evs) - min(x["timestamp"] for x in evs)
        if span > pattern.max_span + 1e-6:
            problems.append(f"span {span:.0f}s exceeds {pattern.max_span:.0f}s")
    return (not problems), problems
