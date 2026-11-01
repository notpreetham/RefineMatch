"""Tests for src.refinement.ambiguity (hand-checkable star / path graphs)."""

import networkx as nx

from src.core.models import RefinementResult
from src.refinement.ambiguity import (
    calculate_ambiguity_score, find_ambiguous_classes, rank_ambiguous_classes)
from src.refinement.color_refinement import color_refine


def g(edges):
    graph = nx.DiGraph()
    for u, v in edges:
        graph.add_edge(u, v, edge_type="e", edge_types={"e": 1})
    return graph


def test_find_ambiguous_classes_star():
    graph = g([("hub", "x"), ("hub", "y"), ("hub", "z")])
    amb = find_ambiguous_classes(color_refine(graph))
    assert list(amb.values()) == [["x", "y", "z"]]


def test_no_ambiguity_on_path():
    graph = g([("a", "b"), ("b", "c"), ("c", "d")])
    assert find_ambiguous_classes(color_refine(graph)) == {}
    assert rank_ambiguous_classes(graph, color_refine(graph)) == []


def test_empty_refinement():
    assert find_ambiguous_classes(RefinementResult({}, {}, 0, True)) == {}


def test_score_hand_checked_values():
    graph = g([("hub", "x"), ("hub", "y")])
    # size 2 -> size_term 0.5; each leaf degree 1 -> d/(d+1) = 0.5; score = 0.5*(0.5+0.25)
    assert abs(calculate_ambiguity_score(graph, ["x", "y"]) - 0.375) < 1e-12


def test_score_zero_for_singletons_and_unknown_nodes():
    graph = g([("a", "b")])
    assert calculate_ambiguity_score(graph, ["a"]) == 0.0
    assert calculate_ambiguity_score(graph, []) == 0.0
    assert calculate_ambiguity_score(graph, ["ghost", "phantom"]) == 0.0


def test_larger_and_better_connected_classes_score_higher():
    graph = g([("hub", f"l{i}") for i in range(4)])
    graph.add_nodes_from(["iso1", "iso2"])
    leaves2, leaves4 = ["l0", "l1"], ["l0", "l1", "l2", "l3"]
    assert calculate_ambiguity_score(graph, leaves4) > calculate_ambiguity_score(graph, leaves2)
    assert calculate_ambiguity_score(graph, leaves2) > calculate_ambiguity_score(graph, ["iso1", "iso2"])


def test_score_bounded_and_rank_sorted_descending():
    graph = g([("hub", f"l{i}") for i in range(5)])
    graph.add_nodes_from(["iso1", "iso2"])
    ranked = rank_ambiguous_classes(graph, color_refine(graph))
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True) and len(ranked) == 2
    assert all(0.0 <= s < 1.0 for s in scores)


def test_ranking_is_deterministic_and_id_independent():
    a = g([("hub", "x"), ("hub", "y"), ("p", "q"), ("p", "r")])
    b = nx.relabel_nodes(a, {n: f"zz{i}" for i, n in enumerate(a.nodes)})
    ra = rank_ambiguous_classes(a, color_refine(a))
    rb = rank_ambiguous_classes(b, color_refine(b))
    assert ra == rb == rank_ambiguous_classes(a, color_refine(a))
