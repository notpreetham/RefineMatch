"""Build attributed, directed communication graphs from events.

Graph attribute contract (for Members 2, 3, 4)
==============================================

The graph is a ``networkx.DiGraph``. Node IDs are ``str``. One edge exists per
ordered ``(source, destination)`` pair; repeated events are aggregated, never
dropped.

Node attributes
    ``node_type`` (str)         default ``DEFAULT_NODE_TYPE`` ("host"); set it
                                explicitly with :func:`assign_node_attributes`.
                                A generic event log does not reveal real roles,
                                so nothing is guessed.
    ``role`` (str | None)       optional semantic label, default ``None``.
    ``original_id`` (str|None)  ``None`` until the graph is anonymised; then the
                                pre-anonymisation identifier. Never a
                                structural feature.

Edge attributes (source -> destination)
    ``edge_type`` (str)         most frequent ``event_type`` (ties: alphabetical).
    ``edge_types`` (dict)       ``{event_type: count}``, keys sorted. Full
                                information; Color Refinement uses its key set.
    ``direction`` (str)         always ``EDGE_DIRECTION_SOURCE_TO_DESTINATION``.
    ``weight`` (int)            number of events aggregated (>= 1).
    ``first_seen`` / ``last_seen`` (datetime)  earliest / latest event time.
    ``protocol`` (str | None)   most frequent non-null protocol, else ``None``.
    ``protocols`` (dict)        ``{protocol: count}`` over events that had one.
    ``bytes_total`` (int|None)  sum of ``bytes`` over events that reported it;
                                ``None`` if none did (unknown is not zero).
    ``bytes_known_count`` (int) how many events contributed to ``bytes_total``.
    ``duration`` (float|None)   TOTAL of ``duration`` over events that reported
                                it (not a mean); ``None`` if none did.
    ``duration_known_count``    how many events contributed to ``duration``.

Self-loops (``source == destination``) are allowed. Ports are not stored on
edges (they can be machine/service identifying); they remain on the events.
"""

from __future__ import annotations

import dataclasses
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

import networkx as nx

from src.core.config import DEFAULT_NODE_TYPE, EDGE_DIRECTION_SOURCE_TO_DESTINATION
from src.core.exceptions import InvalidEventError, InvalidGraphError
from src.core.models import (
    EventRecord,
    GraphEdge,
    GraphNode,
    TemporalGraph,
    is_timezone_aware,
)
from src.graph.temporal_graph import copy_temporal_graph


def validate_events(events: Sequence[EventRecord]) -> None:
    """Validate an event sequence, raising :class:`InvalidEventError`.

    Checks: list/tuple input, every item is a valid ``EventRecord`` (re-checked
    in case it was mutated after construction), and timestamps are all
    timezone-aware or all naive.
    """
    if not isinstance(events, (list, tuple)):
        raise InvalidEventError(f"events must be a list of EventRecord, got {type(events).__name__}")
    awareness: set[bool] = set()
    for index, event in enumerate(events):
        if not isinstance(event, EventRecord):
            raise InvalidEventError(
                f"events[{index}] is {type(event).__name__}, expected EventRecord"
            )
        try:
            event.validate()
        except InvalidEventError as exc:
            raise InvalidEventError(f"events[{index}]: {exc}") from exc
        awareness.add(is_timezone_aware(event.timestamp))
    if len(awareness) > 1:
        raise InvalidEventError(
            "events mix timezone-aware and naive timestamps; normalise them before building a graph"
        )


def _dominant(counter: Counter) -> str | None:
    """Most frequent key; ties broken alphabetically for determinism."""
    if not counter:
        return None
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


@dataclass
class _EdgeAccumulator:
    weight: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    event_types: Counter = field(default_factory=Counter)
    protocols: Counter = field(default_factory=Counter)
    byte_values: list[int] = field(default_factory=list)
    duration_values: list[float] = field(default_factory=list)


