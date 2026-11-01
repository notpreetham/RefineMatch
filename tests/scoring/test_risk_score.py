"""Tests for src.scoring.risk_score."""

import pytest

from src.core.exceptions import InvalidScoreInputError
from src.core.models import ScoreResult
from src.scoring.risk_score import RiskWeights, calculate_risk_score, level_for, tune_weights_and_threshold


def test_default_weights_valid_and_sum_to_one():
    assert abs(sum(RiskWeights().as_tuple()) - 1.0) < 1e-9


@pytest.mark.parametrize("args", [(0.5, 0.5, 0.5, 0.5), (-0.1, 0.5, 0.3, 0.3), (1.0, 1.0, 1.0, 1.0)])
def test_invalid_weights_rejected(args):
    with pytest.raises(InvalidScoreInputError):
        RiskWeights(*args)


def test_all_evidence_strong_gives_high_and_hand_checked_final():
    r = calculate_risk_score(1, 1, 1, 1, 0)
    assert isinstance(r, ScoreResult) and r.risk_level == "high"
    assert abs(r.final_score - 1.0) < 1e-12 and r.contrastive_score == 1.0


def test_all_evidence_absent_gives_low():
    r = calculate_risk_score(0, 0, 0, 0, 1)
    assert r.risk_level == "low" and r.final_score == 0.0 and r.contrastive_score == -1.0


def test_final_score_formula_with_custom_weights():
    w = RiskWeights(0.5, 0.2, 0.2, 0.1)
    r = calculate_risk_score(0.8, 0.5, 0.25, 0.6, 0.2, weights=w)
    expected = 0.5 * 0.8 + 0.2 * 0.5 + 0.2 * 0.25 + 0.1 * ((0.6 - 0.2) + 1) / 2
    assert abs(r.final_score - expected) < 1e-12


def test_borderline_levels_and_thresholds():
    assert level_for(0.59, 0.5) == "medium" and level_for(0.60, 0.5) == "high"
    assert level_for(0.39, 0.5) == "low" and level_for(0.40, 0.5) == "medium"


def test_contrastive_guard_downgrades_high_when_benign_is_as_similar():
    guarded = calculate_risk_score(1, 1, 1, 0.9, 0.9)
    unguarded = calculate_risk_score(1, 1, 1, 0.9, 0.9, use_contrastive_guard=False)
    assert guarded.final_score == unguarded.final_score >= 0.6
    assert guarded.risk_level == "medium" and unguarded.risk_level == "high"


def test_missing_evidence_zeros_do_not_crash_and_inputs_validated():
    assert calculate_risk_score(0, 0, 0, 0, 0).risk_level == "low"
    for bad in (float("nan"), -0.5, 1.5, None):
        with pytest.raises(InvalidScoreInputError):
            calculate_risk_score(bad, 0, 0, 0, 0)
    assert calculate_risk_score(1 + 1e-12, 0, 0, 0, 0).structural_score == 1.0  # tolerance


def test_tuning_finds_separating_weights_deterministically():
    pos = [(0.9, 0.9, 0.8, 0.8), (0.95, 0.7, 0.9, 0.6), (1.0, 1.0, 1.0, 0.9)]
    neg = [(0.1, 0.2, 0.3, -0.7), (0.2, 0.1, 0.1, -0.5), (0.0, 0.3, 0.2, -0.9)]
    samples, labels = pos + neg, [True] * 3 + [False] * 3
    w1, t1, f1 = tune_weights_and_threshold(samples, labels)
    assert f1 == 1.0 and abs(sum(w1.as_tuple()) - 1) < 1e-9
    assert (w1, t1, f1) == tune_weights_and_threshold(samples, labels)


def test_tuning_validates_input():
    with pytest.raises(InvalidScoreInputError):
        tune_weights_and_threshold([], [])
    with pytest.raises(InvalidScoreInputError):
        tune_weights_and_threshold([(1, 1, 1, 1)], [True, False])
    with pytest.raises(InvalidScoreInputError):
        tune_weights_and_threshold([(1, 1, 1, 1)], [True], step=0)
