"""Color Refinement (1-dimensional Weisfeiler-Leman) for directed graphs.

Algorithm
---------
Round 0 (``initialize_colors``): each node gets a color derived ONLY from
structure and typing::

    color0(v) = H("init", node_type(v), in_degree(v), out_degree(v),
                  histogram of outgoing edge labels, histogram of incoming edge labels)

Round k+1 (``refine_once``)::

    color_{k+1}(v) = H("wl", color_k(v),
                       sorted multiset of ("out", edge_label, color_k(w))  for each edge v->w,
                       and                ("in",  edge_label, color_k(u))  for each edge u->v)

where ``edge_label`` is the sorted set of event types on that edge (the key set
of the ``edge_types`` attribute; falls back to ``edge_type``). ``H`` is
SHA-256 over a canonical JSON encoding, truncated to
``COLOR_DIGEST_HEX_LENGTH`` hex characters. Python's randomized ``hash()`` is
never used, so labels are identical across processes, runs and machines.

What is (and is not) a feature
------------------------------
Used: ``node_type``, in/out degree (distinct neighbours), edge-type labels,
direction. NOT used: node IDs, hostnames/IPs, ``original_id``, ``role``,
insertion order, edge ``weight`` (frequency), timestamps, bytes, durations.
Excluding weights means frequency changes do not alter structure; frequency is
scored separately by the temporal/frequency modules. If roles should affect
refinement, encode them into ``node_type`` with ``assign_node_attributes``.

Cross-graph comparability (important for Members 2 and 3)
---------------------------------------------------------
Colors are CONTENT-ADDRESSED: a color is a function of the node's unfolded
neighbourhood, not of a per-graph counter. Hence, two graphs can be compared
directly, WITHOUT joint refinement, as long as colors from the SAME ROUND are
compared:

* Equal color at round k  <=>  identical depth-k unfolding trees (up to a
  negligible 128-bit hash-collision probability).
* ``color_refine`` stops at stability, and 1-WL-equivalent graphs always
  stabilise at the same round, so final colors of equivalent graphs are
  comparable. If two results have different ``iterations`` the graphs are
  distinguishable by 1-WL, and their labels necessarily differ.
* To compare an observed graph that has extra/noisy nodes with a reference
  pattern, use a FIXED shallow depth via :func:`refinement_history` and compare
  ``history[k]`` from both graphs; deep colors encode the whole reachable
  neighbourhood, so extra nodes change them.
* Never compare colors from different rounds.

Stable coloring is NOT an isomorphism test
------------------------------------------
Identical color histograms are *necessary* for isomorphism, not *sufficient*.
Example: one directed 6-cycle and two disjoint directed 3-cycles get identical
colorings but are not isomorphic. Individualization (Member 2's AGIR) exists to
break such ties. :func:`wl_equivalent` reports 1-WL indistinguishability only.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter

import networkx as nx

from src.core.config import (
    COLOR_DIGEST_HEX_LENGTH,
    DEFAULT_INITIAL_REFINEMENT_ITERATIONS,
    DEFAULT_MAX_REFINEMENT_ITERATIONS,
    DEFAULT_NODE_TYPE,
)
from src.core.exceptions import InvalidRefinementInputError
from src.core.models import RefinementResult, TemporalGraph


# --------------------------------------------------------------------------- #
# Canonical encoding
# --------------------------------------------------------------------------- #

def _digest(payload: list) -> str:
    """Deterministic color label for a JSON-serialisable payload."""
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:COLOR_DIGEST_HEX_LENGTH]


def _edge_label(attributes: dict) -> str:
    """Canonical JSON string for an edge's type label (identity-free)."""
    types = attributes.get("edge_types")
    if types:
        labels = sorted(str(t) for t in types)
    elif attributes.get("edge_type") is not None:
        labels = [str(attributes["edge_type"])]
    else:
        labels = []
    return json.dumps(labels, separators=(",", ":"), ensure_ascii=True)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def _validate_graph(graph: nx.DiGraph | TemporalGraph | Any) -> nx.DiGraph:
    if isinstance(graph, TemporalGraph) or (hasattr(graph, "graph") and not isinstance(graph, nx.DiGraph)):
        graph = graph.graph
    if not isinstance(graph, nx.DiGraph) or graph.is_multigraph():
        raise InvalidRefinementInputError(
            "graph must be a networkx.DiGraph (undirected graphs and multigraphs are unsupported)"
        )
    for node in graph.nodes:
        if not isinstance(node, str):
            raise InvalidRefinementInputError(f"node IDs must be strings, got {node!r}")
    return graph


