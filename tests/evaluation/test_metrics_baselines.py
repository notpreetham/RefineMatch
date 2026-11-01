"""Tests for src.evaluation.metrics and src.evaluation.baselines (hand-computed values)."""

import pytest

from src.core.exceptions import InvalidScoreInputError
from src.evaluation.baselines import (
    BASELINES, color_refinement_only_similarity, cr_only_matcher_similarity,
    cr_random_individualization_similarity, degree_statistical_similarity,
    graph2vec_style_similarity, graph_edit_distance_similarity)
from src.evaluation.metrics import (
    calculate_robustness_curve, calculate_runtime, classification_report, confusion_counts,
    f1_score, false_negative_rate, false_positive_rate, matching_accuracy, measure_peak_memory,
    precision, recall)
from src.graph.anonymizer import anonymize_graph
from src.graph.graph_builder import build_temporal_graph
from src.ingestion.synthetic_generator import generate_synthetic_graph
from src.core.models import EventRecord
from datetime import datetime, timedelta


def test_metric_hand_computed_values():
    # tp=6, fp=2, fn=4, tn=8
    assert precision(6, 2) == 0.75 and recall(6, 4) == 0.6
    assert abs(f1_score(6, 2, 4) - 2 * 0.75 * 0.6 / 1.35) < 1e-12
    assert false_positive_rate(2, 8) == 0.2 and false_negative_rate(4, 6) == 0.4


def test_metric_zero_division_and_validation():
    assert precision(0, 0) == recall(0, 0) == f1_score(0, 0, 0) == 0.0
    assert false_positive_rate(0, 0) == false_negative_rate(0, 0) == 0.0
    assert f1_score(0, 3, 3) == 0.0 and f1_score(5, 0, 0) == 1.0
    for bad in (-1, 1.5, True, "3"):
        with pytest.raises(InvalidScoreInputError):
            precision(bad, 1)


def test_confusion_counts_and_report():
    y_true = [True, True, True, False, False, False, False]
    y_pred = [True, True, False, True, False, False, False]
    assert confusion_counts(y_true, y_pred) == {"tp": 2, "fp": 1, "tn": 3, "fn": 1}
    report = classification_report(y_true, y_pred)
    assert report["precision"] == 2 / 3 and report["recall"] == 2 / 3 and report["fpr"] == 0.25
    with pytest.raises(InvalidScoreInputError):
        confusion_counts([True], [True, False])


def test_runtime_memory_accuracy_and_curve():
    value, seconds = calculate_runtime(sum, [1, 2, 3])
    assert value == 6 and seconds >= 0
    result, peak = measure_peak_memory(lambda: [0] * 100000)
    assert len(result) == 100000 and peak > 100000
    assert matching_accuracy({"a": "x", "b": "y"}, {"a": "x", "b": "z"}) == 0.5
    assert matching_accuracy({}, {}) == 1.0 and matching_accuracy({}, {"a": "x"}) == 0.0
    curve = calculate_robustness_curve({0.2: [0.5, 1.0], 0.1: [1.0, 1.0]})
    assert [p["level"] for p in curve] == [0.1, 0.2] and curve[1]["mean"] == 0.75 and curve[1]["min"] == 0.5
    with pytest.raises(InvalidScoreInputError):
        calculate_robustness_curve({0.1: []})


T0 = datetime(2024, 1, 1)


def mk(spec):
    return build_temporal_graph([EventRecord(T0 + timedelta(seconds=i), s, d, t) for i, (s, d, t) in enumerate(spec)])


def test_baselines_identical_graphs_score_one_and_are_identity_independent():
    a = anonymize_graph(generate_synthetic_graph("multi_server_application", 1))
    b = anonymize_graph(generate_synthetic_graph("multi_server_application", 2))
    for name, fn in BASELINES.items():
        assert abs(fn(a, b) - 1.0) < 1e-9, name
    assert cr_only_matcher_similarity(a, b) == 1.0


def test_baselines_in_unit_interval_and_discriminate_different_structures():
    ref = anonymize_graph(generate_synthetic_graph("scanning_like", 1))
    other = anonymize_graph(generate_synthetic_graph("normal_client_server", 1))
    for name, fn in BASELINES.items():
        value = fn(ref, other)
        assert value is None or 0.0 <= value < 0.9, name
    assert degree_statistical_similarity(ref, other) < degree_statistical_similarity(ref, ref)


def test_baseline_empty_conventions_and_ged_skip():
    empty = build_temporal_graph([])
    big = anonymize_graph(generate_synthetic_graph("scanning_like", 1))
    for fn in (degree_statistical_similarity, color_refinement_only_similarity, graph2vec_style_similarity,
               graph_edit_distance_similarity):
        assert fn(empty, empty) == 1.0 and fn(empty, big) == 0.0
    assert graph_edit_distance_similarity(big, big, max_nodes=3) is None


def test_ged_hand_checked():
    assert graph_edit_distance_similarity(mk([("a", "b", "x")]), mk([("p", "q", "x")])) == 1.0
    # one edge relabelled: GED = 1 substitution; denominator 2+2+1+1 = 6
    assert abs(graph_edit_distance_similarity(mk([("a", "b", "x")]), mk([("p", "q", "y")])) - (1 - 1 / 6)) < 1e-9


def test_random_individualization_baseline_is_seed_reproducible():
    a = anonymize_graph(generate_synthetic_graph("scanning_like", 1))
    b = anonymize_graph(generate_synthetic_graph("scanning_like", 2))
    assert cr_random_individualization_similarity(a, b, 4) == cr_random_individualization_similarity(a, b, 4)
