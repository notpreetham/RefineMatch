"""Tests for src.matching.candidate_generation."""

import networkx as nx
import pytest

from src.core.exceptions import InvalidRefinementInputError
from src.matching.candidate_generation import generate_candidates
from src.refinement.color_refinement import color_refine


def g(edges, types=None):
    graph = nx.DiGraph()
    for u, v, t in edges:
        graph.add_edge(u, v, edge_type=t, edge_types={t: 1})
    for n in graph.nodes:
        graph.nodes[n]["node_type"] = (types or {}).get(n, "host")
    return graph


def cands(ref, obs, relaxed=True):
    return generate_candidates(ref, obs, color_refine(ref).node_colors, color_refine(obs).node_colors, relaxed)


def test_exact_color_candidates_for_renamed_graph():
    ref = g([("a", "b", "x"), ("b", "c", "y")])
    obs = g([("p", "q", "x"), ("q", "r", "y")])
    assert cands(ref, obs) == {"a": ["p"], "b": ["q"], "c": ["r"]}


def test_symmetric_nodes_yield_multiple_candidates():
    ref = g([("h", "l1", "e"), ("h", "l2", "e")])
    obs = g([("H", "L1", "e"), ("H", "L2", "e")])
    result = cands(ref, obs)
    assert result["l1"] == ["L1", "L2"] and result["h"] == ["H"]


def test_structurally_incompatible_nodes_are_not_candidates():
    ref = g([("a", "b", "x")])
    obs = g([("p", "q", "other")])
    assert cands(ref, obs, relaxed=False) == {"a": [], "b": []}
    assert cands(ref, obs) == {"a": [], "b": []}  # relaxed also rejects edge-type mismatch


def test_node_type_gates_candidates():
    ref = g([("a", "b", "x")], {"a": "client"})
    obs = g([("p", "q", "x")], {"p": "server"})
    assert cands(ref, obs)["a"] == []


def test_relaxed_fallback_tolerates_extra_noise_edges():
    ref = g([("a", "b", "x")])
    obs = g([("p", "q", "x"), ("n", "p", "dns")])  # p gained an extra incoming edge
    strict = cands(ref, obs, relaxed=False)
    relaxed = cands(ref, obs)
    assert strict["a"] == [] and relaxed["a"] == ["p"]


def test_validation_and_empty():
    ref = g([("a", "b", "x")])
    with pytest.raises(InvalidRefinementInputError):
        generate_candidates(ref, ref, {"a": "c"}, color_refine(ref).node_colors)
    empty = nx.DiGraph()
    assert generate_candidates(ref, empty, color_refine(ref).node_colors, {}) == {"a": [], "b": []}


def test_relaxed_fallback_tolerates_missing_edges_too():
    ref = g([("w", "a1", "rpc"), ("w", "a2", "rpc"), ("c", "w", "http")])
    obs = g([("W", "A2", "rpc"), ("C", "W", "http")])  # one rpc edge deleted
    result = cands(ref, obs)
    assert result["w"] == ["W"] and result["c"] == ["C"]


def test_unrelated_profile_stays_excluded_by_overlap_rule():
    ref = g([("a", "b", "x"), ("a", "c", "x"), ("a", "d", "x")])
    obs = g([("p", "q", "y"), ("p", "r", "y")])
    assert cands(ref, obs)["a"] == []


def test_relaxation_is_added_when_exact_supply_is_too_small():
    # three identical sources in the reference, but noise changed two of them in the observation
    ref = g([("s1", "t", "x"), ("s2", "t", "x"), ("s3", "t", "x")])
    obs = g([("a1", "T", "x"), ("a2", "T", "x"), ("a3", "T", "x"), ("n", "a2", "dns"), ("a3", "m", "ntp")])
    from src.refinement.color_refinement import initialize_colors
    rc, oc = initialize_colors(ref), initialize_colors(obs)       # depth-0 colors
    strict = generate_candidates(ref, obs, rc, oc, allow_relaxed=False)
    relaxed = generate_candidates(ref, obs, rc, oc)
    assert strict["s1"] == ["a1"]                       # only one exact counterpart
    assert set(relaxed["s1"]) == {"a1", "a2", "a3"}     # supply-aware relaxation adds the noisy ones
