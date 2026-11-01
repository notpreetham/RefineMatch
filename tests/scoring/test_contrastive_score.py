"""Tests for src.scoring.contrastive_score."""

from datetime import datetime, timedelta

import pytest

from src.core.exceptions import InvalidScoreInputError
from src.core.models import EventRecord
from src.graph.graph_builder import build_temporal_graph
from src.scoring.contrastive_score import (
    calculate_contrastive_score, find_best_attack_similarity, find_best_benign_similarity,
    find_best_pattern_match, normalize_contrastive)

T0 = datetime(2024, 1, 1)


def mk(spec):
    return build_temporal_graph([EventRecord(T0 + timedelta(seconds=i), s, d, t) for i, (s, d, t) in enumerate(spec)])


CHAIN = [("a", "b", "x"), ("b", "c", "x")]
STAR = [("h", f"l{i}", "p") for i in range(4)]


def test_contrastive_difference_and_range():
    assert abs(calculate_contrastive_score(0.9, 0.2) - 0.7) < 1e-12
    assert calculate_contrastive_score(0.0, 1.0) == -1.0
    assert calculate_contrastive_score(0.5, 0.5) == 0.0


@pytest.mark.parametrize("a,b", [(-0.1, 0.5), (0.5, 1.5), (float("nan"), 0.1), ("x", 0.1)])
def test_contrastive_rejects_bad_input(a, b):
    with pytest.raises(InvalidScoreInputError):
        calculate_contrastive_score(a, b)


def test_normalize_contrastive():
    assert (normalize_contrastive(-1), normalize_contrastive(0), normalize_contrastive(1)) == (0.0, 0.5, 1.0)


def test_best_similarity_picks_best_pattern_regardless_of_identity():
    observed = mk([("p", "q", "x"), ("q", "r", "x")])
    bank = [mk(STAR), mk(CHAIN)]
    sim, index, match = find_best_pattern_match(observed, bank)
    assert sim == 1.0 and index == 1 and len(match.node_mapping) == 3
    assert find_best_attack_similarity(observed, bank) == 1.0
    assert find_best_benign_similarity(observed, [mk(STAR)]) < 0.3


def test_empty_bank_gives_zero():
    assert find_best_attack_similarity(mk(CHAIN), []) == 0.0
    assert find_best_pattern_match(mk(CHAIN), []) == (0.0, None, None)
