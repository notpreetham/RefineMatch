"""Tests for candidate generation module."""

import networkx as nx

from src.matching.candidate_generation import generate_candidates


def test_generate_candidates_color_matching():
    # Create reference graph with 2 nodes: "ref_1" and "ref_2"
    reference_graph = nx.DiGraph()
    reference_graph.add_edge("ref_1", "ref_2")

    # Create observed graph with 3 nodes: "obs_1", "obs_2", and "obs_3"
    observed_graph = nx.DiGraph()
    observed_graph.add_edge("obs_1", "obs_2")
    observed_graph.add_edge("obs_2", "obs_3")

    # Colors:
    # "ref_1" has "color_A" -> matches "obs_1" and "obs_2"
    # "ref_2" has "color_B" -> "color_B" does not exist in observed graph
    reference_colors = {
        "ref_1": "color_A",
        "ref_2": "color_B",
    }
    observed_colors = {
        "obs_1": "color_A",
        "obs_2": "color_A",
        "obs_3": "color_C",
    }

    candidates = generate_candidates(
        observed_graph=observed_graph,
        reference_graph=reference_graph,
        observed_colors=observed_colors,
        reference_colors=reference_colors,
    )

    # ref_1 matches obs_1 and obs_2
    assert set(candidates["ref_1"]) == {"obs_1", "obs_2"}
    # ref_2 has color_B which doesn't exist in observed graph -> empty list
    assert candidates["ref_2"] == []


def test_generate_candidates_all_matching():
    reference_graph = nx.DiGraph()
    reference_graph.add_nodes_from(["r1", "r2"])

    observed_graph = nx.DiGraph()
    observed_graph.add_nodes_from(["o1", "o2"])

    ref_colors = {"r1": "color_X", "r2": "color_Y"}
    obs_colors = {"o1": "color_X", "o2": "color_Y"}

    candidates = generate_candidates(
        observed_graph=observed_graph,
        reference_graph=reference_graph,
        observed_colors=obs_colors,
        reference_colors=ref_colors,
    )

    assert candidates["r1"] == ["o1"]
    assert candidates["r2"] == ["o2"]


def test_generate_candidates_empty_graphs():
    reference_graph = nx.DiGraph()
    observed_graph = nx.DiGraph()

    candidates = generate_candidates(
        observed_graph=observed_graph,
        reference_graph=reference_graph,
        observed_colors={},
        reference_colors={},
    )

    assert candidates == {}
