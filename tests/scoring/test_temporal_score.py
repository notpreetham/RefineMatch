"""Tests for src.scoring.temporal_score (hand-checkable)."""

from datetime import datetime, timedelta

import pytest

from src.core.exceptions import InvalidEventError
from src.core.models import EventRecord, MatchResult
from src.graph.graph_builder import build_temporal_graph
from src.scoring.temporal_score import (
    calculate_frequency_similarity, calculate_order_similarity, calculate_temporal_consistency)

T0 = datetime(2024, 1, 1)


def evs(spec, shift=0):
    return [EventRecord(T0 + timedelta(seconds=t + shift), s, d, ty) for t, s, d, ty in spec]


def tg(spec, shift=0):
    return build_temporal_graph(evs(spec, shift))


def match(mapping):
    return MatchResult(0.0, mapping, sorted(mapping), [], [], 0, 1.0)


def test_order_similarity_cases():
    ab = evs([(0, "a", "b", "A"), (1, "a", "b", "B")])
    ba = evs([(0, "a", "b", "B"), (1, "a", "b", "A")])
    assert calculate_order_similarity(ab, ab) == 1.0
    assert calculate_order_similarity(ab, ba) == 0.5            # LCS 1 -> 2*1/(2+2)
    assert calculate_order_similarity(ab, evs([(0, "a", "b", "Z")])) == 0.0
    assert calculate_order_similarity([], []) == 1.0
    assert calculate_order_similarity(ab, []) == 0.0


def test_order_similarity_ignores_repeats_identities_and_time_shift():
    ref = evs([(0, "a", "b", "A"), (5, "a", "b", "B")])
    obs = evs([(100, "x", "y", "A"), (101, "x", "y", "A"), (200, "p", "q", "B")])
    assert calculate_order_similarity(ref, obs) == 1.0


def test_order_similarity_uses_chronological_not_list_order():
    ref = evs([(0, "a", "b", "A"), (1, "a", "b", "B")])
    assert calculate_order_similarity(ref, list(reversed(ref))) == 1.0


def test_order_similarity_mixed_timezones_rejected():
    aware = [EventRecord(datetime(2024, 1, 1).astimezone(), "a", "b", "A")]
    with pytest.raises(InvalidEventError):
        calculate_order_similarity(evs([(0, "a", "b", "A")]) + aware, aware)


def test_frequency_similarity_basics():
    base = tg([(0, "a", "b", "x"), (1, "a", "b", "x"), (2, "b", "c", "y"), (3, "b", "c", "y")])
    assert calculate_frequency_similarity(base, base) == 1.0
    doubled = tg([(i, s, d, t) for i, (s, d, t) in enumerate([("a", "b", "x")] * 4 + [("b", "c", "y")] * 4)])
    assert calculate_frequency_similarity(base, doubled) == 1.0   # volume scale-invariant


def test_frequency_similarity_detects_shape_change_and_empties():
    base = tg([(i, "a", "b", "x") for i in range(5)] + [(9, "b", "c", "y")])
    skew = tg([(0, "a", "b", "x")] + [(i + 1, "b", "c", "y") for i in range(5)])
    # types: x 5/6,y 1/6 vs x 1/6,y 5/6 -> TV 2/3 -> sim 1/3; sorted edge-weight profiles are
    # identical ([5/6, 1/6]) -> sim 1; mean = 2/3. (Without a node mapping, which edge is heavy
    # is not visible; the event-type distribution catches it.)
    sim = calculate_frequency_similarity(base, skew)
    assert abs(sim - 2 / 3) < 1e-9
    empty = build_temporal_graph([])
    assert calculate_frequency_similarity(empty, empty) == 1.0
    assert calculate_frequency_similarity(base, empty) == 0.0


def test_temporal_consistency_hand_checked():
    ref = tg([(0, "a", "b", "x"), (10, "b", "c", "x")])
    same = tg([(0, "p", "q", "x"), (10, "q", "r", "x")], shift=500)
    swapped = tg([(10, "p", "q", "x"), (0, "q", "r", "x")])
    mapping = {"a": "p", "b": "q", "c": "r"}
    assert calculate_temporal_consistency(ref, same, match(mapping)) == 1.0
    assert calculate_temporal_consistency(ref, swapped, match(mapping)) == 0.0


def test_temporal_consistency_missing_and_neutral_evidence():
    ref = tg([(0, "a", "b", "x"), (10, "b", "c", "x")])
    obs = tg([(0, "p", "q", "x"), (10, "q", "r", "x")])
    assert calculate_temporal_consistency(ref, obs, match({})) == 0.0
    assert calculate_temporal_consistency(ref, obs, match({"a": "p", "b": "q"})) == 0.5  # one edge: neutral
    tie = tg([(0, "a", "b", "x"), (0, "b", "c", "x")])
    assert calculate_temporal_consistency(tie, obs, match({"a": "p", "b": "q", "c": "r"})) == 0.5


def test_temporal_consistency_partial_agreement():
    ref = tg([(0, "a", "b", "x"), (10, "b", "c", "x"), (20, "c", "d", "x")])
    obs = tg([(0, "p", "q", "x"), (20, "q", "r", "x"), (10, "r", "s", "x")])
    value = calculate_temporal_consistency(ref, obs, match({"a": "p", "b": "q", "c": "r", "d": "s"}))
    assert abs(value - 2 / 3) < 1e-12  # pairs (1,2) ok, (1,3) ok, (2,3) flipped
