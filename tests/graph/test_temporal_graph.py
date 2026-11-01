"""Tests for src.graph.temporal_graph."""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.exceptions import InvalidEventError, InvalidTimeWindowError
from src.core.models import EventRecord
from src.graph.graph_builder import build_temporal_graph
from src.graph.temporal_graph import (
    copy_temporal_graph,
    get_event_frequency,
    get_ordered_events,
    get_temporal_window,
)

T0 = datetime(2024, 1, 1, 12, 0, 0)


def ev(seconds, src="a", dst="b", etype="x", base=T0):
    return EventRecord(base + timedelta(seconds=seconds), src, dst, etype)


def test_ordered_events_sorts_chronologically_without_mutating_input():
    events = [ev(30), ev(10), ev(20)]
    original = list(events)
    ordered = get_ordered_events(build_temporal_graph(events))
    assert [e.timestamp for e in ordered] == [T0 + timedelta(seconds=s) for s in (10, 20, 30)]
    assert events == original


def test_equal_timestamps_keep_input_order():
    events = [ev(5, "a", "b"), ev(5, "c", "d"), ev(1, "e", "f"), ev(5, "g", "h")]
    ordered = get_ordered_events(build_temporal_graph(events))
    assert [e.source for e in ordered] == ["e", "a", "c", "g"]


def test_equal_timestamps_not_reordered_by_name():
    events = [ev(5, "zulu", "b"), ev(5, "alpha", "b"), ev(5, "mike", "b")]
    ordered = get_ordered_events(build_temporal_graph(events))
    assert [e.source for e in ordered] == ["zulu", "alpha", "mike"]
    window = get_temporal_window(events, T0, T0 + timedelta(seconds=10))
    assert [e.source for e in window] == ["zulu", "alpha", "mike"]


def test_ordered_events_does_not_modify_graph_events():
    tg = build_temporal_graph([ev(2), ev(1)])
    get_ordered_events(tg)
    assert [e.timestamp.second for e in tg.events] == [2, 1]


def test_aware_timestamps_compared_as_instants():
    plus1 = timezone(timedelta(hours=1))
    late = EventRecord(datetime(2024, 1, 1, 12, 30, tzinfo=plus1), "a", "b", "x")  # 11:30Z
    early = EventRecord(datetime(2024, 1, 1, 11, 45, tzinfo=timezone.utc), "a", "b", "x")
    ordered = get_ordered_events(build_temporal_graph([early, late]))
    assert ordered[0] is not None and ordered[0].timestamp == late.timestamp


def test_mixed_awareness_rejected():
    tg = build_temporal_graph([ev(1)])
    tg.events.append(EventRecord(datetime(2024, 1, 1, tzinfo=timezone.utc), "a", "b", "x"))
    with pytest.raises(InvalidEventError):
        get_ordered_events(tg)


def test_empty_inputs():
    tg = build_temporal_graph([])
    assert get_ordered_events(tg) == []
    assert get_event_frequency(tg, "a", "b") == 0
    assert get_temporal_window([], T0, T0 + timedelta(seconds=1)) == []


def test_event_frequency_counts_repeats_and_is_directional():
    tg = build_temporal_graph([ev(1), ev(2), ev(3), ev(4, "b", "a"), ev(5, "a", "c")])
    assert get_event_frequency(tg, "a", "b") == 3
    assert get_event_frequency(tg, "b", "a") == 1
    assert get_event_frequency(tg, "a", "zzz") == 0
    assert tg.graph.edges["a", "b"]["weight"] == get_event_frequency(tg, "a", "b")


def test_window_is_half_open():
    events = [ev(0), ev(10), ev(20), ev(30)]
    got = get_temporal_window(events, T0 + timedelta(seconds=10), T0 + timedelta(seconds=30))
    assert [e.timestamp for e in got] == [T0 + timedelta(seconds=10), T0 + timedelta(seconds=20)]


def test_window_adjacent_windows_partition_events():
    events = [ev(s) for s in range(0, 40, 10)]
    first = get_temporal_window(events, T0, T0 + timedelta(seconds=20))
    second = get_temporal_window(events, T0 + timedelta(seconds=20), T0 + timedelta(seconds=40))
    assert len(first) + len(second) == len(events)


def test_window_zero_length_and_reversed():
    events = [ev(0), ev(10)]
    assert get_temporal_window(events, T0, T0) == []
    with pytest.raises(InvalidTimeWindowError):
        get_temporal_window(events, T0 + timedelta(seconds=5), T0)


def test_window_returns_chronological_and_leaves_input_untouched():
    events = [ev(20), ev(5), ev(10)]
    snapshot = list(events)
    got = get_temporal_window(events, T0, T0 + timedelta(seconds=100))
    assert [e.timestamp.second for e in got] == [5, 10, 20]
    assert events == snapshot


def test_window_timezone_checks():
    aware_events = [EventRecord(datetime(2024, 1, 1, tzinfo=timezone.utc), "a", "b", "x")]
    with pytest.raises(InvalidTimeWindowError):
        get_temporal_window(aware_events, T0, T0 + timedelta(seconds=1))
    with pytest.raises(InvalidTimeWindowError):
        get_temporal_window([], T0, datetime(2025, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(InvalidTimeWindowError):
        get_temporal_window([], "x", T0)
    start = datetime(2023, 12, 31, 23, 0, tzinfo=timezone.utc)
    assert len(get_temporal_window(aware_events, start, start + timedelta(hours=2))) == 1


def test_copy_temporal_graph_is_independent():
    tg = build_temporal_graph([ev(1), ev(2)])
    clone = copy_temporal_graph(tg)
    clone.graph.edges["a", "b"]["edge_types"]["x"] = 99
    clone.events[0].source = "zzz"
    assert tg.graph.edges["a", "b"]["edge_types"]["x"] == 2
    assert tg.events[0].source == "a"
