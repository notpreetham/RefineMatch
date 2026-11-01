"""Temporal-order, event-frequency and temporal-consistency scores, all in [0, 1].

Everything is identity- and clock-independent: only relative order and
proportions are used, so shifting all timestamps or renaming hosts changes
nothing.

* ORDER similarity: first-occurrence order of event types in each event list,
  compared with a Dice-normalised longest common subsequence
  (2*LCS/(len_a+len_b)). Two empty lists give 1.0; one empty gives 0.0.
* FREQUENCY similarity: mean of (a) 1 - total-variation distance between the
  event-type distributions and (b) the same between sorted per-edge weight
  proportions (zero-padded). Proportions, not raw counts, so uniformly higher
  traffic volume is not penalised; shape changes are.
* TEMPORAL CONSISTENCY: over pairs of mapped reference edges whose first_seen
  times differ, the share whose observed counterparts have the same order.
  No mapped edges -> 0.0. Mapped edges but no comparable pair -> 0.5 (neutral:
  no evidence either way).
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations

from src.core.exceptions import InvalidEventError
from src.core.models import EventRecord, MatchResult, TemporalGraph


def _chronological(events: list[EventRecord]) -> list[EventRecord]:
    try:
        return sorted(events, key=lambda e: e.timestamp)
    except TypeError as exc:
        raise InvalidEventError("events mix timezone-aware and naive timestamps") from exc


def _first_occurrence_order(events: list[EventRecord]) -> list[str]:
    seen: list[str] = []
    for event in _chronological(events):
        if event.event_type not in seen:
            seen.append(event.event_type)
    return seen


def _lcs_length(a: list[str], b: list[str]) -> int:
    row = [0] * (len(b) + 1)
    for x in a:
        previous = 0
        for j, y in enumerate(b, start=1):
            current = row[j]
            row[j] = previous + 1 if x == y else max(row[j], row[j - 1])
            previous = current
    return row[-1]


def calculate_order_similarity(
    reference_events: list[EventRecord], observed_events: list[EventRecord]
) -> float:
    """Dice-normalised LCS of first-occurrence event-type order."""
    a, b = _first_occurrence_order(reference_events), _first_occurrence_order(observed_events)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return 2.0 * _lcs_length(a, b) / (len(a) + len(b))


def _tv_similarity(p: list[float], q: list[float]) -> float:
    size = max(len(p), len(q))
    p, q = p + [0.0] * (size - len(p)), q + [0.0] * (size - len(q))
    return 1.0 - 0.5 * sum(abs(x - y) for x, y in zip(p, q))


def _proportions(counter: Counter) -> dict[str, float]:
    total = sum(counter.values())
    return {k: v / total for k, v in counter.items()} if total else {}


def calculate_frequency_similarity(reference: TemporalGraph, observed: TemporalGraph) -> float:
    """Frequency-shape similarity (see module docstring)."""
    if not reference.events and not observed.events:
        return 1.0
    if not reference.events or not observed.events:
        return 0.0
    ref_types = _proportions(Counter(e.event_type for e in reference.events))
    obs_types = _proportions(Counter(e.event_type for e in observed.events))
    keys = set(ref_types) | set(obs_types)
    type_sim = 1.0 - 0.5 * sum(abs(ref_types.get(k, 0.0) - obs_types.get(k, 0.0)) for k in keys)

    def weight_profile(graph: TemporalGraph) -> list[float]:
        weights = sorted((a["weight"] for _, _, a in graph.graph.edges(data=True)), reverse=True)
        total = sum(weights)
        return [w / total for w in weights] if total else []

    weight_sim = _tv_similarity(weight_profile(reference), weight_profile(observed))
    return max(0.0, min(1.0, 0.5 * (type_sim + weight_sim)))


def calculate_temporal_consistency(
    reference: TemporalGraph, observed: TemporalGraph, match: MatchResult
) -> float:
    """Share of order-comparable mapped edge pairs whose order is preserved."""
    mapped = []
    for u, w, attrs in reference.graph.edges(data=True):
        mu, mw = match.node_mapping.get(u), match.node_mapping.get(w)
        if mu is not None and mw is not None and observed.graph.has_edge(mu, mw):
            mapped.append((attrs["first_seen"], observed.graph.edges[mu, mw]["first_seen"]))
    if not mapped:
        return 0.0
    agree = total = 0
    for (r1, o1), (r2, o2) in combinations(mapped, 2):
        if r1 == r2:
            continue
        total += 1
        agree += (r1 < r2) == (o1 < o2) and o1 != o2
    return 0.5 if total == 0 else agree / total
