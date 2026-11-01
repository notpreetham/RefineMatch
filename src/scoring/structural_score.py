"""Structural similarity of a reference and an observed graph under a match.

Definitions (all in ``[0, 1]``; identity-independent):

* node score  = sum over reference nodes of compat(u, match(u)) / |V_ref|, with
  compat = 0.5*[same node_type] + 0.5*min/max total-degree ratio; unmatched
  reference nodes contribute 0.
* edge score  = sum over reference edges (u,w) whose images are joined by an
  observed edge of Jaccard(edge-type sets) / (|E_ref| + extra), where ``extra``
  counts observed edges between matched observed nodes that are not images of
  reference edges (penalising added edges inside the matched region; noise
  nodes outside it are not penalised).
* similarity  = 0.5 * node score + 0.5 * edge score.

Empty-graph conventions: an empty reference matches only an empty observed
graph (1.0), otherwise 0.0.
"""

from __future__ import annotations

from src.core.models import MatchResult, TemporalGraph
from src.graph.graph_utils import edge_label, label_jaccard, node_type_of, ratio_compat


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _total_degree(graph, node: str) -> int:
    return graph.in_degree(node) + graph.out_degree(node)


def calculate_node_match_score(
    reference: TemporalGraph, observed: TemporalGraph, match: MatchResult
) -> float:
    """Average node compatibility over reference nodes (unmatched count as 0)."""
    rg, og = reference.graph, observed.graph
    if rg.number_of_nodes() == 0:
        return 1.0 if og.number_of_nodes() == 0 else 0.0
    total = 0.0
    for u, v in match.node_mapping.items():
        if u in rg and v in og:
            total += 0.5 * (node_type_of(rg, u) == node_type_of(og, v)) \
                + 0.5 * ratio_compat(_total_degree(rg, u), _total_degree(og, v))
    return _clip(total / rg.number_of_nodes())


def calculate_edge_match_score(
    reference: TemporalGraph, observed: TemporalGraph, match: MatchResult
) -> float:
    """Edge preservation score with a penalty for extra edges (see module doc)."""
    rg, og = reference.graph, observed.graph
    mapping = {u: v for u, v in match.node_mapping.items() if u in rg and v in og}
    credit, image_edges = 0.0, set()
    for u, w, attrs in rg.edges(data=True):
        if u in mapping and w in mapping and og.has_edge(mapping[u], mapping[w]):
            image_edges.add((mapping[u], mapping[w]))
            credit += label_jaccard(edge_label(attrs), edge_label(og.edges[mapping[u], mapping[w]]))
    images = set(mapping.values())
    extra = sum(1 for a, b in og.subgraph(images).edges if (a, b) not in image_edges)
    denominator = rg.number_of_edges() + extra
    if denominator == 0:
        return 1.0
    return _clip(credit / denominator)


def calculate_structural_similarity(
    reference: TemporalGraph, observed: TemporalGraph, match: MatchResult
) -> float:
    """Combined structural similarity in ``[0, 1]``."""
    if reference.graph.number_of_nodes() == 0:
        return 1.0 if observed.graph.number_of_nodes() == 0 else 0.0
    node = calculate_node_match_score(reference, observed, match)
    edge = calculate_edge_match_score(reference, observed, match)
    return _clip(0.5 * node + 0.5 * edge)
