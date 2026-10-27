"""Tests for AGIR individualization logic."""

import networkx as nx

from src.core.models import RefinementResult
from src.refinement.individualization import individualize_graph, individualize_node


def test_individualize_graph_breaks_tie():
    # Build a 4-node directed cycle graph
    graph = nx.cycle_graph(4, create_using=nx.DiGraph)

    # Dummy RefinementResult where nodes "0" and "1" share "color_A" (tied class)
    initial_refinement = RefinementResult(
        node_colors={"0": "color_A", "1": "color_A", "2": "color_B", "3": "color_C"},
        color_classes={"color_A": ["0", "1"], "color_B": ["2"], "color_C": ["3"]},
        iterations=2,
        stable=True,
    )

    updated_refinement = individualize_graph(graph, initial_refinement)

    # Verify stable flag is set to False to notify 1-WL coloring loop
    assert updated_refinement.stable is False

    # Verify that the tie was broken between "0" and "1"
    assert updated_refinement.node_colors["0"] != updated_refinement.node_colors["1"]

    # Verify color_A now has one less member and the individualized color exists
    assert len(updated_refinement.color_classes["color_A"]) == 1
    assert any(col.startswith("color_A_indiv") for col in updated_refinement.color_classes)


def test_individualize_graph_no_ties():
    graph = nx.cycle_graph(3, create_using=nx.DiGraph)

    # RefinementResult with all unique colors (no ties)
    stable_refinement = RefinementResult(
        node_colors={"0": "color_A", "1": "color_B", "2": "color_C"},
        color_classes={"color_A": ["0"], "color_B": ["1"], "color_C": ["2"]},
        iterations=1,
        stable=True,
    )

    result = individualize_graph(graph, stable_refinement)

    # If there are no ties, refinement remains stable and unchanged
    assert result.stable is True
    assert result.node_colors == stable_refinement.node_colors
    assert result.color_classes == stable_refinement.color_classes