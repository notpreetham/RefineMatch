"""Reproducible graph/event mutations for robustness testing.

Every mutation works on the EVENT list and rebuilds the graph with the Member 1
engine, so ``graph`` and ``events`` always stay consistent. Node ``node_type``,
``role`` and ``original_id`` of surviving nodes are carried over. The input
graph is never modified. All randomness comes from ``random.Random(seed)`` over
sorted inputs, so the same graph + seed + parameters give identical output.

Identity-only vs structural: ``rename_identities`` changes names and nothing
else (structure must be unchanged, so a good matcher's score must not change).
All other mutations change structure, timing or frequency.
:func:`is_identity_only` tells the two apart.
"""

from __future__ import annotations

import dataclasses
import math
import random
from datetime import timedelta
from typing import Callable

from src.core.exceptions import InvalidGraphError
from src.core.models import EventRecord, TemporalGraph
from src.graph.graph_builder import build_temporal_graph

NOISE_EVENT_TYPES = ("dns_query", "ntp_sync", "web_browse")
IDENTITY_ONLY_MUTATIONS = frozenset({"rename_identities"})


def _check(graph: TemporalGraph, percentage: float | None, seed: int) -> None:
    if not isinstance(graph, TemporalGraph):
        raise InvalidGraphError("graph must be a TemporalGraph")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise InvalidGraphError("seed must be an int")
    if percentage is not None and (not isinstance(percentage, (int, float)) or not 0.0 <= percentage <= 1.0):
        raise InvalidGraphError(f"percentage must be in [0, 1], got {percentage!r}")


def _count(percentage: float, total: int) -> int:
    """Items affected: floor(p*total + 0.5), at least 1 if p > 0 and total > 0."""
    if percentage <= 0 or total == 0:
        return 0
    return max(1, min(total, math.floor(percentage * total + 0.5)))


def rebuild_from_events(source: TemporalGraph, events: list[EventRecord],
                        origin_of: dict[str, str] | None = None) -> TemporalGraph:
    """Build a graph from ``events`` and copy node attributes from ``source``.

    ``origin_of`` maps new node IDs to the ID they had in ``source`` (identity
    for nodes not listed).
    """
    rebuilt = build_temporal_graph(events)
    for node in rebuilt.graph.nodes:
        old = (origin_of or {}).get(node, node)
        if old in source.graph:
            for key in ("node_type", "role", "original_id"):
                if key in source.graph.nodes[old]:
                    rebuilt.graph.nodes[node][key] = source.graph.nodes[old][key]
    return rebuilt


def _time_range(graph: TemporalGraph):
    return graph.start_time, graph.end_time


def _random_time(graph: TemporalGraph, rng: random.Random):
    start, end = _time_range(graph)
    span = (end - start).total_seconds() if start is not None else 0.0
    return start + timedelta(seconds=rng.uniform(0.0, span)) if start is not None else None


def rename_identities(graph: TemporalGraph, seed: int) -> TemporalGraph:
    """Replace every node ID with a random unrelated name (identity-only change)."""
    _check(graph, None, seed)
    rng = random.Random(seed)
    mapping, used = {}, set()
    for node in sorted(graph.graph.nodes):
        while True:
            new = f"host-{rng.getrandbits(32):08x}"
            if new not in used:
                used.add(new)
                mapping[node] = new
                break
    events = [dataclasses.replace(e, source=mapping[e.source], destination=mapping[e.destination])
              for e in graph.events]
    result = rebuild_from_events(graph, events, {new: old for old, new in mapping.items()})
    for new, old in ((mapping[o], o) for o in mapping):
        if result.graph.nodes[new].get("original_id") is None:
            result.graph.nodes[new]["original_id"] = old
    # isolated nodes (no events) cannot survive an event-based rebuild; keep them explicitly
    for old, new in mapping.items():
        if new not in result.graph:
            result.graph.add_node(new, **dict(graph.graph.nodes[old], original_id=old))
    return result


def insert_benign_nodes(graph: TemporalGraph, percentage: float, seed: int) -> TemporalGraph:
    """Add ``percentage`` * |V| new noise nodes, each linked to existing nodes by 1-3 benign events."""
    _check(graph, percentage, seed)
    rng = random.Random(seed)
    existing = sorted(graph.graph.nodes)
    events = [dataclasses.replace(e) for e in graph.events]
    for i in range(_count(percentage, len(existing))):
        noise = f"noise-{rng.getrandbits(32):08x}"
        for _ in range(rng.randint(1, 2)):
            peer = rng.choice(existing)
            source, destination = (noise, peer) if rng.random() < 0.5 else (peer, noise)
            for _ in range(rng.randint(1, 3)):
                events.append(EventRecord(_random_time(graph, rng), source, destination,
                                          rng.choice(NOISE_EVENT_TYPES), protocol="tcp"))
    return rebuild_from_events(graph, events)


def insert_edges(graph: TemporalGraph, percentage: float, seed: int) -> TemporalGraph:
    """Add new edges between existing nodes (``percentage`` * |E|), reusing existing event types."""
    _check(graph, percentage, seed)
    rng = random.Random(seed)
    nodes = sorted(graph.graph.nodes)
    types = sorted({e.event_type for e in graph.events}) or ["event"]
    absent = [(u, v) for u in nodes for v in nodes if u != v and not graph.graph.has_edge(u, v)]
    chosen = rng.sample(absent, min(len(absent), _count(percentage, graph.graph.number_of_edges())))
    events = [dataclasses.replace(e) for e in graph.events]
    for u, v in chosen:
        events.append(EventRecord(_random_time(graph, rng), u, v, rng.choice(types), protocol="tcp"))
    return rebuild_from_events(graph, events)


