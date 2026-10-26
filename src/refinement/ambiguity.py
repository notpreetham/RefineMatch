"""Ambiguity detection and scoring for Color Refinement results."""

from typing import Dict, List, Tuple
import networkx as nx
from src.core.models import RefinementResult


def find_ambiguous_classes(refinement: RefinementResult) -> Dict[str, List[str]]:
    """Return all color classes containing more than one node."""
    return {
        color: nodes
        for color, nodes in refinement.color_classes.items()
        if len(nodes) > 1
    }


def calculate_ambiguity_score(graph: nx.DiGraph, color_class: List[str]) -> float:
    """Calculate an ambiguity priority score for a group of tied nodes.
    
    Higher score means resolving this class first is more informative
    (e.g., higher degree nodes propagate more structural information).
    """
    if not color_class:
        return 0.0

    # Base score: class size weighted by average total degree
    avg_degree = sum(dict(graph.degree(color_class)).values()) / len(color_class)
    return float(len(color_class) * avg_degree)


def rank_ambiguous_classes(
    graph: nx.DiGraph, refinement: RefinementResult
) -> List[Tuple[str, float]]:
    """Rank ambiguous color classes in descending order of priority."""
    ambiguous = find_ambiguous_classes(refinement)
    scored = [
        (color, calculate_ambiguity_score(graph, nodes))
        for color, nodes in ambiguous.items()
    ]
    return sorted(scored, key=lambda item: item[1], reverse=True)