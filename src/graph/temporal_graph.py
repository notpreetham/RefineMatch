"""Temporal utilities over :class:`~src.core.models.TemporalGraph`.

Conventions (shared by all modules):

* **Ordering** - events are ordered by timestamp using a *stable* sort. Events
  with equal timestamps keep the relative order in which they appear in the
  input list.
* **Timezones** - timezone-aware timestamps are compared as instants (so
  ``12:00+01:00`` equals ``11:00Z``). Comparing aware with naive timestamps is
  ambiguous, so it is rejected with an explicit exception rather than a bare
  ``TypeError``.
* **Windows** - :func:`get_temporal_window` is half-open: ``start_time <= t <
  end_time``. Adjacent windows therefore never double-count an event. To
  include the very last event of a graph, use an ``end_time`` just after
  ``graph.end_time``.
* **Purity** - no function here mutates its inputs.
"""

from __future__ import annotations

import copy
from datetime import datetime

from src.core.exceptions import InvalidEventError, InvalidTimeWindowError
from src.core.models import EventRecord, TemporalGraph, is_timezone_aware


def _check_comparable(events: list[EventRecord]) -> None:
    """Raise if any timestamp is not a datetime or awareness is mixed."""
    kinds = set()
    for index, event in enumerate(events):
        if not isinstance(event, EventRecord) or not isinstance(event.timestamp, datetime):
            raise InvalidEventError(f"events[{index}] is not an EventRecord with a datetime timestamp")
        kinds.add(is_timezone_aware(event.timestamp))
    if len(kinds) > 1:
        raise InvalidEventError(
            "events mix timezone-aware and naive timestamps; normalise them before use"
        )


def _sorted_events(events: list[EventRecord]) -> list[EventRecord]:
    _check_comparable(events)
    return sorted(events, key=lambda event: event.timestamp)  # stable


def copy_temporal_graph(graph: TemporalGraph) -> TemporalGraph:
    """Return a deep, independent copy of ``graph`` (graph, attributes and events)."""
    return TemporalGraph(
        graph=copy.deepcopy(graph.graph),
        events=[copy.deepcopy(event) for event in graph.events],
        start_time=graph.start_time,
        end_time=graph.end_time,
    )


def get_ordered_events(graph: TemporalGraph) -> list[EventRecord]:
    """Return ``graph.events`` in chronological order as a new list.

    Equal timestamps keep their input order (stable sort). The graph is not
    modified. Raises :class:`InvalidEventError` for mixed aware/naive stamps.
    """
    return _sorted_events(graph.events)


def get_event_frequency(graph: TemporalGraph, source: str, destination: str) -> int:
    """Count events from ``source`` to ``destination`` (directional).

    ``(a, b)`` and ``(b, a)`` are counted separately. The preserved event list
    is the source of truth; for graphs made by ``build_temporal_graph`` this
    equals the edge's ``weight``. Unknown node pairs return ``0``.
    """
    return sum(
        1 for event in graph.events if event.source == source and event.destination == destination
    )


def get_temporal_window(
    events: list[EventRecord], start_time: datetime, end_time: datetime
) -> list[EventRecord]:
    """Return events with ``start_time <= timestamp < end_time``, chronologically.

    ``start_time == end_time`` yields an empty list. Raises
    :class:`InvalidTimeWindowError` if bounds are not datetimes, are reversed,
    or their timezone-awareness differs from the events'. The input list is not
    modified.
    """
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        raise InvalidTimeWindowError("window bounds must be datetime objects")
    if is_timezone_aware(start_time) != is_timezone_aware(end_time):
        raise InvalidTimeWindowError("window bounds must both be timezone-aware or both naive")
    if start_time > end_time:
        raise InvalidTimeWindowError("start_time must not be after end_time")
    ordered = _sorted_events(list(events))
    if ordered and is_timezone_aware(ordered[0].timestamp) != is_timezone_aware(start_time):
        raise InvalidTimeWindowError(
            "window bounds and event timestamps differ in timezone-awareness"
        )
    return [event for event in ordered if start_time <= event.timestamp < end_time]
