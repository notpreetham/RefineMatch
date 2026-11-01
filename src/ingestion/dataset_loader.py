"""Dataset adapters. Implemented: ``synthetic`` and generic CSV.

``load_dataset("synthetic", "c2_like")`` or ``"c2_like:7"`` (pattern:seed).
``load_dataset("csv", path)`` / ``"generic_csv"`` use the CSV parser; an optional
``column_map`` renames columns of non-standard files.

NOT implemented (no dataset was available to validate an adapter against, and
guessing a schema would risk silently wrong results): StreamSpot, DARPA
TC/OpTC, and network-flow datasets. Requesting them raises a clear error.
To add one, write a function returning ``list[EventRecord]`` and register it
in ``ADAPTERS``; the graph engine needs no changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from src.core.exceptions import InvalidEventError
from src.core.models import EventRecord
from src.ingestion.csv_parser import load_events_from_csv
from src.ingestion.synthetic_generator import generate_synthetic_events

PLANNED_ADAPTERS = ("streamspot", "darpa_tc", "optc", "netflow")


def _synthetic(spec: str, column_map=None) -> list[EventRecord]:
    name, _, seed_text = spec.partition(":")
    try:
        seed = int(seed_text) if seed_text else 0
    except ValueError as exc:
        raise InvalidEventError(f"synthetic seed must be an int, got {seed_text!r}") from exc
    return generate_synthetic_events(name.strip(), seed)


def _csv(path: str, column_map: Mapping[str, str] | None = None) -> list[EventRecord]:
    return load_events_from_csv(path, column_map)


ADAPTERS: dict[str, Callable[..., list[EventRecord]]] = {
    "synthetic": _synthetic, "csv": _csv, "generic_csv": _csv}


def load_dataset(
    dataset_name: str, path: str, column_map: Mapping[str, str] | None = None
) -> list[EventRecord]:
    """Load events from a named source (see module docstring)."""
    key = (dataset_name or "").strip().lower()
    if key in ADAPTERS:
        return ADAPTERS[key](path, column_map)
    if key in PLANNED_ADAPTERS:
        raise InvalidEventError(
            f"adapter {dataset_name!r} is planned but not implemented; export the data to CSV "
            f"and use dataset 'csv' (see {__name__} docstring)")
    raise InvalidEventError(f"unknown dataset {dataset_name!r}; supported: {sorted(ADAPTERS)}")
