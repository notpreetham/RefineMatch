"""Tests for src.matching.node_assignment."""

import networkx as nx

from src.matching.candidate_generation import generate_candidates
from src.matching.node_assignment import assign_nodes
from src.refinement.color_refinement import color_refine


def g(edges):
    graph = nx.DiGraph()
    for u, v, t in edges:
        graph.add_edge(u, v, edge_type=t, edge_types={t: 1})
    return graph


def run(ref, obs, **kw):
    rc, oc = color_refine(ref).node_colors, color_refine(obs).node_colors
    return assign_nodes(generate_candidates(ref, obs, rc, oc), ref, obs, rc, oc, **kw)


def test_recovers_unique_mapping_on_renamed_chain():
    ref = g([("a", "b", "x"), ("b", "c", "y"), ("c", "d", "x")])
    obs = g([("w", "x", "x"), ("x", "y", "y"), ("y", "z", "x")])
    assert run(ref, obs) == {"a": "w", "b": "x", "c": "y", "d": "z"}


def test_assignment_is_one_to_one_even_with_symmetric_candidates():
    ref = g([("h", "l1", "e"), ("h", "l2", "e"), ("h", "l3", "e")])
    obs = g([("H", "A", "e"), ("H", "B", "e"), ("H", "C", "e")])
    mapping = run(ref, obs)
    assert mapping["h"] == "H" and sorted(mapping.values()) == ["A", "B", "C", "H"]
    assert len(set(mapping.values())) == len(mapping)


def test_only_candidates_are_assigned_and_empty_input_is_empty():
    ref = g([("a", "b", "x")])
    assert assign_nodes({"a": [], "b": []}, ref, g([("p", "q", "x")])) == {}
    assert assign_nodes({}, ref, ref) == {}
    mapping = assign_nodes({"a": ["p"], "b": ["p"]}, ref, g([("p", "q", "x")]))
    assert list(mapping.values()).count("p") <= 1


def test_min_score_drops_poor_pairs():
    ref = g([("a", "b", "x")])
    obs = g([("p", "q", "x")])
    candidate_map = {"a": ["q"], "b": ["p"]}  # deliberately reversed roles
    assert assign_nodes(candidate_map, ref, obs, min_score=0.95) == {}


def test_deterministic():
    ref = g([("h", "l1", "e"), ("h", "l2", "e")])
    obs = g([("H", "A", "e"), ("H", "B", "e")])
    assert run(ref, obs) == run(ref, obs)