def aggregate_edges(events: list[EventRecord]) -> nx.DiGraph:
    """Aggregate events into a directed graph (see module docstring for attributes).

    Repeated communications between the same ordered pair become one edge whose
    ``weight`` equals the event count. Direction is preserved: ``a -> b`` and
    ``b -> a`` are distinct edges. Empty input gives an empty graph. Raises
    :class:`InvalidEventError` for invalid records.
    """
    validate_events(events)
    graph = nx.DiGraph()
    accumulators: dict[tuple[str, str], _EdgeAccumulator] = {}

    for event in events:
        for node in (event.source, event.destination):
            if node not in graph:
                graph.add_node(node, node_type=DEFAULT_NODE_TYPE, role=None, original_id=None)
        acc = accumulators.setdefault((event.source, event.destination), _EdgeAccumulator())
        acc.weight += 1
        if acc.first_seen is None or event.timestamp < acc.first_seen:
            acc.first_seen = event.timestamp
        if acc.last_seen is None or event.timestamp > acc.last_seen:
            acc.last_seen = event.timestamp
        acc.event_types[event.event_type] += 1
        if event.protocol is not None:
            acc.protocols[event.protocol] += 1
        if event.bytes is not None:
            acc.byte_values.append(event.bytes)
        if event.duration is not None:
            acc.duration_values.append(float(event.duration))

    for (source, destination), acc in accumulators.items():
        graph.add_edge(
            source,
            destination,
            edge_type=_dominant(acc.event_types),
            edge_types=dict(sorted(acc.event_types.items())),
            direction=EDGE_DIRECTION_SOURCE_TO_DESTINATION,
            weight=acc.weight,
            first_seen=acc.first_seen,
            last_seen=acc.last_seen,
            protocol=_dominant(acc.protocols),
            protocols=dict(sorted(acc.protocols.items())),
            bytes_total=sum(acc.byte_values) if acc.byte_values else None,
            bytes_known_count=len(acc.byte_values),
            duration=math.fsum(acc.duration_values) if acc.duration_values else None,
            duration_known_count=len(acc.duration_values),
        )
    return graph


def build_temporal_graph(events: list[EventRecord]) -> TemporalGraph:
    """Build a :class:`TemporalGraph` from events.

    ``graph`` is :func:`aggregate_edges` of the events. ``events`` is an
    independent copy of the input in its ORIGINAL (input) order; use
    ``get_ordered_events`` for chronological order. ``start_time``/``end_time``
    are the earliest/latest timestamps, or ``None`` for empty input.
    """
    validate_events(events)
    graph = aggregate_edges(events)
    stored = [dataclasses.replace(event) for event in events]
    if stored:
        start_time = min(event.timestamp for event in stored)
        end_time = max(event.timestamp for event in stored)
    else:
        start_time = end_time = None
    return TemporalGraph(graph=graph, events=stored, start_time=start_time, end_time=end_time)


def assign_node_attributes(
    graph: TemporalGraph,
    node_types: Mapping[str, str] | None = None,
    roles: Mapping[str, str | None] | None = None,
) -> TemporalGraph:
    """Return a copy of ``graph`` with explicit node types and/or roles.

    Keys are the graph's current node IDs (original IDs before anonymisation,
    abstract IDs afterwards). Unmentioned nodes keep their attributes. Raises
    :class:`InvalidGraphError` for unknown node IDs or empty type strings. The
    input graph is not modified.
    """
    result = copy_temporal_graph(graph)
    for label, mapping in (("node_types", node_types), ("roles", roles)):
        for node, value in (mapping or {}).items():
            if node not in result.graph:
                raise InvalidGraphError(f"{label} refers to unknown node {node!r}")
            key = "node_type" if label == "node_types" else "role"
            if key == "node_type" and (not isinstance(value, str) or not value.strip()):
                raise InvalidGraphError(f"node type for {node!r} must be a non-empty string")
            result.graph.nodes[node][key] = value
    return result


def get_graph_node(graph: nx.DiGraph, node_id: str) -> GraphNode:
    """Read a node of ``graph`` as a :class:`GraphNode` dataclass."""
    if node_id not in graph:
        raise InvalidGraphError(f"node {node_id!r} not in graph")
    attrs = graph.nodes[node_id]
    return GraphNode(
        node_id=node_id,
        node_type=attrs.get("node_type", DEFAULT_NODE_TYPE),
        role=attrs.get("role"),
        original_id=attrs.get("original_id"),
    )


def get_graph_edge(graph: nx.DiGraph, source: str, destination: str) -> GraphEdge:
    """Read an edge of ``graph`` as a :class:`GraphEdge` dataclass."""
    if not graph.has_edge(source, destination):
        raise InvalidGraphError(f"edge {source!r} -> {destination!r} not in graph")
    attrs = graph.edges[source, destination]
    missing = [k for k in ("edge_type", "weight", "first_seen", "last_seen") if k not in attrs]
    if missing:
        raise InvalidGraphError(f"edge {source!r} -> {destination!r} lacks attributes {missing}")
    return GraphEdge(
        source=source,
        destination=destination,
        edge_type=attrs["edge_type"],
        direction=attrs.get("direction", EDGE_DIRECTION_SOURCE_TO_DESTINATION),
        weight=attrs["weight"],
        first_seen=attrs["first_seen"],
        last_seen=attrs["last_seen"],
        duration=attrs.get("duration"),
        bytes_total=attrs.get("bytes_total"),
        protocol=attrs.get("protocol"),
    )
