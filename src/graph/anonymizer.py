"""Identity abstraction: replace machine identifiers with abstract ones.

Mapping rule (deterministic, name-independent)
----------------------------------------------
Abstract IDs ``N_0001, N_0002, ...`` are assigned in order of FIRST APPEARANCE
in the chronologically ordered events (stable for ties; source before
destination within an event). Graph nodes that appear in no event follow, in
the graph's node insertion order. Because the order never looks at the original
names, renaming machines does not change the anonymised output.

Replacement is simultaneous (old -> new in one pass over a freshly built
graph), so an original ID that already looks like an abstract ID (even one
that is swapped with another) cannot collide.

Traceability
------------
Each node's ``original_id`` attribute stores the pre-anonymisation ID (if the
node already had one, e.g. when re-anonymising, the earliest is kept). Color
Refinement never reads ``original_id`` or node names.

IMPORTANT: anonymisation is NOT privacy protection
--------------------------------------------------
This is pseudonymisation for structural analysis. Topology, timing, event
frequency, protocols and (in events) ports remain and can allow
re-identification by linkage or fingerprinting. The deterministic mapping is
also reversible by anyone holding ``original_id`` attributes or the mapping.
Do not treat output as anonymous data for sharing or compliance purposes.
"""

from __future__ import annotations

import copy
import dataclasses

import networkx as nx

from src.core.config import DEFAULT_IDENTITY_PREFIX, IDENTITY_INDEX_WIDTH
from src.core.exceptions import InvalidGraphError
from src.core.models import TemporalGraph
from src.graph.temporal_graph import get_ordered_events


def _abstract_id(index: int) -> str:
    return f"{DEFAULT_IDENTITY_PREFIX}_{index:0{IDENTITY_INDEX_WIDTH}d}"


def create_identity_mapping(graph: TemporalGraph) -> dict[str, str]:
    """Return ``{current_node_id: abstract_id}`` for every node of ``graph``.

    Deterministic for the same input and a bijection (no two nodes share an
    abstract ID). Raises :class:`InvalidGraphError` if a node ID is not a
    string or an event references a node absent from the graph.
    """
    nodes = graph.graph.nodes
    for node in nodes:
        if not isinstance(node, str):
            raise InvalidGraphError(f"node IDs must be strings, got {node!r}")
    mapping: dict[str, str] = {}

    def assign(node: str) -> None:
        if node not in mapping:
            mapping[node] = _abstract_id(len(mapping) + 1)

    for event in get_ordered_events(graph):
        for endpoint in (event.source, event.destination):
            if endpoint not in nodes:
                raise InvalidGraphError(f"event references node {endpoint!r} missing from graph")
            assign(endpoint)
    for node in nodes:
        assign(node)
    return mapping


def anonymize_graph(graph: TemporalGraph) -> TemporalGraph:
    """Return a NEW :class:`TemporalGraph` with abstract node identifiers.

    Preserved: topology, direction, node types/roles, all edge attributes
    (types, weights, timestamps, bytes, durations), event order, event content
    other than endpoints, and ``start_time``/``end_time``. Nodes and edges are
    inserted in canonical (abstract-ID) order. The input is never mutated.
    """
    mapping = create_identity_mapping(graph)
    new_graph = nx.DiGraph()
    new_graph.graph.update(copy.deepcopy(graph.graph.graph))

    for old_id, new_id in mapping.items():  # insertion order == abstract-ID order
        attrs = copy.deepcopy(graph.graph.nodes[old_id])
        if attrs.get("original_id") is None:
            attrs["original_id"] = old_id
        new_graph.add_node(new_id, **attrs)

    renamed_edges = sorted(
        (mapping[u], mapping[v], u, v) for u, v in graph.graph.edges
    )
    for new_u, new_v, old_u, old_v in renamed_edges:
        new_graph.add_edge(new_u, new_v, **copy.deepcopy(graph.graph.edges[old_u, old_v]))

    new_events = [
        dataclasses.replace(
            event, source=mapping[event.source], destination=mapping[event.destination]
        )
        for event in graph.events
    ]
    return TemporalGraph(
        graph=new_graph,
        events=new_events,
        start_time=graph.start_time,
        end_time=graph.end_time,
    )
