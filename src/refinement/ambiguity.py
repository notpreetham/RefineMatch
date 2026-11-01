"""Ambiguity detection after Color Refinement.

A color class with more than one node means 1-WL could not tell those nodes
apart. That is either genuine symmetry (automorphic nodes, harmless) or a 1-WL
blind spot (not harmless). Either way matching is ambiguous there, so we rank
classes by how much resolving them is worth.

Ambiguity score (HEURISTIC; documented, not experimentally validated - the
AGIR-vs-random-vs-none experiment is how it is evaluated)::

    size_term    = 1 - 1/|class|                       in [0, 1), 0 for singletons
    connectivity = mean over nodes of d/(d+1), d = in+out degree
    score        = size_term * (0.5 + 0.5 * connectivity)

Bigger classes and better-connected nodes score higher; isolated twins carry
no structural information, so they are halved. Node IDs and roles are not used.
"""

from __future__ import annotations

import networkx as nx

from src.core.models import RefinementResult


def find_ambiguous_classes(refinement: RefinementResult) -> dict[str, list[str]]:
    """Return ``{color: nodes}`` for every color class with more than one node."""
    return {
        color: list(nodes)
        for color, nodes in refinement.color_classes.items()
        if len(nodes) > 1
    }


def calculate_ambiguity_score(graph: nx.DiGraph, color_class: list[str]) -> float:
    """Ambiguity score in ``[0, 1)`` for one class (see module docstring)."""
    nodes = [node for node in color_class if node in graph]
    if len(nodes) < 2:
        return 0.0
    size_term = 1.0 - 1.0 / len(nodes)
    degrees = [graph.in_degree(node) + graph.out_degree(node) for node in nodes]
    connectivity = sum(d / (d + 1.0) for d in degrees) / len(degrees)
    return size_term * (0.5 + 0.5 * connectivity)


def rank_ambiguous_classes(
    graph: nx.DiGraph, refinement: RefinementResult
) -> list[tuple[str, float]]:
    """Ambiguous classes as ``(color, score)``, highest score first.

    Ties are broken by color label (identity-independent, deterministic).
    """
    ranked = [
        (color, calculate_ambiguity_score(graph, nodes))
        for color, nodes in find_ambiguous_classes(refinement).items()
    ]
    return sorted(ranked, key=lambda item: (-item[1], item[0]))
