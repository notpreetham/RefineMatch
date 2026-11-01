"""End-to-end analysis: observed telemetry -> banks -> match -> scores -> explanation.

Single integration point used by the experiments and the dashboard. It reuses
Member 1 (build/anonymize/refine), Member 2 (AGIR matching) and Member 3
(temporal/contrastive/risk) modules without re-implementing any of them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.core.exceptions import InvalidGraphError
from src.core.models import EventRecord, MatchResult, ScoreResult, TemporalGraph
from src.explanation.evidence_generator import generate_match_explanation
from src.graph.anonymizer import anonymize_graph
from src.graph.graph_builder import assign_node_attributes, build_temporal_graph
from src.ingestion.pattern_bank import BankPattern
from src.matching.graph_matcher import MatchDetails, MatcherConfig, match_graphs_detailed
from src.scoring.risk_score import RiskWeights, calculate_risk_score
from src.scoring.temporal_score import (
    calculate_frequency_similarity, calculate_order_similarity, calculate_temporal_consistency)


@dataclass
class PairEvidence:
    """All per-pattern evidence for one (reference pattern, observed) pair."""

    pattern: BankPattern
    details: MatchDetails
    structural: float
    order: float
    consistency: float
    frequency: float

    @property
    def temporal(self) -> float:
        """Temporal score = mean(order similarity, temporal consistency)."""
        return 0.5 * (self.order + self.consistency)


@dataclass
class AnalysisResult:
    """Full result of analysing one observed graph."""

    observed: TemporalGraph
    best_attack: PairEvidence
    best_benign: PairEvidence | None
    match: MatchResult
    score: ScoreResult
    explanation: dict
    attack_evidence: list[PairEvidence] = field(default_factory=list)
    benign_evidence: list[PairEvidence] = field(default_factory=list)


def prepare_observed(
    events: list[EventRecord],
    node_types: Mapping[str, str] | None = None,
    anonymize: bool = True,
) -> TemporalGraph:
    """Events -> (optionally typed) -> anonymised temporal graph."""
    graph = build_temporal_graph(events)
    if node_types:
        known = {n: t for n, t in node_types.items() if n in graph.graph}
        graph = assign_node_attributes(graph, known)
    return anonymize_graph(graph) if anonymize else graph


def compute_pair_evidence(
    pattern: BankPattern | TemporalGraph, observed: TemporalGraph, config: MatcherConfig | None = None
) -> PairEvidence:
    """Match one pattern against the observation and compute temporal evidence."""
    ref_tg = pattern if isinstance(pattern, TemporalGraph) else pattern.graph
    details = match_graphs_detailed(ref_tg, observed, config)
    return PairEvidence(
        pattern=pattern, details=details, structural=details.match.similarity,
        order=calculate_order_similarity(ref_tg.events, observed.events),
        consistency=calculate_temporal_consistency(ref_tg, observed, details.match),
        frequency=calculate_frequency_similarity(ref_tg, observed))


def best_evidence(evidence: list[PairEvidence]) -> PairEvidence | None:
    """Highest structural similarity (first in bank order on ties)."""
    best = None
    for item in evidence:
        if best is None or item.structural > best.structural:
            best = item
    return best


def _pattern_name(pattern: Any) -> str | None:
    if pattern is None:
        return None
    if hasattr(pattern, "name"):
        return pattern.name
    if hasattr(pattern, "meta") and isinstance(pattern.meta, dict):
        return pattern.meta.get("name", "")
    return getattr(pattern, "pattern_id", "pattern")


def analyze_observed(
    observed: TemporalGraph,
    attack_bank: list[BankPattern],
    benign_bank: list[BankPattern],
    weights: RiskWeights | None = None,
    matcher_config: MatcherConfig | None = None,
    identity_changed: bool | None = None,
    flag_threshold: float | None = None,
) -> AnalysisResult:
    """Run matching and scoring of ``observed`` against both banks."""
    if not attack_bank:
        raise InvalidGraphError("attack_bank is empty; load patterns first")
    attack_ev = [compute_pair_evidence(p, observed, matcher_config) for p in attack_bank]
    benign_ev = [compute_pair_evidence(p, observed, matcher_config) for p in benign_bank]
    top_attack, top_benign = best_evidence(attack_ev), best_evidence(benign_ev)
    kwargs = {} if flag_threshold is None else {"flag_threshold": flag_threshold}
    score = calculate_risk_score(
        top_attack.structural, top_attack.temporal, top_attack.frequency,
        top_attack.structural, top_benign.structural if top_benign else 0.0,
        weights=weights, **kwargs)
    explanation = generate_match_explanation(
        top_attack.details.match, score, _pattern_name(top_attack.pattern),
        _pattern_name(top_benign.pattern) if top_benign else None, identity_changed)
    return AnalysisResult(observed, top_attack, top_benign, top_attack.details.match, score,
                          explanation, attack_ev, benign_ev)
