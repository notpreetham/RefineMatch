"""Candidate generation module for matching observed graphs against reference patterns."""

from typing import Dict, List
import networkx as nx

from src.core.models import MatchResult


def generate_candidates(
    observed_graph: nx.DiGraph,
    reference_graph: nx.DiGraph,
    observed_colors: Dict[str, str],
    reference_colors: Dict[str, str],
) -> Dict[str, List[str]]:
    """Generate candidate matching nodes between reference and observed graphs.

    A node in observed_graph is a valid candidate for a node in reference_graph
    if and only if they share the exact same final color from refinement.

    Args:
        observed_graph: Directed graph representing observed telemetry.
        reference_graph: Directed graph representing a reference pattern.
        observed_colors: Node-to-color mapping for the observed graph.
        reference_colors: Node-to-color mapping for the reference graph.

    Returns:
        Dict[str, List[str]]: Mapping where each key is a node ID from reference_graph,
        and value is a list of node IDs from observed_graph sharing the same color.
        Reference nodes whose color is not found in observed_graph receive an empty list.
    """
    # Group observed nodes by their color for efficient lookup
    color_to_observed_nodes: Dict[str, List[str]] = {}
    for node in observed_graph.nodes:
        color = observed_colors.get(node)
        if color is not None:
            color_to_observed_nodes.setdefault(color, []).append(node)

    candidates: Dict[str, List[str]] = {}
    for ref_node in reference_graph.nodes:
        ref_color = reference_colors.get(ref_node)
        if ref_color is not None and ref_color in color_to_observed_nodes:
            candidates[ref_node] = list(color_to_observed_nodes[ref_color])
        else:
            candidates[ref_node] = []

    return candidates
