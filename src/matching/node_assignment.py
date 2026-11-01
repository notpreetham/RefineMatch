"""One-to-one node assignment (Hungarian algorithm via SciPy).

Pair score = mean of: node-type match, degree compatibility, edge-type
histogram overlap (out and in), and (if colors are supplied) color match.
After a first pass, ``rounds - 1`` further passes add a neighborhood term:
the share of the reference node's neighbors whose current image is a neighbor
of the candidate. Pairs below ``min_score`` are dropped, so noise nodes stay
unmatched instead of being forced into bad pairs. Node IDs are never features.
A tiny identity-free tie-break (difference of relative first-seen position)
prefers temporally aligned pairs among otherwise equivalent (e.g. symmetric
twin) candidates; it can never override a real structural difference.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
from scipy.optimize import linear_sum_assignment

from src.core.config import DEFAULT_MIN_ASSIGNMENT_SCORE, TEMPORAL_TIEBREAK_WEIGHT
from src.graph.graph_utils import ratio_compat, relative_first_seen
from src.matching.candidate_generation import node_profile

_NEIGHBOR_WEIGHT = 0.4


def _overlap(a, b) -> float:
    total = max(sum(a.values()), sum(b.values()))
    return 1.0 if total == 0 else sum((a & b).values()) / total


def _local_score(ref, obs, u, v, ref_colors, obs_colors) -> float:
    r_type, r_out, r_in = node_profile(ref, u)
    o_type, o_out, o_in = node_profile(obs, v)
    parts = [
        1.0 if r_type == o_type else 0.0,
        0.5 * ratio_compat(ref.out_degree(u), obs.out_degree(v))
        + 0.5 * ratio_compat(ref.in_degree(u), obs.in_degree(v)),
        0.5 * _overlap(r_out, o_out) + 0.5 * _overlap(r_in, o_in),
    ]
    if ref_colors is not None and obs_colors is not None:
        parts.append(1.0 if ref_colors[u] == obs_colors[v] else 0.0)
    return sum(parts) / len(parts)


def _neighbor_score(ref, obs, u, v, assignment) -> float:
    total = ref.out_degree(u) + ref.in_degree(u)
    if total == 0:
        return 1.0
    hits = sum(1 for w in ref.successors(u) if assignment.get(w) in obs.successors(v))
    hits += sum(1 for w in ref.predecessors(u) if assignment.get(w) in obs.predecessors(v))
    return hits / total


def assign_nodes(
    candidate_map: dict[str, list[str]],
    reference_graph: nx.DiGraph,
    observed_graph: nx.DiGraph,
    reference_colors: dict[str, str] | None = None,
    observed_colors: dict[str, str] | None = None,
    min_score: float = DEFAULT_MIN_ASSIGNMENT_SCORE,
    rounds: int = 3,
) -> dict[str, str]:
    """Return a one-to-one ``{reference_node: observed_node}`` mapping."""
    rows = sorted(u for u, c in candidate_map.items() if c)
    cols = sorted({v for u in rows for v in candidate_map[u]})
    if not rows or not cols:
        return {}
    local = np.full((len(rows), len(cols)), -1.0)
    col_index = {v: j for j, v in enumerate(cols)}
    ref_pos, obs_pos = relative_first_seen(reference_graph), relative_first_seen(observed_graph)
    for i, u in enumerate(rows):
        for v in candidate_map[u]:
            local[i, col_index[v]] = _local_score(
                reference_graph, observed_graph, u, v, reference_colors, observed_colors
            ) - TEMPORAL_TIEBREAK_WEIGHT * abs(ref_pos[u] - obs_pos[v])
    assignment: dict[str, str] = {}
    for pass_number in range(max(1, rounds)):
        score = local.copy()
        if pass_number > 0:
            for i, u in enumerate(rows):
                for v in candidate_map[u]:
                    j = col_index[v]
                    nb = _neighbor_score(reference_graph, observed_graph, u, v, assignment)
                    score[i, j] = (1 - _NEIGHBOR_WEIGHT) * local[i, j] + _NEIGHBOR_WEIGHT * nb
        row_ind, col_ind = linear_sum_assignment(-score)
        assignment = {
            rows[i]: cols[j]
            for i, j in zip(row_ind, col_ind)
            if score[i, j] >= min_score and cols[j] in candidate_map[rows[i]]
        }
    return assignment
