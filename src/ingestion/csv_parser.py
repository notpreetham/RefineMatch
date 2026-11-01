"""CSV telemetry ingestion into :class:`~src.core.models.EventRecord`.

Required columns: ``timestamp, source, destination, event_type``.
Optional columns: ``protocol, source_port, destination_port, bytes, duration``
(missing columns or empty cells become ``None``). Header names are matched
case-insensitively; a UTF-8 BOM is tolerated. Timestamps may be ISO-8601 (a
trailing ``Z`` is accepted) or numeric Unix epoch seconds (read as UTC).

Every problem raises :class:`InvalidEventError` naming the file/row, instead
of silently skipping data.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from src.core.exceptions import InvalidEventError
from src.core.models import EventRecord

REQUIRED_COLUMNS = ("timestamp", "source", "destination", "event_type")
OPTIONAL_COLUMNS = (
    "protocol", "source_port", "destination_port", "bytes", "duration")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def parse_timestamp(text: str) -> datetime:
    """Parse an ISO-8601 or epoch-seconds timestamp."""
    value = (text or "").strip()
    if not value:
        raise InvalidEventError("empty timestamp")
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        pass
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
    except ValueError as exc:
        raise InvalidEventError(f"unparseable timestamp {text!r}") from exc


def _optional(row: Mapping[str, str], name: str):
    value = row.get(name)
    return None if value is None or str(value).strip() == "" else str(value).strip()


def _int(value: str | None, name: str) -> int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise InvalidEventError(f"{name} is not a number: {value!r}") from exc
    if number != int(number):
        raise InvalidEventError(f"{name} must be a whole number, got {value!r}")
    return int(number)


def _float(value: str | None, name: str) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise InvalidEventError(f"{name} is not a number: {value!r}") from exc


def parse_event_rows(
    rows: Iterable[Mapping[str, str]], origin: str = "<rows>", first_line: int = 2
) -> list[EventRecord]:
    """Convert dict rows (already lower-case keys) to validated events."""
    events: list[EventRecord] = []
    for offset, row in enumerate(rows):
        where = f"{origin}, line {first_line + offset}"
        try:
            events.append(EventRecord(
                timestamp=parse_timestamp(row.get("timestamp", "")),
                source=(row.get("source") or "").strip(),
                destination=(row.get("destination") or "").strip(),
                event_type=(row.get("event_type") or "").strip(),
                protocol=_optional(row, "protocol"),
                source_port=_int(_optional(row, "source_port"), "source_port"),
                destination_port=_int(_optional(row, "destination_port"), "destination_port"),
                bytes=_int(_optional(row, "bytes"), "bytes"),
                duration=_float(_optional(row, "duration"), "duration"),
            ))
        except InvalidEventError as exc:
            raise InvalidEventError(f"{where}: {exc}") from exc
    return events


def load_events_from_csv(path: str, column_map: Mapping[str, str] | None = None) -> list[EventRecord]:
    """Load events from a CSV file.

    ``column_map`` optionally maps this project's column names to the file's
    column names (e.g. ``{"source": "src_ip"}``). Mixed timezone-aware and
    naive timestamps are rejected here so the error points at the data file.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    reverse = {v.strip().lower(): k for k, v in (column_map or {}).items()}
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise InvalidEventError(f"{file_path}: file is empty or has no header row")
        names = {}
        for raw in reader.fieldnames:
            key = (raw or "").strip().lower()
            names[raw] = reverse.get(key, key)
        missing = [c for c in REQUIRED_COLUMNS if c not in names.values()]
        if missing:
            raise InvalidEventError(
                f"{file_path}: missing required column(s) {missing}; found {sorted(names.values())}")
        rows = [{names[k]: v for k, v in row.items() if k in names} for row in reader]
    events = parse_event_rows(rows, origin=str(file_path))
    kinds = {e.timestamp.tzinfo is not None for e in events}
    if len(kinds) > 1:
        raise InvalidEventError(f"{file_path}: mixes timezone-aware and naive timestamps")
    return events


def events_to_csv(events: list[EventRecord], path: str) -> None:
    """Write events to CSV in the format :func:`load_events_from_csv` reads."""
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(ALL_COLUMNS)
        for e in events:
            writer.writerow([e.timestamp.isoformat(), e.source, e.destination, e.event_type,
                             e.protocol or "", "" if e.source_port is None else e.source_port,
                             "" if e.destination_port is None else e.destination_port,
                             "" if e.bytes is None else e.bytes,
                             "" if e.duration is None else e.duration])
