"""Baseline similarity methods. Every function maps ``(reference, observed)`` to [0, 1].

All baselines receive the SAME anonymised ``TemporalGraph`` inputs as RefineMatch.
SIMPLIFICATIONS (stated honestly):

* ``degree_statistical_similarity``: hand-built statistical features.
* ``color_refinement_only_similarity``: color-histogram overlap per 1-WL round;
  no node matching.
* ``graph2vec_style_similarity``: NOT Graph2Vec. It is the Weisfeiler-Lehman
  subtree-feature cosine similarity that Graph2Vec's features are based on,
  without the learned doc2vec embedding (no extra ML dependency).
* ``graph_edit_distance_similarity``: exact/timeout-limited NetworkX GED,
  small graphs only; returns ``None`` when skipped (too large or no result in time).
* ``cr_random_individualization_similarity``: our matcher with RANDOM instead of
  ambiguity-guided individualization (ablation of the AGIR selection rule).
* ``cr_only_matcher_similarity``: our matcher without any individualization.
"""

from __future__ import annotations

import math
from collections import Counter

import networkx as nx

from src.core.models import TemporalGraph
from src.graph.graph_utils import edge_label, node_type_of, ratio_compat
from src.matching.graph_matcher import MatcherConfig, match_graphs_detailed
from src.refinement.color_refinement import initialize_colors, refinement_history
from src.refinement.individualization import refine_fixed_rounds

WL_FEATURE_ROUNDS = 3


def _tv_sim(a: Counter, b: Counter) -> float:
    ta, tb = sum(a.values()), sum(b.values())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    keys = set(a) | set(b)
    return 1.0 - 0.5 * sum(abs(a[k] / ta - b[k] / tb) for k in keys)


def _empty_case(reference: TemporalGraph, observed: TemporalGraph) -> float | None:
    rn, on = reference.graph.number_of_nodes(), observed.graph.number_of_nodes()
    if rn == 0 or on == 0:
        return 1.0 if rn == on else 0.0
    return None


def degree_statistical_similarity(reference: TemporalGraph, observed: TemporalGraph) -> float:
    """Mean of size ratios and distribution overlaps of in/out degree and edge types."""
    early = _empty_case(reference, observed)
    if early is not None:
        return early
    rg, og = reference.graph, observed.graph
    parts = [ratio_compat(rg.number_of_nodes(), og.number_of_nodes()),
             ratio_compat(rg.number_of_edges(), og.number_of_edges())]
    for degree in ("in_degree", "out_degree"):
        parts.append(_tv_sim(Counter(d for _, d in getattr(rg, degree)()),
                             Counter(d for _, d in getattr(og, degree)())))
    parts.append(_tv_sim(Counter(edge_label(a) for _, _, a in rg.edges(data=True)),
                         Counter(edge_label(a) for _, _, a in og.edges(data=True))))
    return sum(parts) / len(parts)


def color_refinement_only_similarity(reference: TemporalGraph, observed: TemporalGraph) -> float:
    """Average over comparable 1-WL rounds of color-histogram overlap / max(|V|)."""
    early = _empty_case(reference, observed)
    if early is not None:
        return early
    hist_r, hist_o = refinement_history(reference.graph), refinement_history(observed.graph)
    size = max(reference.graph.number_of_nodes(), observed.graph.number_of_nodes())
    scores = []
    for cr, co in zip(hist_r, hist_o):
        overlap = sum((Counter(cr.values()) & Counter(co.values())).values())
        scores.append(overlap / size)
    return sum(scores) / len(scores)


def _wl_features(graph: nx.DiGraph) -> Counter:
    colors = initialize_colors(graph)
    features: Counter = Counter()
    for round_number in range(WL_FEATURE_ROUNDS + 1):
        features.update((round_number, c) for c in colors.values())
        if round_number < WL_FEATURE_ROUNDS:
            colors = refine_fixed_rounds(graph, colors, 1)
    return features


def graph2vec_style_similarity(reference: TemporalGraph, observed: TemporalGraph) -> float:
    """Cosine similarity of WL-subtree feature counts (Graph2Vec-style, not learned)."""
    early = _empty_case(reference, observed)
    if early is not None:
        return early
    fa, fb = _wl_features(reference.graph), _wl_features(observed.graph)
    dot = sum(fa[k] * fb[k] for k in fa.keys() & fb.keys())
    norm = math.sqrt(sum(v * v for v in fa.values())) * math.sqrt(sum(v * v for v in fb.values()))
    return dot / norm if norm else 0.0


def graph_edit_distance_similarity(
    reference: TemporalGraph, observed: TemporalGraph, max_nodes: int = 9, timeout: float = 1.0
) -> float | None:
    """``1 - GED / (|V1|+|V2|+|E1|+|E2|)``; ``None`` if skipped (size) or no result within ``timeout``."""
    early = _empty_case(reference, observed)
    if early is not None:
        return early
    rg, og = reference.graph, observed.graph
    if rg.number_of_nodes() > max_nodes or og.number_of_nodes() > max_nodes:
        return None
    distance = nx.graph_edit_distance(
        rg, og, timeout=timeout,
        node_match=lambda a, b: a.get("node_type") == b.get("node_type"),
        edge_match=lambda a, b: edge_label(a) == edge_label(b))
    if distance is None:
        return None
    worst = rg.number_of_nodes() + og.number_of_nodes() + rg.number_of_edges() + og.number_of_edges()
    return max(0.0, min(1.0, 1.0 - distance / worst))


def cr_random_individualization_similarity(
    reference: TemporalGraph, observed: TemporalGraph, seed: int = 0
) -> float:
    """Matcher similarity with random (not ambiguity-guided) individualization."""
    return match_graphs_detailed(reference, observed, MatcherConfig(selection="random", seed=seed)).match.similarity


def cr_only_matcher_similarity(reference: TemporalGraph, observed: TemporalGraph) -> float:
    """Matcher similarity with individualization disabled."""
    return match_graphs_detailed(reference, observed, MatcherConfig(selection="none")).match.similarity


BASELINES = {
    "degree_statistics": degree_statistical_similarity,
    "color_refinement_only": color_refinement_only_similarity,
    "graph2vec_style_wl": graph2vec_style_similarity,
    "graph_edit_distance": graph_edit_distance_similarity,
    "cr_random_individualization": cr_random_individualization_similarity,
}
