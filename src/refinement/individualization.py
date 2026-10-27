"""AGIR selective individualization module for resolving ambiguous color classes."""

from typing import Dict, List, Optional
import networkx as nx

from src.core.config import DEFAULT_IDENTITY_PREFIX, DEFAULT_MAX_INDIVIDUALIZATIONS
from src.core.models import RefinementResult
from src.refinement.ambiguity import rank_ambiguous_classes


def individualize_node(colors: Dict[str, str], node_id: str) -> Dict[str, str]:
    """Assign a unique individualized color to a specific node."""
    new_colors = dict(colors)
    if node_id in new_colors:
        new_colors[node_id] = f"{new_colors[node_id]}_indiv_{node_id}"
    return new_colors


def individualize_graph(
    graph: nx.DiGraph, current_refinement: RefinementResult
) -> RefinementResult:
    """Break ties by individualizing a single node from the highest-priority ambiguous color class.
    
    Returns a new RefinementResult with stable=False to signal to the refinement
    loop that re-refinement is required.
    """
    ranked_ambiguities = rank_ambiguous_classes(graph, current_refinement)

    # If there are no ambiguous/tied classes, return the refinement as-is
    if not ranked_ambiguities:
        return current_refinement

    # Select the top-ranked tied color class
    top_color, _ = ranked_ambiguities[0]
    tied_nodes = current_refinement.color_classes[top_color]

    # Select one node from the tied class (deterministic choice)
    selected_node = tied_nodes[0]

    # Modify its color to be unique
    updated_node_colors = individualize_node(current_refinement.node_colors, selected_node)

    # Reconstruct color classes with the newly individualized node
    updated_color_classes: Dict[str, List[str]] = {}
    for node, color in updated_node_colors.items():
        updated_color_classes.setdefault(color, []).append(node)

    return RefinementResult(
        node_colors=updated_node_colors,
        color_classes=updated_color_classes,
        iterations=current_refinement.iterations,
        stable=False,
    )