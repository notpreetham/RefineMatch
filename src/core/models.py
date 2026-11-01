"""Shared data models for RefineMatch.

These dataclasses are the data contract between all team members. Field names
and order follow the team blueprint (sections 4.1-4.7) exactly.

This file contains data definitions plus *construction-time validation only*;
there is no algorithmic logic. Validation raises the exceptions defined in
:mod:`src.core.exceptions`. ``validate()`` can be called again later because
dataclasses are mutable and can be changed after construction.

Graph attribute contract (stored on the ``networkx.DiGraph`` inside
:class:`TemporalGraph`) is documented in :mod:`src.graph.graph_builder`.

Dependency rule: this module imports only from ``src.core``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import networkx as nx

from src.core.config import MAX_PORT
from src.core.exceptions import (
    InvalidEventError,
    InvalidGraphError,
    InvalidRefinementInputError,
    RefineMatchError,
)


def is_timezone_aware(moment: datetime) -> bool:
    """Return ``True`` if ``moment`` carries a usable UTC offset.

    Python only allows ordering comparisons between two aware or two naive
    datetimes, so every module that compares timestamps uses this predicate to
    reject mixed input explicitly instead of failing with a bare ``TypeError``.
    """
    return moment.tzinfo is not None and moment.tzinfo.utcoffset(moment) is not None


# --------------------------------------------------------------------------- #
# Private validation helpers
# --------------------------------------------------------------------------- #

def _require_text(
    owner: str, field_name: str, value: Any, error: type[RefineMatchError]
) -> None:
    if not isinstance(value, str) or not value.strip():
        raise error(f"{owner}.{field_name} must be a non-empty string, got {value!r}")


def _require_optional_text(
    owner: str, field_name: str, value: Any, error: type[RefineMatchError]
) -> None:
    if value is not None:
        _require_text(owner, field_name, value, error)


def _require_optional_int(
    owner: str,
    field_name: str,
    value: Any,
    error: type[RefineMatchError],
    minimum: int,
    maximum: int | None = None,
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise error(f"{owner}.{field_name} must be an int or None, got {value!r}")
    if value < minimum or (maximum is not None and value > maximum):
        bound = f">= {minimum}" if maximum is None else f"in [{minimum}, {maximum}]"
        raise error(f"{owner}.{field_name} must be {bound}, got {value!r}")


def _require_optional_duration(
    owner: str, field_name: str, value: Any, error: type[RefineMatchError]
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error(f"{owner}.{field_name} must be a number or None, got {value!r}")
    if not math.isfinite(value) or value < 0:
        raise error(f"{owner}.{field_name} must be finite and >= 0, got {value!r}")


# --------------------------------------------------------------------------- #
# Telemetry and graph elements
# --------------------------------------------------------------------------- #

@dataclass
class EventRecord:
    """One normalised communication event (blueprint 4.1).

    ``timestamp`` may be timezone-aware or naive, but all events processed
    together must use the same kind. ``bytes`` and ``duration`` are optional;
    ``None`` means *unknown*, which is different from zero.
    """

    timestamp: datetime
    source: str
    destination: str
    event_type: str
    protocol: str | None = None
    source_port: int | None = None
    destination_port: int | None = None
    bytes: int | None = None
    duration: float | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise :class:`InvalidEventError` if any field is invalid."""
        if not isinstance(self.timestamp, datetime):
            raise InvalidEventError(
                f"EventRecord.timestamp must be a datetime, got {self.timestamp!r}"
            )
        for name in ("source", "destination", "event_type"):
            _require_text("EventRecord", name, getattr(self, name), InvalidEventError)
        _require_optional_text("EventRecord", "protocol", self.protocol, InvalidEventError)
        _require_optional_int(
            "EventRecord", "source_port", self.source_port, InvalidEventError, 0, MAX_PORT
        )
        _require_optional_int(
            "EventRecord",
            "destination_port",
            self.destination_port,
            InvalidEventError,
            0,
            MAX_PORT,
        )
        _require_optional_int("EventRecord", "bytes", self.bytes, InvalidEventError, 0)
        _require_optional_duration("EventRecord", "duration", self.duration, InvalidEventError)


@dataclass
class GraphNode:
    """Description of a graph node (blueprint 4.2).

    ``original_id`` records the pre-anonymisation identifier for traceability.
    It must never be used as a structural feature.
    """

    node_id: str
    node_type: str
    role: str | None = None
    original_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise :class:`InvalidGraphError` if any field is invalid."""
        _require_text("GraphNode", "node_id", self.node_id, InvalidGraphError)
        _require_text("GraphNode", "node_type", self.node_type, InvalidGraphError)
        _require_optional_text("GraphNode", "role", self.role, InvalidGraphError)
        _require_optional_text("GraphNode", "original_id", self.original_id, InvalidGraphError)


@dataclass
class GraphEdge:
    """Description of an aggregated directed edge (blueprint 4.3).

    ``weight`` is the number of underlying events. ``duration`` and
    ``bytes_total`` are sums over the events that reported a value, and are
    ``None`` when no event reported one.
    """

    source: str
    destination: str
    edge_type: str
    direction: str
    weight: int
    first_seen: datetime
    last_seen: datetime
    duration: float | None = None
    bytes_total: int | None = None
    protocol: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise :class:`InvalidGraphError` if any field is invalid."""
        for name in ("source", "destination", "edge_type", "direction"):
            _require_text("GraphEdge", name, getattr(self, name), InvalidGraphError)
        if isinstance(self.weight, bool) or not isinstance(self.weight, int) or self.weight < 1:
            raise InvalidGraphError(f"GraphEdge.weight must be an int >= 1, got {self.weight!r}")
        for name in ("first_seen", "last_seen"):
            if not isinstance(getattr(self, name), datetime):
                raise InvalidGraphError(
                    f"GraphEdge.{name} must be a datetime, got {getattr(self, name)!r}"
                )
        if is_timezone_aware(self.first_seen) != is_timezone_aware(self.last_seen):
            raise InvalidGraphError(
                "GraphEdge.first_seen and last_seen must both be timezone-aware or both naive"
            )
        if self.last_seen < self.first_seen:
            raise InvalidGraphError("GraphEdge.last_seen must not be earlier than first_seen")
        _require_optional_duration("GraphEdge", "duration", self.duration, InvalidGraphError)
        _require_optional_int("GraphEdge", "bytes_total", self.bytes_total, InvalidGraphError, 0)
        _require_optional_text("GraphEdge", "protocol", self.protocol, InvalidGraphError)


