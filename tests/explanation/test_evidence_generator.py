"""Tests for src.explanation.evidence_generator and src.pipeline."""

import pytest

from src.core.exceptions import InvalidGraphError
from src.core.models import MatchResult
from src.explanation.evidence_generator import DISCLAIMER, generate_match_explanation
from src.graph.anonymizer import anonymize_graph
from src.ingestion.pattern_bank import load_default_banks
from src.ingestion.synthetic_generator import (
    BENIGN_PATTERNS, SUSPICIOUS_PATTERNS, generate_synthetic_events, generate_synthetic_graph)
from src.pipeline import analyze_observed, prepare_observed
from src.scoring.risk_score import calculate_risk_score

KEYS = {"matched_pattern", "structural_evidence", "temporal_evidence",
        "identity_independence_evidence", "benign_comparison", "risk_level"}
MATCH = MatchResult(0.9, {"a": "x"}, ["a"], [], [], 1, 0.8)


def test_explanation_has_required_keys_and_never_claims_proof():
    for score in (calculate_risk_score(1, 1, 1, 1, 0), calculate_risk_score(0.5, 0.5, 0.5, 0.5, 0.5),
                  calculate_risk_score(0, 0, 0, 0, 1)):
        text = generate_match_explanation(MATCH, score, "Pattern X", "Benign Y", identity_changed=True)
        assert KEYS <= set(text)
        blob = " ".join(str(v) for v in text.values()).lower()
        assert "proves an attack" not in blob and "confirmed attack" in blob  # only in the disclaimer
        assert text["disclaimer"] == DISCLAIMER and text["risk_level"] == score.risk_level


def test_explanation_reflects_benign_comparison():
    strong = generate_match_explanation(MATCH, calculate_risk_score(1, 1, 1, 0.9, 0.1))
    weak = generate_match_explanation(MATCH, calculate_risk_score(1, 1, 1, 0.5, 0.9))
    assert "less similar" in strong["benign_comparison"] and "weakens" in weak["benign_comparison"]
    assert generate_match_explanation(MATCH, calculate_risk_score(1, 1, 1, 1, 0))["matched_pattern"] is None


def test_pipeline_end_to_end_on_every_synthetic_pattern():
    attack, benign = load_default_banks()
    for name in SUSPICIOUS_PATTERNS:
        result = analyze_observed(anonymize_graph(generate_synthetic_graph(name, 21)), attack, benign)
        assert result.score.risk_level == "high" and result.score.structural_score > 0.95
    for name in BENIGN_PATTERNS:
        result = analyze_observed(anonymize_graph(generate_synthetic_graph(name, 21)), attack, benign)
        assert result.score.risk_level == "low" and result.score.benign_similarity > 0.95


def test_pipeline_result_independent_of_identities_across_seeds():
    attack, benign = load_default_banks()
    levels = {analyze_observed(anonymize_graph(generate_synthetic_graph("c2_like", s)), attack, benign).score.risk_level
              for s in range(5)}
    assert levels == {"high"}


def test_prepare_observed_and_validation():
    events = generate_synthetic_events("c2_like", 1)
    graph = prepare_observed(events)
    assert all(n.startswith("N_") for n in graph.graph.nodes)
    assert not any(n.startswith("N_") for n in prepare_observed(events, anonymize=False).graph.nodes)
    attack, benign = load_default_banks()
    with pytest.raises(InvalidGraphError):
        analyze_observed(graph, [], benign)
    assert analyze_observed(graph, attack, []).score.benign_similarity == 0.0