def delete_edges(graph: TemporalGraph, percentage: float, seed: int) -> TemporalGraph:
    """Remove ``percentage`` * |E| aggregated edges (all their events). Nodes left isolated disappear."""
    _check(graph, percentage, seed)
    rng = random.Random(seed)
    edges = sorted(graph.graph.edges)
    removed = set(rng.sample(edges, _count(percentage, len(edges))))
    events = [dataclasses.replace(e) for e in graph.events if (e.source, e.destination) not in removed]
    return rebuild_from_events(graph, events)


def rewire_edges(graph: TemporalGraph, percentage: float, seed: int) -> TemporalGraph:
    """Topology mutation: redirect ``percentage`` * |E| edges to a different destination node."""
    _check(graph, percentage, seed)
    rng = random.Random(seed)
    nodes = sorted(graph.graph.nodes)
    edges = sorted(graph.graph.edges)
    redirect = {}
    for u, v in rng.sample(edges, _count(percentage, len(edges))):
        options = [n for n in nodes if n not in (u, v)]
        if options:
            redirect[(u, v)] = rng.choice(options)
    events = [dataclasses.replace(e, destination=redirect.get((e.source, e.destination), e.destination))
              for e in graph.events]
    return rebuild_from_events(graph, events)


def perturb_timestamps(graph: TemporalGraph, percentage: float, seed: int,
                       max_shift_seconds: float | None = None) -> TemporalGraph:
    """Shift ``percentage`` of events by up to +-``max_shift_seconds`` (default 10% of the time span, min 1 s)."""
    _check(graph, percentage, seed)
    rng = random.Random(seed)
    start, end = _time_range(graph)
    span = (end - start).total_seconds() if start is not None else 0.0
    limit = max_shift_seconds if max_shift_seconds is not None else max(1.0, 0.1 * span)
    picked = set(rng.sample(range(len(graph.events)), _count(percentage, len(graph.events))))
    events = [dataclasses.replace(e, timestamp=e.timestamp + timedelta(seconds=rng.uniform(-limit, limit)))
              if i in picked else dataclasses.replace(e) for i, e in enumerate(graph.events)]
    return rebuild_from_events(graph, events)


def perturb_frequency(graph: TemporalGraph, percentage: float, seed: int,
                      min_factor: float = 0.5, max_factor: float = 2.0) -> TemporalGraph:
    """Rescale the event count of ``percentage`` * |E| edges by a random factor (edges never vanish)."""
    _check(graph, percentage, seed)
    rng = random.Random(seed)
    by_edge: dict[tuple[str, str], list[EventRecord]] = {}
    for e in graph.events:
        by_edge.setdefault((e.source, e.destination), []).append(e)
    chosen = set(rng.sample(sorted(by_edge), _count(percentage, len(by_edge))))
    events: list[EventRecord] = []
    for key in sorted(by_edge):
        group = [dataclasses.replace(e) for e in by_edge[key]]
        if key in chosen:
            target = max(1, round(len(group) * rng.uniform(min_factor, max_factor)))
            if target < len(group):
                group = rng.sample(group, target)
            else:
                first = min(e.timestamp for e in group)
                span = (max(e.timestamp for e in group) - first).total_seconds()
                for _ in range(target - len(group)):
                    template = rng.choice(group)
                    group.append(dataclasses.replace(
                        template, timestamp=first + timedelta(seconds=rng.uniform(0.0, span))))
        events.extend(group)
    return rebuild_from_events(graph, events)


MUTATIONS: dict[str, Callable[..., TemporalGraph]] = {
    "insert_benign_nodes": insert_benign_nodes, "insert_edges": insert_edges,
    "delete_edges": delete_edges, "rewire_edges": rewire_edges,
    "perturb_timestamps": perturb_timestamps, "perturb_frequency": perturb_frequency,
}


def is_identity_only(mutations: list[dict]) -> bool:
    """True if every mutation only changes identities (``rename_identities``)."""
    return all(m.get("type") in IDENTITY_ONLY_MUTATIONS for m in mutations)


def apply_mutations(graph: TemporalGraph, mutations: list[dict], seed: int) -> TemporalGraph:
    """Apply mutations in order. Each dict: ``{"type": name, "percentage": p, ...extra kwargs}``.

    Step ``i`` uses seed ``seed + 7919 * (i + 1)`` so steps are independent but
    the whole sequence is reproducible.
    """
    _check(graph, None, seed)
    result = graph
    for i, spec in enumerate(mutations):
        kind = spec.get("type")
        step_seed = seed + 7919 * (i + 1)
        extra = {k: v for k, v in spec.items() if k not in ("type", "percentage")}
        if kind == "rename_identities":
            result = rename_identities(result, step_seed)
        elif kind in MUTATIONS:
            if "percentage" not in spec:
                raise InvalidGraphError(f"mutation {kind!r} requires a 'percentage'")
            result = MUTATIONS[kind](result, spec["percentage"], step_seed, **extra)
        else:
            raise InvalidGraphError(
                f"unknown mutation {kind!r}; choose from {['rename_identities', *MUTATIONS]}")
    return result