@dataclass
class TemporalGraph:
    """Aggregated graph plus the preserved event sequence (blueprint 4.4).

    ``graph`` holds aggregated relationships; ``events`` preserves the original
    temporal record. ``start_time``/``end_time`` are both ``None`` for an empty
    graph, otherwise the earliest and latest event timestamps.
    """

    graph: nx.DiGraph
    events: list[EventRecord]
    start_time: datetime | None
    end_time: datetime | None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise :class:`InvalidGraphError` if the container is inconsistent."""
        if not isinstance(self.graph, nx.DiGraph) or self.graph.is_multigraph():
            raise InvalidGraphError(
                "TemporalGraph.graph must be a networkx.DiGraph (multigraphs are not supported)"
            )
        if not isinstance(self.events, list):
            raise InvalidGraphError("TemporalGraph.events must be a list of EventRecord")
        if (self.start_time is None) != (self.end_time is None):
            raise InvalidGraphError(
                "TemporalGraph.start_time and end_time must both be set or both be None"
            )
        if self.start_time is not None and self.end_time is not None:
            if not isinstance(self.start_time, datetime) or not isinstance(self.end_time, datetime):
                raise InvalidGraphError("TemporalGraph start_time/end_time must be datetimes")
            if is_timezone_aware(self.start_time) != is_timezone_aware(self.end_time):
                raise InvalidGraphError(
                    "TemporalGraph start_time and end_time must have the same timezone-awareness"
                )
            if self.start_time > self.end_time:
                raise InvalidGraphError("TemporalGraph.start_time must not be after end_time")


@dataclass
class RefinementResult:
    """Outcome of Color Refinement (blueprint 4.5).

    ``node_colors`` maps node ID to color label. ``color_classes`` is the
    inverse mapping (color label to sorted node IDs). ``iterations`` counts the
    refinement rounds executed. ``stable`` is ``True`` only if a round was
    observed that did not split any class.
    """

    node_colors: dict[str, str]
    color_classes: dict[str, list[str]]
    iterations: int
    stable: bool

    def __post_init__(self) -> None:
        self.validate()

    def __getitem__(self, node: str) -> str:
        return self.node_colors[node]

    def __iter__(self):
        return iter(self.node_colors)

    def __contains__(self, node: object) -> bool:
        return node in self.node_colors

    def keys(self):
        return self.node_colors.keys()

    def values(self):
        return self.node_colors.values()

    def items(self):
        return self.node_colors.items()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return self.node_colors == other
        if isinstance(other, RefinementResult):
            return (
                self.node_colors == other.node_colors
                and self.color_classes == other.color_classes
                and self.iterations == other.iterations
                and self.stable == other.stable
            )
        return False

    def validate(self) -> None:
        """Raise :class:`InvalidRefinementInputError` if fields are inconsistent."""
        if isinstance(self.iterations, bool) or not isinstance(self.iterations, int):
            raise InvalidRefinementInputError(
                f"RefinementResult.iterations must be an int, got {self.iterations!r}"
            )
        if self.iterations < 0:
            raise InvalidRefinementInputError("RefinementResult.iterations must be >= 0")
        if not isinstance(self.stable, bool):
            raise InvalidRefinementInputError("RefinementResult.stable must be a bool")
        for node, color in self.node_colors.items():
            if not isinstance(node, str) or not isinstance(color, str):
                raise InvalidRefinementInputError(
                    "RefinementResult.node_colors must map str node IDs to str colors"
                )
        seen: dict[str, str] = {}
        for color, members in self.color_classes.items():
            for node in members:
                if node in seen:
                    raise InvalidRefinementInputError(
                        f"node {node!r} appears in more than one color class"
                    )
                seen[node] = color
        if seen != self.node_colors:
            raise InvalidRefinementInputError(
                "RefinementResult.color_classes is inconsistent with node_colors"
            )


# --------------------------------------------------------------------------- #
# Result containers owned by Members 2 and 3 (blueprint 4.6, 4.7)
#
# Blueprint section 5.1 places these in models.py. They are pure data holders
# here, with no validation, so their owners can add rules without touching
# any Member 1 code.
# --------------------------------------------------------------------------- #

@dataclass
class MatchResult:
    """Graph-matching outcome (blueprint 4.6; produced by Member 2)."""

    similarity: float
    node_mapping: dict[str, str]
    matched_nodes: list[str]
    unmatched_observed_nodes: list[str]
    unmatched_reference_nodes: list[str]
    individualization_count: int
    confidence: float


@dataclass
class ScoreResult:
    """Final scoring outcome (blueprint 4.7; produced by Member 3)."""

    structural_score: float
    temporal_score: float
    frequency_score: float
    attack_similarity: float
    benign_similarity: float
    contrastive_score: float
    risk_level: str
    #: Weighted final score in [0, 1] (added with Member 3 integration; defaults to 0.0).
    final_score: float = 0.0
