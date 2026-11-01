"""Tests for src.scoring.structural_score with hand-computed values."""

from datetime import datetime, timedelta

from src.core.models import EventRecord, MatchResult
from src.graph.graph_builder import build_temporal_graph
from src.scoring.structural_score import (
    calculate_edge_match_score, calculate_node_match_score, calculate_structural_similarity)

T0 = datetime(2024, 1, 1)


def mk(spec):
    return build_temporal_graph(
        [EventRecord(T0 + timedelta(seconds=i), s, d, t) for i, (s, d, t) in enumerate(spec)])


def match(mapping):
    return MatchResult(0.0, mapping, sorted(mapping), [], [], 0, 1.0)


PATH = [("a", "b", "e"), ("b", "c", "e")]
IDENT = {"a": "a", "b": "b", "c": "c"}


def test_perfect_identity_match_scores_one():
    ref = mk(PATH)
    assert calculate_structural_similarity(ref, mk(PATH), match(IDENT)) == 1.0


def test_partial_mapping_hand_computed():
    ref, obs = mk(PATH), mk(PATH)
    m = match({"a": "a", "b": "b"})  # c unmatched
    assert abs(calculate_node_match_score(ref, obs, m) - 2 / 3) < 1e-12
    # node: a(deg1 vs 1)=1, b(deg2 vs 2)=1 -> 2/3 ; edge: credit 1 / (2 + 0) = 0.5
    assert abs(calculate_edge_match_score(ref, obs, m) - 0.5) < 1e-12
    assert abs(calculate_structural_similarity(ref, obs, m) - (0.5 * 2 / 3 + 0.25)) < 1e-12


def test_extra_edge_inside_matched_region_is_penalised():
    ref, obs = mk(PATH), mk(PATH + [("a", "c", "e")])
    m = match(IDENT)
    assert abs(calculate_edge_match_score(ref, obs, m) - 2 / 3) < 1e-12  # 2 credits / (2 + 1 extra)


def test_noise_nodes_outside_matched_region_not_penalised_in_edge_score():
    ref, obs = mk(PATH), mk(PATH + [("n", "a", "dns")])
    assert calculate_edge_match_score(ref, obs, match(IDENT)) == 1.0


def test_edge_type_mismatch_earns_no_credit_and_partial_overlap_earns_half():
    ref = mk([("a", "b", "http")])
    assert calculate_edge_match_score(ref, mk([("a", "b", "dns")]), match({"a": "a", "b": "b"})) == 0.0
    obs = mk([("a", "b", "http"), ("a", "b", "dns")])
    assert calculate_edge_match_score(ref, obs, match({"a": "a", "b": "b"})) == 0.5


def test_direction_matters():
    ref, obs = mk([("a", "b", "e")]), mk([("y", "x", "e")])
    assert calculate_edge_match_score(ref, obs, match({"a": "x", "b": "y"})) == 0.0


def test_empty_graph_conventions_and_bounds():
    empty = build_temporal_graph([])
    assert calculate_structural_similarity(empty, empty, match({})) == 1.0
    assert calculate_structural_similarity(empty, mk(PATH), match({})) == 0.0
    assert calculate_structural_similarity(mk(PATH), empty, match({})) == 0.0
    assert calculate_structural_similarity(mk(PATH), mk(PATH), match({})) == 0.0