def _validate_colors(graph: nx.DiGraph, colors: dict[str, str]) -> None:
    if not isinstance(colors, dict):
        raise InvalidRefinementInputError("colors must be a dict[str, str]")
    graph_nodes, colored_nodes = set(graph.nodes), set(colors)
    if graph_nodes != colored_nodes:
        missing = sorted(graph_nodes - colored_nodes)
        extra = sorted(colored_nodes - graph_nodes)
        raise InvalidRefinementInputError(
            f"colors must cover exactly the graph's nodes (missing={missing}, extra={extra})"
        )
    for node, color in colors.items():
        if not isinstance(color, str):
            raise InvalidRefinementInputError(f"color of node {node!r} must be a string")


# --------------------------------------------------------------------------- #
# Core steps
# --------------------------------------------------------------------------- #

def _initial_colors(graph: nx.DiGraph) -> dict[str, str]:
    colors: dict[str, str] = {}
    for node in graph.nodes:
        node_type = str(graph.nodes[node].get("node_type", DEFAULT_NODE_TYPE))
        out_hist = Counter(_edge_label(a) for _, _, a in graph.out_edges(node, data=True))
        in_hist = Counter(_edge_label(a) for _, _, a in graph.in_edges(node, data=True))
        colors[node] = _digest([
            "init",
            node_type,
            graph.in_degree(node),
            graph.out_degree(node),
            sorted(out_hist.items()),
            sorted(in_hist.items()),
        ])
    return dict(sorted(colors.items()))


def _refine(graph: nx.DiGraph, colors: dict[str, str]) -> dict[str, str]:
    refined: dict[str, str] = {}
    for node in graph.nodes:
        signature_parts: list[str] = []
        for _, neighbor, attrs in graph.out_edges(node, data=True):
            signature_parts.append(json.dumps(["out", _edge_label(attrs), colors[neighbor]]))
        for neighbor, _, attrs in graph.in_edges(node, data=True):
            signature_parts.append(json.dumps(["in", _edge_label(attrs), colors[neighbor]]))
        signature_parts.sort()  # multiset made canonical; duplicates are kept
        refined[node] = _digest(["wl", colors[node], signature_parts])
    return dict(sorted(refined.items()))


def _class_count(colors: dict[str, str]) -> int:
    return len(set(colors.values()))


def _run(graph: nx.DiGraph | TemporalGraph | Any, max_iterations: int) -> tuple[list[dict[str, str]], bool]:
    """Return (history of colorings from round 0, stable flag)."""
    graph = _validate_graph(graph)
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 0:
        raise InvalidRefinementInputError(
            f"max_iterations must be a non-negative int, got {max_iterations!r}"
        )
    colors = _initial_colors(graph)
    history = [colors]
    if not colors:
        return history, True
    for _ in range(max_iterations):
        new_colors = _refine(graph, colors)
        history.append(new_colors)
        # New colors are a function of the old ones, so classes can only split.
        # Equal class counts therefore means the partition did not change.
        if _class_count(new_colors) == _class_count(colors):
            return history, True
        colors = new_colors
    return history, False


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def initialize_colors(graph: nx.DiGraph | TemporalGraph | Any) -> RefinementResult:
    """Round-0 colors from node type, in/out degree and edge-type histograms.

    Raises :class:`InvalidRefinementInputError` for non-``DiGraph`` input or
    non-string node IDs. An empty graph returns a RefinementResult with empty
    node_colors and color_classes.
    """
    g = _validate_graph(graph)
    colors = _initial_colors(g)
    return RefinementResult(
        node_colors=colors,
        color_classes=get_color_classes(colors),
        iterations=DEFAULT_INITIAL_REFINEMENT_ITERATIONS,
        stable=len(colors) == 0,
    )


