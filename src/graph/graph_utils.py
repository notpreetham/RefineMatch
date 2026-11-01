"""Small identity-free helpers shared by matching, scoring and baselines."""

from __future__ import annotations

from src.core.config import DEFAULT_NODE_TYPE


def edge_label(attributes: dict) -> tuple[str, ...]:
    """Sorted distinct event types on an edge (same rule Color Refinement uses)."""
    types = attributes.get("edge_types")
    if types:
        return tuple(sorted(str(t) for t in types))
    if attributes.get("edge_type") is not None:
        return (str(attributes["edge_type"]),)
    return ()


def node_type_of(graph, node: str) -> str:
    """The node's ``node_type`` attribute, or the configured default."""
    return str(graph.nodes[node].get("node_type", DEFAULT_NODE_TYPE))


def label_jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Jaccard overlap of two edge-type labels (1.0 when both are empty)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def ratio_compat(a: float, b: float) -> float:
    """``min/max`` compatibility of two non-negative numbers (1.0 if both 0)."""
    if a == b:
        return 1.0
    return min(a, b) / max(a, b)


def relative_first_seen(graph) -> dict[str, float]:
    """Each node's earliest incident-edge ``first_seen`` as a position in [0, 1].

    0 = earliest in this graph, 1 = latest. Uses only RELATIVE time, so it is
    independent of identities and absolute clocks; used solely to break ties
    between structurally equivalent candidates. Graphs without ``first_seen``
    attributes (or with zero time span) map every node to 0.0.
    """
    firsts: dict[str, object] = {}
    for u, v, attrs in graph.edges(data=True):
        moment = attrs.get("first_seen")
        if moment is None:
            continue
        for node in (u, v):
            if node not in firsts or moment < firsts[node]:
                firsts[node] = moment
    if not firsts:
        return {node: 0.0 for node in graph.nodes}
    low, high = min(firsts.values()), max(firsts.values())
    span = (high - low).total_seconds()
    return {node: ((firsts[node] - low).total_seconds() / span if span > 0 and node in firsts else 0.0)
            for node in graph.nodes}
