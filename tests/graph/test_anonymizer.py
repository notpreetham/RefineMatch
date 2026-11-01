"""Tests for src.graph.anonymizer."""

from datetime import datetime, timedelta

import networkx as nx
import pytest

from src.core.exceptions import InvalidGraphError
from src.core.models import EventRecord
from src.graph.anonymizer import anonymize_graph, create_identity_mapping
from src.graph.graph_builder import assign_node_attributes, build_temporal_graph

T0 = datetime(2024, 1, 1, 12, 0, 0)


def ev(seconds, src, dst, etype="http", **kw):
    return EventRecord(T0 + timedelta(seconds=seconds), src, dst, etype, **kw)


def sample_events(names=("10.0.0.1", "10.0.0.2", "10.0.0.3")):
    a, b, c = names
    return [ev(0, a, b, bytes=10), ev(5, a, b, bytes=20), ev(7, b, c, "sql", protocol="tcp"),
            ev(9, c, a, "reply")]


def sample_graph():
    tg = build_temporal_graph(sample_events())
    return assign_node_attributes(
        tg, {"10.0.0.1": "client", "10.0.0.2": "server", "10.0.0.3": "database"},
        {"10.0.0.2": "web"},
    )


def test_identifiers_replaced():
    anon = anonymize_graph(sample_graph())
    assert set(anon.graph.nodes) == {"N_0001", "N_0002", "N_0003"}
    assert all("10.0.0" not in e.source + e.destination for e in anon.events)
    assert {a["original_id"] for _, a in anon.graph.nodes(data=True)} == {
        "10.0.0.1", "10.0.0.2", "10.0.0.3"}


def test_mapping_follows_first_appearance_order():
    mapping = create_identity_mapping(sample_graph())
    assert mapping == {"10.0.0.1": "N_0001", "10.0.0.2": "N_0002", "10.0.0.3": "N_0003"}


def test_structure_and_attributes_preserved():
    original = sample_graph()
    anon = anonymize_graph(original)
    mapping = create_identity_mapping(original)
    for u, v, attrs in original.graph.edges(data=True):
        assert anon.graph.edges[mapping[u], mapping[v]] == attrs
    for node, attrs in original.graph.nodes(data=True):
        new_attrs = anon.graph.nodes[mapping[node]]
        assert new_attrs["node_type"] == attrs["node_type"] and new_attrs["role"] == attrs["role"]
    assert anon.graph.number_of_edges() == original.graph.number_of_edges()
    assert (anon.start_time, anon.end_time) == (original.start_time, original.end_time)
    renamed = nx.relabel_nodes(original.graph, mapping)
    assert nx.is_isomorphic(
        renamed, anon.graph,
        node_match=lambda x, y: x["node_type"] == y["node_type"] and x["role"] == y["role"],
        edge_match=lambda x, y: x == y,
    )


def test_direction_preserved():
    anon = anonymize_graph(sample_graph())
    assert anon.graph.has_edge("N_0003", "N_0001") and not anon.graph.has_edge("N_0001", "N_0003")


def test_deterministic_mapping_and_output():
    g = sample_graph()
    assert create_identity_mapping(g) == create_identity_mapping(g)
    first, second = anonymize_graph(g), anonymize_graph(g)
    assert list(first.graph.nodes(data=True)) == list(second.graph.nodes(data=True))
    assert list(first.graph.edges(data=True)) == list(second.graph.edges(data=True))
    assert first.events == second.events


def test_renaming_machines_does_not_change_anonymized_output():
    g1 = build_temporal_graph(sample_events(("alpha", "beta", "gamma")))
    g2 = build_temporal_graph(sample_events(("zz", "yy", "xx")))
    a1, a2 = anonymize_graph(g1), anonymize_graph(g2)
    assert list(a1.graph.edges(data=True)) == list(a2.graph.edges(data=True))
    assert a1.events == a2.events


def test_consistency_across_nodes_edges_and_events():
    anon = anonymize_graph(sample_graph())
    for event in anon.events:
        assert event.source in anon.graph and event.destination in anon.graph
        assert anon.graph.has_edge(event.source, event.destination)
    from src.graph.temporal_graph import get_event_frequency
    for u, v, attrs in anon.graph.edges(data=True):
        assert get_event_frequency(anon, u, v) == attrs["weight"]


def test_event_order_and_non_endpoint_fields_preserved():
    original = sample_graph()
    anon = anonymize_graph(original)
    for before, after in zip(original.events, anon.events):
        assert (before.timestamp, before.event_type, before.protocol, before.bytes) == (
            after.timestamp, after.event_type, after.protocol, after.bytes)


def test_original_not_mutated():
    original = sample_graph()
    nodes_before = list(original.graph.nodes(data=True))
    edges_before = [(u, v, dict(a)) for u, v, a in original.graph.edges(data=True)]
    events_before = [(e.source, e.destination) for e in original.events]
    anon = anonymize_graph(original)
    anon.graph.edges["N_0001", "N_0002"]["edge_types"]["http"] = 999
    anon.events[0].bytes = 12345
    assert list(original.graph.nodes(data=True)) == nodes_before
    assert [(u, v, dict(a)) for u, v, a in original.graph.edges(data=True)] == edges_before
    assert [(e.source, e.destination) for e in original.events] == events_before
    assert original.graph.edges["10.0.0.1", "10.0.0.2"]["edge_types"]["http"] == 2
    assert original.events[0].bytes == 10


def test_collision_with_abstract_looking_names_is_handled():
    # Original IDs already look abstract and are swapped relative to the new order.
    tg = build_temporal_graph([ev(0, "N_0002", "N_0001"), ev(1, "N_0001", "N_0003")])
    mapping = create_identity_mapping(tg)
    assert mapping == {"N_0002": "N_0001", "N_0001": "N_0002", "N_0003": "N_0003"}
    assert len(set(mapping.values())) == len(mapping)
    anon = anonymize_graph(tg)
    assert anon.graph.has_edge("N_0001", "N_0002") and anon.graph.has_edge("N_0002", "N_0003")
    assert anon.graph.nodes["N_0001"]["original_id"] == "N_0002"


def test_reanonymizing_keeps_earliest_original_id():
    twice = anonymize_graph(anonymize_graph(sample_graph()))
    assert {a["original_id"] for _, a in twice.graph.nodes(data=True)} == {
        "10.0.0.1", "10.0.0.2", "10.0.0.3"}


def test_isolated_nodes_are_mapped_after_event_nodes():
    tg = build_temporal_graph([ev(0, "a", "b")])
    tg.graph.add_node("lonely", node_type="host", role=None, original_id=None)
    mapping = create_identity_mapping(tg)
    assert mapping["lonely"] == "N_0003"


def test_empty_graph():
    anon = anonymize_graph(build_temporal_graph([]))
    assert anon.graph.number_of_nodes() == 0 and anon.start_time is None


def test_event_referencing_missing_node_rejected():
    tg = build_temporal_graph([ev(0, "a", "b")])
    tg.events.append(ev(1, "a", "ghost"))
    with pytest.raises(InvalidGraphError):
        create_identity_mapping(tg)


def test_non_string_node_ids_rejected():
    tg = build_temporal_graph([])
    tg.graph.add_node(42)
    with pytest.raises(InvalidGraphError):
        create_identity_mapping(tg)
