"""1-to-1 Node assignment module using the Hungarian algorithm."""

from typing import Dict, List, Tuple
import numpy as np
from scipy.optimize import linear_sum_assignment

from src.core.models import MatchResult


def assign_nodes(
    reference_nodes: List[str],
    observed_nodes: List[str],
    candidates: Dict[str, List[str]],
) -> Tuple[Dict[str, str], float]:
    """Assign reference nodes to observed nodes using 1-to-1 optimal assignment.

    Constructs a cost matrix between reference and observed nodes where compatible
    candidate pairings have cost 0.0 and incompatible pairings carry a penalty cost.
    Solves the global minimum-weight bipartite matching via the Hungarian algorithm.

    Args:
        reference_nodes: List of node IDs from the reference pattern.
        observed_nodes: List of node IDs from the observed graph.
        candidates: Mapping from reference node ID to candidate observed node IDs.

    Returns:
        Tuple[Dict[str, str], float]:
            - mapping_dict: Optimal 1-to-1 mapping from reference node to observed node.
            - similarity_score: Fraction of reference nodes successfully matched (in [0.0, 1.0]).
    """
    if not reference_nodes or not observed_nodes:
        return {}, 0.0

    penalty = 1000.0
    cost_matrix = np.full((len(reference_nodes), len(observed_nodes)), penalty)

    ref_indices = {node: i for i, node in enumerate(reference_nodes)}
    obs_indices = {node: j for j, node in enumerate(observed_nodes)}

    for ref_node, cand_list in candidates.items():
        if ref_node in ref_indices:
            r = ref_indices[ref_node]
            for obs_node in cand_list:
                if obs_node in obs_indices:
                    c = obs_indices[obs_node]
                    cost_matrix[r, c] = 0.0

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    mapping_dict: Dict[str, str] = {}
    for r, c in zip(row_ind, col_ind):
        if cost_matrix[r, c] < penalty:
            mapping_dict[reference_nodes[r]] = observed_nodes[c]

    similarity_score = (
        len(mapping_dict) / len(reference_nodes) if reference_nodes else 0.0
    )

    return mapping_dict, similarity_score
