"""Tests for src.core.models, config and exceptions."""

import ast
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import pytest

from src.core import config
from src.core.exceptions import (
    InvalidEventError,
    InvalidGraphError,
    InvalidRefinementInputError,
    RefineMatchError,
)
from src.core.models import (
    EventRecord,
    GraphEdge,
    GraphNode,
    MatchResult,
    RefinementResult,
    ScoreResult,
    TemporalGraph,
    is_timezone_aware,
)

T0 = datetime(2024, 1, 1, 12, 0, 0)
UTC_T0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_event_minimal_construction_uses_none_defaults():
    ev = EventRecord(T0, "a", "b", "connect")
    assert (ev.protocol, ev.source_port, ev.destination_port, ev.bytes, ev.duration) == (
        None, None, None, None, None,
    )


def test_event_full_construction_and_zero_values_allowed():
    ev = EventRecord(UTC_T0, "a", "b", "http", "tcp", 0, 65535, 0, 0.0)
    assert ev.bytes == 0 and ev.duration == 0.0 and ev.destination_port == 65535


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timestamp": "2024-01-01"},
        {"source": ""},
        {"destination": "   "},
        {"event_type": ""},
        {"source": 5},
        {"protocol": ""},
        {"source_port": -1},
        {"destination_port": 65536},
        {"source_port": True},
        {"bytes": -1},
        {"bytes": 1.5},
        {"duration": -0.1},
        {"duration": float("nan")},
        {"duration": float("inf")},
    ],
)
def test_event_invalid_values_rejected(kwargs):
    base = dict(timestamp=T0, source="a", destination="b", event_type="x")
    base.update(kwargs)
    with pytest.raises(InvalidEventError):
        EventRecord(**base)


def test_event_revalidate_catches_mutation_after_construction():
    ev = EventRecord(T0, "a", "b", "x")
    ev.bytes = -5
    with pytest.raises(InvalidEventError):
        ev.validate()


def test_timezone_awareness_helper():
    assert is_timezone_aware(UTC_T0)
    assert not is_timezone_aware(T0)


def test_graph_node_valid_and_invalid():
    node = GraphNode("n1", "server")
    assert node.role is None and node.original_id is None
    assert GraphNode("n1", "server", "web", "10.0.0.1").original_id == "10.0.0.1"
    with pytest.raises(InvalidGraphError):
        GraphNode("", "server")
    with pytest.raises(InvalidGraphError):
        GraphNode("n1", "")
    with pytest.raises(InvalidGraphError):
        GraphNode("n1", "server", role="")


def test_graph_edge_valid_and_invalid():
    edge = GraphEdge("a", "b", "dns", "source_to_destination", 3, T0, T0)
    assert edge.duration is None and edge.bytes_total is None and edge.protocol is None
    with pytest.raises(InvalidGraphError):
        GraphEdge("a", "b", "dns", "d", 0, T0, T0)
    with pytest.raises(InvalidGraphError):
        GraphEdge("a", "b", "dns", "d", 1, UTC_T0, datetime(2020, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(InvalidGraphError):
        GraphEdge("a", "b", "dns", "d", 1, T0, UTC_T0)  # mixed awareness
    with pytest.raises(InvalidGraphError):
        GraphEdge("a", "b", "dns", "d", 1, T0, T0, bytes_total=-1)


def test_temporal_graph_valid_and_invalid():
    tg = TemporalGraph(nx.DiGraph(), [], None, None)
    assert tg.start_time is None
    TemporalGraph(nx.DiGraph(), [], T0, T0)
    with pytest.raises(InvalidGraphError):
        TemporalGraph(nx.Graph(), [], None, None)
    with pytest.raises(InvalidGraphError):
        TemporalGraph(nx.MultiDiGraph(), [], None, None)
    with pytest.raises(InvalidGraphError):
        TemporalGraph(nx.DiGraph(), [], T0, None)
    with pytest.raises(InvalidGraphError):
        TemporalGraph(nx.DiGraph(), [], datetime(2025, 1, 1), T0)
    with pytest.raises(InvalidGraphError):
        TemporalGraph(nx.DiGraph(), (), None, None)


def test_refinement_result_valid_and_invalid():
    ok = RefinementResult({"a": "c1", "b": "c1"}, {"c1": ["a", "b"]}, 2, True)
    assert ok.iterations == 2
    RefinementResult({}, {}, 0, True)
    with pytest.raises(InvalidRefinementInputError):
        RefinementResult({"a": "c1"}, {"c1": ["a", "b"]}, 1, True)
    with pytest.raises(InvalidRefinementInputError):
        RefinementResult({"a": "c1"}, {"c1": ["a"], "c2": ["a"]}, 1, True)
    with pytest.raises(InvalidRefinementInputError):
        RefinementResult({}, {}, -1, True)
    with pytest.raises(InvalidRefinementInputError):
        RefinementResult({}, {}, 0, "yes")


def test_match_and_score_results_are_plain_containers():
    m = MatchResult(0.5, {"a": "b"}, ["a"], [], [], 0, 0.4)
    s = ScoreResult(0.1, 0.2, 0.3, 0.4, 0.5, -0.1, "low")
    assert m.node_mapping == {"a": "b"} and s.risk_level == "low"


def test_exception_hierarchy():
    for exc in (InvalidEventError, InvalidGraphError, InvalidRefinementInputError):
        assert issubclass(exc, RefineMatchError) and issubclass(exc, ValueError)


def test_config_values_present_and_sane():
    assert config.DEFAULT_MAX_REFINEMENT_ITERATIONS > 0
    assert config.DEFAULT_IDENTITY_PREFIX
    assert config.DEFAULT_TEMPORAL_WINDOW_SECONDS > 0
    assert 0 <= config.DEFAULT_MATCH_THRESHOLD <= 1
    assert 0 <= config.DEFAULT_RISK_THRESHOLD <= 1
    assert 0 <= config.DEFAULT_AMBIGUITY_THRESHOLD <= 1
    assert config.DEFAULT_MAX_INDIVIDUALIZATIONS >= 0


def test_core_modules_do_not_import_higher_layers():
    core_dir = Path(__file__).resolve().parents[1] / "src" / "core"
    forbidden = ("graph", "refinement", "matching", "scoring", "evaluation",
                 "ingestion", "explanation", "robustness")
    for path in core_dir.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if parts[0] == "src" and len(parts) > 1:
                    assert parts[1] not in forbidden, f"{path.name} imports {node.module}"
