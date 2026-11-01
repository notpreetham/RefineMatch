"""Tests for src.graph.graph_builder."""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.config import DEFAULT_NODE_TYPE, EDGE_DIRECTION_SOURCE_TO_DESTINATION
from src.core.exceptions import InvalidEventError, InvalidGraphError
from src.core.models import EventRecord
from src.graph.graph_builder import (
    aggregate_edges,
    assign_node_attributes,
    build_temporal_graph,
    get_graph_edge,
    get_graph_node,
)

T0 = datetime(2024, 1, 1, 12, 0, 0)


def ev(seconds, src="a", dst="b", etype="http", **kw):
    return EventRecord(T0 + timedelta(seconds=seconds), src, dst, etype, **kw)


def test_empty_input():
    tg = build_temporal_graph([])
    assert tg.graph.number_of_nodes() == 0 and tg.events == []
    assert tg.start_time is None and tg.end_time is None
    assert aggregate_edges([]).number_of_nodes() == 0


def test_single_event():
    tg = build_temporal_graph([ev(0, protocol="tcp", bytes=100, duration=1.5)])
    g = tg.graph
    assert set(g.nodes) == {"a", "b"} and list(g.edges) == [("a", "b")]
    edge = g.edges["a", "b"]
    assert edge["weight"] == 1 and edge["edge_type"] == "http" and edge["protocol"] == "tcp"
    assert edge["bytes_total"] == 100 and edge["duration"] == 1.5
    assert edge["direction"] == EDGE_DIRECTION_SOURCE_TO_DESTINATION
    assert g.nodes["a"]["node_type"] == DEFAULT_NODE_TYPE
    assert g.nodes["a"]["role"] is None and g.nodes["a"]["original_id"] is None
    assert tg.start_time == tg.end_time == T0


def test_repeated_communication_aggregates_without_losing_counts():
    tg = build_temporal_graph([ev(0), ev(5), ev(9)])
    assert tg.graph.number_of_edges() == 1
    assert tg.graph.edges["a", "b"]["weight"] == 3
    assert len(tg.events) == 3


def test_multiple_event_types_and_protocols_preserved():
    events = [ev(0, etype="dns", protocol="udp"), ev(1, etype="http", protocol="tcp"),
              ev(2, etype="http", protocol="tcp"), ev(3, etype="http")]
    edge = aggregate_edges(events).edges["a", "b"]
    assert edge["edge_types"] == {"dns": 1, "http": 3}
    assert edge["edge_type"] == "http"
    assert edge["protocols"] == {"tcp": 2, "udp": 1} and edge["protocol"] == "tcp"
    assert edge["weight"] == 4


def test_dominant_type_tie_is_alphabetical():
    edge = aggregate_edges([ev(0, etype="zeta"), ev(1, etype="alpha")]).edges["a", "b"]
    assert edge["edge_type"] == "alpha"


def test_direction_preserved():
    g = aggregate_edges([ev(0, "a", "b"), ev(1, "b", "a", etype="reply")])
    assert g.has_edge("a", "b") and g.has_edge("b", "a")
    assert g.edges["a", "b"]["edge_type"] == "http" and g.edges["b", "a"]["edge_type"] == "reply"
    assert g.number_of_edges() == 2


def test_first_and_last_seen_independent_of_input_order():
    g = aggregate_edges([ev(50), ev(10), ev(30)])
    assert g.edges["a", "b"]["first_seen"] == T0 + timedelta(seconds=10)
    assert g.edges["a", "b"]["last_seen"] == T0 + timedelta(seconds=50)


def test_time_range_and_original_event_order_preserved():
    events = [ev(50), ev(10), ev(30)]
    tg = build_temporal_graph(events)
    assert tg.start_time == T0 + timedelta(seconds=10)
    assert tg.end_time == T0 + timedelta(seconds=50)
    assert tg.events == events and tg.events is not events
    assert tg.events[0] is not events[0]  # independent copies


