"""Tests for src.refinement.individualization (AGIR)."""

import networkx as nx
import pytest

from src.core.exceptions import InvalidRefinementInputError
from src.refinement.color_refinement import color_refine, initialize_colors
from src.refinement.individualization import (
    agir_refine, agir_refine_with_trace, individualize_node, individualize_pair,
    refine_fixed_rounds, refine_from_colors, run_individualization)


def g(edges, extra_nodes=()):
    graph = nx.DiGraph()
    for u, v in edges:
        graph.add_edge(u, v, edge_type="e", edge_types={"e": 1})
    graph.add_nodes_from(extra_nodes)
    return graph


def cycle(n, prefix="c"):
    return g([(f"{prefix}{i}", f"{prefix}{(i + 1) % n}") for i in range(n)])


def star(k):
    return g([("hub", f"l{i}") for i in range(k)])


def n_classes(result):
    return len(result.color_classes)


def test_individualize_node_gives_unique_new_color_without_mutating_input():
    colors = initialize_colors(star(3))
    before = dict(colors)
    new = individualize_node(colors, "l0")
    assert colors == before
    assert new["l0"] not in colors.values() and new["l1"] == colors["l1"]


def test_individualize_node_is_deterministic_and_id_independent():
    a, b = star(3), nx.relabel_nodes(star(3), {"l0": "zzz", "hub": "q"})
    na = individualize_node(initialize_colors(a), "l0")["l0"]
    nb = individualize_node(initialize_colors(b), "zzz")["zzz"]
    assert na == nb == individualize_node(initialize_colors(a), "l0")["l0"]


def test_repeated_individualization_never_collides():
    colors = initialize_colors(star(3))
    once = individualize_node(colors, "l0")
    twice = individualize_node(once, "l1")
    assert len({twice["l0"], twice["l1"], twice["l2"]}) == 3


def test_individualize_unknown_node_rejected():
    with pytest.raises(InvalidRefinementInputError):
        individualize_node({"a": "c"}, "b")


def test_individualize_pair_shares_color_across_graphs():
    ca, cb = initialize_colors(star(3)), initialize_colors(star(3))
    na, nb = individualize_pair(ca, "l0", cb, "l2")
    assert na["l0"] == nb["l2"] and na["l0"] not in ca.values()


def test_refinement_after_individualization_c6_resolves_everything():
    graph = cycle(6)
    base = color_refine(graph)
    assert n_classes(base) == 1
    after = run_individualization(graph, base, "c0")
    assert n_classes(after) == 6 and after.stable
    assert after.iterations > base.iterations


def test_individualizing_one_star_leaf_splits_it_off_only():
    graph = star(3)
    after = run_individualization(graph, color_refine(graph), "l1")
    sizes = sorted(len(v) for v in after.color_classes.values())
    assert sizes == [1, 1, 2]


def test_agir_resolves_c6_with_one_individualization():
    result, trace = agir_refine_with_trace(cycle(6), max_individualizations=5)
    assert len(trace) == 1 and n_classes(result) == 6 and trace[0].refinement_gain == 5
    assert trace[0].ambiguous_nodes_before == 6 and trace[0].ambiguous_nodes_after == 0


def test_agir_budget_zero_equals_plain_refinement():
    graph = star(4)
    assert agir_refine(graph, 0).node_colors == color_refine(graph).node_colors


def test_agir_respects_budget_and_terminates():
    graph = star(6)
    for budget in (0, 1, 2, 3):
        result, trace = agir_refine_with_trace(graph, budget)
        assert len(trace) <= budget
        assert n_classes(result) == 2 + len(trace)  # each step peels one leaf off
    result, trace = agir_refine_with_trace(graph, 100)
    assert len(trace) == 5  # last two leaves are resolved by the 5th step; then nothing ambiguous
    assert not any(len(v) > 1 for v in result.color_classes.values())


def test_agir_does_not_touch_unambiguous_graph():
    graph = g([("a", "b"), ("b", "c")])
    result, trace = agir_refine_with_trace(graph, 5)
    assert trace == [] and result.node_colors == color_refine(graph).node_colors


def test_agir_ignores_low_value_isolated_twins_but_random_does_not():
    graph = g([], extra_nodes=["i1", "i2"])
    assert agir_refine_with_trace(graph, 3)[1] == []
    assert len(agir_refine_with_trace(graph, 3, selection="random", seed=1)[1]) >= 1


def test_agir_targets_most_ambiguous_class_first():
    graph = g([("hub", f"l{i}") for i in range(4)] + [("p", "q1"), ("p", "q2")])
    _, trace = agir_refine_with_trace(graph, 1)
    assert trace[0].class_size == 4 and trace[0].selected_node.startswith("l")


def test_agir_is_deterministic_and_seeded_random_is_reproducible():
    graph = star(5)
    assert agir_refine_with_trace(graph, 3)[0] == agir_refine_with_trace(graph, 3)[0]
    r1 = agir_refine_with_trace(graph, 2, "random", seed=7)
    r2 = agir_refine_with_trace(graph, 2, "random", seed=7)
    assert r1[0] == r2[0] and [s.selected_node for s in r1[1]] == [s.selected_node for s in r2[1]]


def test_agir_empty_graph_and_validation():
    result, trace = agir_refine_with_trace(nx.DiGraph(), 3)
    assert result.node_colors == {} and trace == []
    with pytest.raises(InvalidRefinementInputError):
        agir_refine_with_trace(star(2), -1)
    with pytest.raises(InvalidRefinementInputError):
        agir_refine_with_trace(star(2), 1, selection="bogus")


def test_refine_fixed_rounds_runs_exact_count_even_when_stable():
    graph = cycle(3)
    c0 = initialize_colors(graph)
    assert refine_fixed_rounds(graph, c0, 0) == c0
    assert refine_fixed_rounds(graph, c0, 2) != refine_fixed_rounds(graph, c0, 1)
    with pytest.raises(InvalidRefinementInputError):
        refine_fixed_rounds(graph, c0, -1)


def test_refine_from_colors_stable_flags():
    graph = cycle(3)
    _, rounds, stable = refine_from_colors(graph, initialize_colors(graph))
    assert stable and rounds == 1
    _, rounds, stable = refine_from_colors(g([("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]),
                                           initialize_colors(g([("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")])), 1)
    assert rounds == 1 and not stable
