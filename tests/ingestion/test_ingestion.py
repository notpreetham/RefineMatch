"""Tests for csv_parser, dataset_loader and synthetic_generator."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.exceptions import InvalidEventError
from src.ingestion.csv_parser import events_to_csv, load_events_from_csv, parse_timestamp
from src.ingestion.dataset_loader import load_dataset
from src.ingestion.synthetic_generator import (
    BENIGN_PATTERNS, PATTERN_NAMES, SUSPICIOUS_PATTERNS, generate_synthetic_events,
    generate_synthetic_graph, generate_synthetic_instance, pattern_category)

HEADER = "timestamp,source,destination,event_type,protocol,source_port,destination_port,bytes,duration\n"


def write(text, name="t.csv", encoding="utf-8"):
    folder = tempfile.mkdtemp()
    path = Path(folder) / name
    path.write_text(text, encoding=encoding)
    return str(path)


def test_parse_full_row_and_optional_none():
    path = write(HEADER + "2024-01-01T10:00:00Z,a,b,http,tcp,1234,80,500,1.5\n"
                 "2024-01-01T10:00:01+00:00,b,a,reply,,,,,\n")
    e1, e2 = load_events_from_csv(path)
    assert e1.timestamp == datetime(2024, 1, 1, 10, tzinfo=timezone.utc)
    assert (e1.protocol, e1.source_port, e1.destination_port, e1.bytes, e1.duration) == ("tcp", 1234, 80, 500, 1.5)
    assert (e2.protocol, e2.source_port, e2.bytes, e2.duration) == (None, None, None, None)


def test_only_required_columns_bom_case_and_epoch():
    path = write("\ufeffTimestamp,SOURCE,Destination,Event_Type\n1704103200,a,b,x\n", encoding="utf-8")
    (event,) = load_events_from_csv(path)
    assert event.timestamp == datetime(2024, 1, 1, 10, tzinfo=timezone.utc) and event.bytes is None


def test_column_map_for_nonstandard_files():
    path = write("time,src_ip,dst_ip,kind\n2024-01-01T00:00:00,a,b,x\n")
    (event,) = load_events_from_csv(path, {"timestamp": "time", "source": "src_ip",
                                           "destination": "dst_ip", "event_type": "kind"})
    assert (event.source, event.destination, event.event_type) == ("a", "b", "x")


@pytest.mark.parametrize("body,fragment", [
    ("timestamp,source,destination\n2024-01-01,a,b\n", "missing required column"),
    (HEADER + "not-a-date,a,b,x,,,,,\n", "line 2"),
    (HEADER + "2024-01-01T00:00:00,a,b,x,,,,-5,\n", "bytes"),
    (HEADER + "2024-01-01T00:00:00,a,b,x,,70000,,,\n", "source_port"),
    (HEADER + "2024-01-01T00:00:00,a,b,x,,abc,,,\n", "source_port"),
    (HEADER + "2024-01-01T00:00:00,a,b,x,,,,,nan\n", "duration"),
    (HEADER + "2024-01-01T00:00:00,,b,x,,,,,\n", "source"),
    (HEADER + "2024-01-01T00:00:00,a,b,x,,,,,\n2024-01-01T00:00:00Z,a,b,x,,,,,\n", "timezone"),
    ("", "empty"),
])
def test_malformed_csv_raises_descriptive_error(body, fragment):
    with pytest.raises(InvalidEventError, match=fragment):
        load_events_from_csv(write(body))


def test_missing_file_and_header_only():
    with pytest.raises(FileNotFoundError):
        load_events_from_csv("definitely_not_here.csv")
    assert load_events_from_csv(write(HEADER)) == []


def test_parse_timestamp_variants():
    assert parse_timestamp("2024-01-01").year == 2024
    with pytest.raises(InvalidEventError):
        parse_timestamp("   ")


def test_csv_roundtrip():
    events = generate_synthetic_events("normal_database_access", 2)
    path = write("")
    events_to_csv(events, path)
    assert load_events_from_csv(path) == events


def test_dataset_loader_adapters():
    assert load_dataset("synthetic", "c2_like:3", None) == generate_synthetic_events("c2_like", 3)
    assert load_dataset("synthetic", "c2_like") == generate_synthetic_events("c2_like", 0)
    path = write(HEADER + "2024-01-01T00:00:00,a,b,x,,,,,\n")
    assert len(load_dataset("generic_csv", path)) == len(load_dataset("CSV", path)) == 1
    with pytest.raises(InvalidEventError, match="not implemented"):
        load_dataset("streamspot", path)
    with pytest.raises(InvalidEventError, match="unknown dataset"):
        load_dataset("nope", path)
    with pytest.raises(InvalidEventError):
        load_dataset("synthetic", "c2_like:x")


def test_generator_is_deterministic_and_seed_sensitive():
    for name in PATTERN_NAMES:
        assert generate_synthetic_events(name, 5) == generate_synthetic_events(name, 5)
        assert generate_synthetic_events(name, 5) != generate_synthetic_events(name, 6)


def test_generator_topology_is_seed_invariant_but_identities_change():
    a, b = generate_synthetic_graph("external_to_internal_chain", 1), generate_synthetic_graph("external_to_internal_chain", 2)
    roles = lambda tg: sorted((tg.graph.nodes[u]["role"], tg.graph.nodes[v]["role"]) for u, v in tg.graph.edges)
    assert roles(a) == roles(b)
    assert not set(a.graph.nodes) & set(b.graph.nodes)


def test_generator_events_are_valid_sorted_and_timezone_aware():
    for name in PATTERN_NAMES:
        events = generate_synthetic_events(name, 0)
        assert events and all(e.timestamp.tzinfo for e in events)
        assert [e.timestamp for e in events] == sorted(e.timestamp for e in events)


def test_first_seen_order_of_relations_is_stable_across_seeds():
    for seed in range(10):
        tg = generate_synthetic_graph("lateral_movement_like", seed)
        by_role = {(tg.graph.nodes[u]["role"], tg.graph.nodes[v]["role"]): a["first_seen"]
                   for u, v, a in tg.graph.edges(data=True)}
        order = sorted(by_role, key=by_role.get)
        assert order == [("ws", "h1"), ("h1", "h2"), ("h2", "h3"), ("h3", "fs")]


def test_categories_and_typed_graph():
    assert set(BENIGN_PATTERNS) | set(SUSPICIOUS_PATTERNS) == set(PATTERN_NAMES)
    assert len(PATTERN_NAMES) == 8 and pattern_category("c2_like") == "suspicious"
    g = generate_synthetic_graph("normal_database_access", 0)
    types = {a["role"]: a["node_type"] for _, a in g.graph.nodes(data=True)}
    assert types == {"app": "application_server", "db": "database", "admin": "client"}


def test_unknown_pattern_and_bad_seed():
    with pytest.raises(InvalidEventError):
        generate_synthetic_events("nope", 0)
    with pytest.raises(InvalidEventError):
        generate_synthetic_events("c2_like", "0")
    events, names = generate_synthetic_instance("scanning_like", 1)
    assert len(names) == 9 and len(set(names.values())) == 9