def test_bytes_and_duration_policy_sum_known_values_only():
    g = aggregate_edges([ev(0, bytes=10, duration=1.0), ev(1), ev(2, bytes=5, duration=0.5)])
    edge = g.edges["a", "b"]
    assert edge["bytes_total"] == 15 and edge["bytes_known_count"] == 2
    assert edge["duration"] == 1.5 and edge["duration_known_count"] == 2
    assert edge["weight"] == 3


def test_unknown_bytes_stay_none_not_zero():
    edge = aggregate_edges([ev(0), ev(1)]).edges["a", "b"]
    assert edge["bytes_total"] is None and edge["duration"] is None
    assert edge["bytes_known_count"] == 0


def test_zero_bytes_is_distinct_from_unknown():
    assert aggregate_edges([ev(0, bytes=0)]).edges["a", "b"]["bytes_total"] == 0


def test_self_loop_allowed():
    g = aggregate_edges([ev(0, "a", "a")])
    assert g.has_edge("a", "a") and g.number_of_nodes() == 1


def test_invalid_records_rejected():
    with pytest.raises(InvalidEventError):
        build_temporal_graph(None)
    with pytest.raises(InvalidEventError):
        build_temporal_graph(["not an event"])
    bad = ev(0)
    bad.timestamp = "yesterday"
    with pytest.raises(InvalidEventError, match="events\\[1\\]"):
        build_temporal_graph([ev(0), bad])
    bad2 = ev(0)
    bad2.bytes = -3
    with pytest.raises(InvalidEventError):
        aggregate_edges([bad2])


def test_mixed_timezone_awareness_rejected():
    aware = EventRecord(datetime(2024, 1, 1, tzinfo=timezone.utc), "a", "b", "x")
    with pytest.raises(InvalidEventError):
        build_temporal_graph([ev(0), aware])


def test_aware_events_build_fine():
    e1 = EventRecord(datetime(2024, 1, 1, tzinfo=timezone.utc), "a", "b", "x")
    e2 = EventRecord(datetime(2024, 1, 2, tzinfo=timezone.utc), "a", "b", "x")
    tg = build_temporal_graph([e2, e1])
    assert tg.start_time == e1.timestamp and tg.end_time == e2.timestamp


def test_caller_events_not_mutated_by_build():
    events = [ev(1), ev(0)]
    snapshot = [(e.source, e.timestamp) for e in events]
    tg = build_temporal_graph(events)
    tg.events[0].source = "changed"
    assert [(e.source, e.timestamp) for e in events] == snapshot


def test_assign_node_attributes_returns_copy_with_types_and_roles():
    tg = build_temporal_graph([ev(0)])
    typed = assign_node_attributes(tg, {"a": "client", "b": "server"}, {"b": "web"})
    assert typed.graph.nodes["a"]["node_type"] == "client"
    assert typed.graph.nodes["b"]["role"] == "web"
    assert tg.graph.nodes["a"]["node_type"] == DEFAULT_NODE_TYPE  # original untouched


def test_assign_node_attributes_rejects_unknown_node_and_empty_type():
    tg = build_temporal_graph([ev(0)])
    with pytest.raises(InvalidGraphError):
        assign_node_attributes(tg, {"zzz": "client"})
    with pytest.raises(InvalidGraphError):
        assign_node_attributes(tg, {"a": ""})


def test_dataclass_views_of_graph_elements():
    tg = assign_node_attributes(
        build_temporal_graph([ev(0, protocol="tcp", bytes=7), ev(4)]), {"a": "client"}
    )
    node = get_graph_node(tg.graph, "a")
    assert (node.node_id, node.node_type, node.role) == ("a", "client", None)
    edge = get_graph_edge(tg.graph, "a", "b")
    assert edge.weight == 2 and edge.bytes_total == 7 and edge.protocol == "tcp"
    assert edge.last_seen - edge.first_seen == timedelta(seconds=4)
    with pytest.raises(InvalidGraphError):
        get_graph_edge(tg.graph, "b", "a")
    with pytest.raises(InvalidGraphError):
        get_graph_node(tg.graph, "nope")
