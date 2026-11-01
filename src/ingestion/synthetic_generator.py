"""Deterministic SYNTHETIC telemetry for repeatable experiments.

HONESTY NOTE: everything here is synthetic. The "suspicious-like" patterns are
illustrative behavioural SHAPES (fan-out probing, periodic beaconing, multi-hop
chains, ...). They are NOT recordings of real attacks, are not validated
against real malware or traffic, and the ATT&CK identifiers are loose
analogies for orientation only. Results on this data demonstrate that the
pipeline works; they are not evidence of real-world detection performance.

Seeds change identities (host names/IPs), event counts (+-20%), inter-event
gaps and byte volumes, but not the topology. Same pattern + same seed gives
byte-identical events across runs and machines.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.core.config import (
    DEFAULT_MIN_PORT,
    DEFAULT_SYNTHETIC_BASE_TIME,
    MAX_PORT,
    SYNTHETIC_BYTE_VARIANCE_RATIO,
    SYNTHETIC_COUNT_JITTER_BOUNDS,
    SYNTHETIC_DURATION_BOUNDS,
    SYNTHETIC_DURATION_ROUNDING_DIGITS,
    SYNTHETIC_INTERVAL_JITTER_BOUNDS,
    SYNTHETIC_START_JITTER_SECONDS,
)
from src.core.exceptions import InvalidEventError
from src.core.models import EventRecord, TemporalGraph
from src.graph.graph_builder import assign_node_attributes, build_temporal_graph

BASE_TIME = DEFAULT_SYNTHETIC_BASE_TIME
BENIGN, SUSPICIOUS = "benign", "suspicious"


@dataclass(frozen=True)
class EdgeSpec:
    """One communication relation: ``count`` events every ~``interval`` seconds."""

    source: str
    destination: str
    event_type: str
    count: int
    interval: float
    start: float
    protocol: str = "tcp"
    port: int = 443
    mean_bytes: int = 2000


@dataclass(frozen=True)
class PatternSpec:
    category: str
    name: str
    description: str
    technique: str
    nodes: dict[str, str]  # role -> node_type
    edges: tuple[EdgeSpec, ...]


def _e(s, d, t, count, interval, start, proto="tcp", port=443, b=2000):
    return EdgeSpec(s, d, t, count, interval, start, proto, port, b)


PATTERN_SPECS: dict[str, PatternSpec] = {
    "normal_client_server": PatternSpec(
        BENIGN, "Normal client-server exchange", "A client repeatedly requests a server.", "",
        {"client": "client", "server": "server"},
        (_e("client", "server", "http_request", 12, 20, 0, port=80),
         _e("server", "client", "http_response", 12, 20, 12, port=80, b=8000))),
    "normal_database_access": PatternSpec(
        BENIGN, "Normal application database access", "An app queries a database; rare admin access.", "",
        {"app": "application_server", "db": "database", "admin": "client"},
        (_e("app", "db", "sql_query", 20, 15, 0, port=5432),
         _e("db", "app", "sql_result", 20, 15, 12, port=5432, b=6000),
         _e("admin", "db", "sql_admin", 2, 300, 60, port=5432))),
    "multi_server_application": PatternSpec(
        BENIGN, "Multi-tier web application", "Client -> web -> two app servers -> database.", "",
        {"client": "client", "web": "server", "app1": "application_server",
         "app2": "application_server", "db": "database"},
        (_e("client", "web", "http_request", 15, 10, 0, port=80),
         _e("web", "app1", "rpc_call", 15, 10, 14, port=8080),
         _e("web", "app2", "rpc_call", 15, 10, 28, port=8080),
         _e("app1", "db", "sql_query", 10, 12, 42, port=5432),
         _e("app2", "db", "sql_query", 10, 12, 56, port=5432))),
    "external_to_internal_chain": PatternSpec(
        SUSPICIOUS, "External-to-internal multi-hop chain (synthetic)",
        "External source reaches an edge server, then hops inward to a database.",
        "T1190 (analogy only)",
        {"ext": "external", "dmz": "server", "int1": "server", "int2": "server", "db": "database"},
        (_e("ext", "dmz", "http_request", 5, 30, 0, port=80),
         _e("dmz", "int1", "remote_exec", 3, 60, 40, port=445),
         _e("int1", "int2", "remote_exec", 3, 60, 110, port=445),
         _e("int2", "db", "sql_query", 4, 45, 180, port=5432))),
    "lateral_movement_like": PatternSpec(
        SUSPICIOUS, "Lateral-movement-like host chain (synthetic)",
        "A workstation logs into a host which logs into further hosts, ending at a file server.",
        "T1021 (analogy only)",
        {"ws": "client", "h1": "server", "h2": "server", "h3": "server", "fs": "fileserver"},
        (_e("ws", "h1", "remote_login", 2, 120, 0, port=3389),
         _e("h1", "h2", "remote_login", 2, 120, 150, port=3389),
         _e("h2", "h3", "remote_login", 2, 120, 300, port=3389),
         _e("h3", "fs", "smb_access", 6, 20, 420, port=445))),
    "scanning_like": PatternSpec(
        SUSPICIOUS, "Scanning-like fan-out (synthetic)",
        "One source probes many targets once each.", "T1046 (analogy only)",
        {"scanner": "external", **{f"t{i}": "server" for i in range(1, 9)}},
        tuple(_e("scanner", f"t{i}", "probe", 1, 1, 10.0 * i, b=60) for i in range(1, 9))),
    "c2_like": PatternSpec(
        SUSPICIOUS, "Command-and-control-like beaconing (synthetic)",
        "An internal host beacons periodically to an external host that rarely replies.",
        "T1071 (analogy only)",
        {"host": "client", "c2": "external"},
        (_e("host", "c2", "beacon", 40, 60, 0, b=300),
         _e("c2", "host", "tasking", 3, 600, 70, b=1500))),
    "data_staging_like": PatternSpec(
        SUSPICIOUS, "Data-staging-like fan-in then upload (synthetic)",
        "Several hosts send files to one staging host, which uploads externally.",
        "T1074/T1041 (analogy only)",
        {"src1": "client", "src2": "client", "src3": "client", "stage": "server", "ext": "external"},
        (_e("src1", "stage", "file_transfer", 5, 30, 0, port=445, b=50000),
         _e("src2", "stage", "file_transfer", 5, 30, 15, port=445, b=50000),
         _e("src3", "stage", "file_transfer", 5, 30, 30, port=445, b=50000),
         _e("stage", "ext", "bulk_upload", 4, 20, 200, b=400000))),
}

PATTERN_NAMES: tuple[str, ...] = tuple(PATTERN_SPECS)
BENIGN_PATTERNS = tuple(n for n, s in PATTERN_SPECS.items() if s.category == BENIGN)
SUSPICIOUS_PATTERNS = tuple(n for n, s in PATTERN_SPECS.items() if s.category == SUSPICIOUS)


def _spec(pattern_name: str) -> PatternSpec:
    if pattern_name not in PATTERN_SPECS:
        raise InvalidEventError(f"unknown pattern {pattern_name!r}; choose from {list(PATTERN_NAMES)}")
    return PATTERN_SPECS[pattern_name]


def _host_names(spec: PatternSpec, rng: random.Random) -> dict[str, str]:
    names, used = {}, set()
    for role, node_type in spec.nodes.items():
        while True:
            ip = (f"203.0.113.{rng.randint(1, 250)}" if node_type == "external"
                  else f"10.{rng.randint(0, 250)}.{rng.randint(0, 250)}.{rng.randint(1, 250)}")
            if ip not in used:
                used.add(ip)
                names[role] = ip
                break
    return names


def generate_synthetic_instance(pattern_name: str, seed: int) -> tuple[list[EventRecord], dict[str, str]]:
    """Return ``(events, role -> host name)`` for a pattern and seed."""
    spec = _spec(pattern_name)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise InvalidEventError("seed must be an int")
    rng = random.Random(f"refinematch:{pattern_name}:{seed}")
    names = _host_names(spec, rng)
    events: list[EventRecord] = []
    for edge in spec.edges:
        n = max(1, round(edge.count * rng.uniform(*SYNTHETIC_COUNT_JITTER_BOUNDS)))
        t = edge.start + rng.uniform(*SYNTHETIC_START_JITTER_SECONDS)
        for _ in range(n):
            events.append(EventRecord(
                timestamp=BASE_TIME + timedelta(seconds=t),
                source=names[edge.source], destination=names[edge.destination],
                event_type=edge.event_type, protocol=edge.protocol,
                source_port=rng.randint(DEFAULT_MIN_PORT, MAX_PORT), destination_port=edge.port,
                bytes=max(1, int(rng.gauss(edge.mean_bytes, edge.mean_bytes * SYNTHETIC_BYTE_VARIANCE_RATIO))),
                duration=round(rng.uniform(*SYNTHETIC_DURATION_BOUNDS), SYNTHETIC_DURATION_ROUNDING_DIGITS)))
            t += edge.interval * rng.uniform(*SYNTHETIC_INTERVAL_JITTER_BOUNDS)
    events.sort(key=lambda e: e.timestamp)
    return events, names


def generate_synthetic_events(pattern_name: str, seed: int) -> list[EventRecord]:
    """Deterministic synthetic events for one of :data:`PATTERN_NAMES`."""
    return generate_synthetic_instance(pattern_name, seed)[0]


def generate_synthetic_graph(pattern_name: str, seed: int) -> TemporalGraph:
    """Typed (not anonymised) graph of a synthetic pattern.

    Nodes get the pattern's ``node_type`` and a ``role`` equal to the pattern's
    role label. Roles serve ONLY as ground truth for evaluation; matching and
    refinement never read them.
    """
    spec = _spec(pattern_name)
    events, names = generate_synthetic_instance(pattern_name, seed)
    graph = build_temporal_graph(events)
    return assign_node_attributes(
        graph,
        node_types={names[r]: t for r, t in spec.nodes.items()},
        roles={names[r]: r for r in spec.nodes},
    )


def pattern_category(pattern_name: str) -> str:
    """``"benign"`` or ``"suspicious"`` (a synthetic label, not ground truth about real traffic)."""
    return _spec(pattern_name).category
