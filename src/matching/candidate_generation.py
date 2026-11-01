"""Candidate generation: which observed nodes could correspond to a reference node.

Two tiers, both identity-independent:

1. EXACT: observed nodes with the same color as the reference node.
2. RELAXED (only if ``allow_relaxed`` and the exact tier is too small, i.e. there
   are fewer exact observed nodes than reference nodes sharing that color, as
   happens when noise edges change some nodes' colors): observed nodes with
   the same ``node_type`` whose tagged out/in edge-label multiset has Jaccard
   overlap >= ``DEFAULT_RELAXED_MIN_PROFILE_OVERLAP`` with the reference node's.
   This tolerates both extra (noise) and missing (deleted) edges. Relaxed
candidates are ADDED to the exact ones; the assignment step prefers exact colors.
"""

from __future__ import annotations

from collections import Counter

import networkx as nx

from src.core.config import DEFAULT_RELAXED_MIN_PROFILE_OVERLAP
from src.core.exceptions import InvalidRefinementInputError
from src.graph.graph_utils import edge_label, node_type_of


def node_profile(graph: nx.DiGraph, node: str) -> tuple[str, Counter, Counter]:
    """``(node_type, out edge-label multiset, in edge-label multiset)``."""
    out = Counter(edge_label(a) for _, _, a in graph.out_edges(node, data=True))
    inc = Counter(edge_label(a) for _, _, a in graph.in_edges(node, data=True))
    return node_type_of(graph, node), out, inc


def profile_overlap(ref_profile: tuple, obs_profile: tuple) -> float:
    """Jaccard overlap of the tagged (direction, edge label) multisets; 0 on type mismatch."""
    if ref_profile[0] != obs_profile[0]:
        return 0.0
    def tagged(profile):
        merged = Counter()
        for direction, counter in (("out", profile[1]), ("in", profile[2])):
            merged.update({(direction, label): count for label, count in counter.items()})
        return merged
    a, b = tagged(ref_profile), tagged(obs_profile)
    union = sum((a | b).values())
    return 1.0 if union == 0 else sum((a & b).values()) / union


def generate_candidates(
    reference_graph: nx.DiGraph,
    observed_graph: nx.DiGraph,
    reference_colors: dict[str, str],
    observed_colors: dict[str, str],
    allow_relaxed: bool = True,
) -> dict[str, list[str]]:
    """Map every reference node to its (possibly empty) sorted candidate list."""
    if set(reference_colors) != set(reference_graph.nodes) or \
            set(observed_colors) != set(observed_graph.nodes):
        raise InvalidRefinementInputError("colors must cover exactly each graph's nodes")
    by_color: dict[str, list[str]] = {}
    for node in sorted(observed_graph.nodes):
        by_color.setdefault(observed_colors[node], []).append(node)
    observed_profiles = None
    reference_class_size = Counter(reference_colors.values())
    candidates: dict[str, list[str]] = {}
    for node in sorted(reference_graph.nodes):
        exact = by_color.get(reference_colors[node], [])
        if len(exact) >= reference_class_size[reference_colors[node]]:
            candidates[node] = list(exact)
        elif allow_relaxed:
            if observed_profiles is None:
                observed_profiles = {n: node_profile(observed_graph, n) for n in sorted(observed_graph.nodes)}
            ref_profile = node_profile(reference_graph, node)
            relaxed = {
                n for n, profile in observed_profiles.items()
                if profile_overlap(ref_profile, profile) >= DEFAULT_RELAXED_MIN_PROFILE_OVERLAP
            }
            candidates[node] = sorted(relaxed | set(exact))
        else:
            candidates[node] = list(exact)
    return candidates