def refine_once(
    graph: nx.DiGraph | TemporalGraph | Any,
    colors: dict[str, str] | RefinementResult,
) -> RefinementResult:
    """Apply one refinement round to ``colors`` and return the new coloring.

    ``colors`` must cover exactly the graph's nodes (can be a raw dictionary
    or a RefinementResult dataclass). Incoming and outgoing edges both
    contribute, tagged by direction and edge-type label. Returns the official
    RefinementResult dataclass.
    """
    g = _validate_graph(graph)
    raw_colors = colors.node_colors if isinstance(colors, RefinementResult) else colors
    _validate_colors(g, raw_colors)
    new_colors = _refine(g, raw_colors)
    stable = _class_count(new_colors) == _class_count(raw_colors)
    prev_iterations = colors.iterations if isinstance(colors, RefinementResult) else 0
    return RefinementResult(
        node_colors=new_colors,
        color_classes=get_color_classes(new_colors),
        iterations=prev_iterations + 1,
        stable=stable,
    )


def get_color_classes(colors: dict[str, str] | RefinementResult) -> dict[str, list[str]]:
    """Group nodes by color: ``{color: sorted node IDs}``, keys sorted.

    Sorting only makes the output order deterministic; it never feeds back into
    color computation.
    """
    if isinstance(colors, RefinementResult):
        return colors.color_classes
    if not isinstance(colors, dict):
        raise InvalidRefinementInputError("colors must be a dict[str, str]")
    classes: dict[str, list[str]] = {}
    for node, color in colors.items():
        if not isinstance(color, str):
            raise InvalidRefinementInputError(f"color of node {node!r} must be a string")
        classes.setdefault(color, []).append(node)
    return {color: sorted(nodes) for color, nodes in sorted(classes.items())}


def color_refine(
    graph: nx.DiGraph,
    max_iterations: int = DEFAULT_MAX_REFINEMENT_ITERATIONS,
) -> RefinementResult:
    """Run Color Refinement until the partition is stable or the cap is hit.

    ``iterations`` is the number of refinement rounds executed, including the
    final round that confirmed stability (so a graph already stable at round 0
    reports ``iterations == 1``). ``stable`` is ``True`` only if such a
    confirming round was observed within ``max_iterations``; an empty graph is
    trivially stable with 0 iterations. ``max_iterations=0`` returns the
    initial coloring with ``stable=False`` for non-empty graphs.
    """
    history, stable = _run(graph, max_iterations)
    final = history[-1]
    return RefinementResult(
        node_colors=final,
        color_classes=get_color_classes(final),
        iterations=len(history) - 1,
        stable=stable,
    )


def refinement_history(
    graph: nx.DiGraph,
    max_iterations: int = DEFAULT_MAX_REFINEMENT_ITERATIONS,
) -> list[dict[str, str]]:
    """Return ``[colors_0, colors_1, ...]``, stopping at stability or the cap.

    Same-index entries of two graphs' histories are directly comparable; use
    this for fixed-depth cross-graph comparison. Additive helper (not part of
    the blueprint contract).
    """
    return _run(graph, max_iterations)[0]


def color_histogram(colors: dict[str, str] | RefinementResult) -> dict[str, int]:
    """Multiset of colors: ``{color: node count}``, an identity-free fingerprint."""
    raw = colors.node_colors if isinstance(colors, RefinementResult) else colors
    return dict(sorted(Counter(raw.values()).items()))


def wl_equivalent(
    graph_a: nx.DiGraph,
    graph_b: nx.DiGraph,
    max_iterations: int = DEFAULT_MAX_REFINEMENT_ITERATIONS,
) -> bool:
    """Return ``True`` if 1-WL does not distinguish the two graphs.

    Compares the color histograms round by round and requires the same number
    of rounds. ``True`` means *indistinguishable by 1-WL within
    ``max_iterations``*; it does NOT prove isomorphism. ``False`` is
    conclusive: the graphs are not isomorphic.
    """
    history_a, stable_a = _run(graph_a, max_iterations)
    history_b, stable_b = _run(graph_b, max_iterations)
    if len(history_a) != len(history_b) or stable_a != stable_b:
        return False
    return all(color_histogram(a) == color_histogram(b) for a, b in zip(history_a, history_b))
