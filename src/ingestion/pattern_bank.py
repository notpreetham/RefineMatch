"""JSON pattern bank: reference (suspicious-like) and benign pattern definitions.

Format (blueprint 7.4 plus provenance fields)::

    {"pattern_id": "SUSP_SYN_001", "name": ..., "category": "suspicious"|"benign",
     "technique": ..., "description": ..., "source": "synthetic",
     "required_node_roles": [{"role": "ext", "node_type": "external"}, ...],
     "required_edges": [{"source": "ext", "destination": "dmz", "edge_type": "http_request",
                         "count": 5, "interval_seconds": 30, "start_offset_seconds": 0}, ...],
     "temporal_constraints": [{"before_edge": 0, "after_edge": 1}, ...],
     "optional_nodes": []}

``source: "synthetic"`` marks entries derived from this project's synthetic
generator. Directories: ``data/reference_patterns`` and ``data/benign_patterns``.
Loaded patterns become anonymised :class:`TemporalGraph` objects built with the
Member 1 engine (canonical, jitter-free instances).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from src.core.exceptions import InvalidGraphError
from src.core.models import EventRecord, TemporalGraph
from src.graph.anonymizer import anonymize_graph
from src.graph.graph_builder import assign_node_attributes, build_temporal_graph
from src.ingestion.synthetic_generator import BASE_TIME, BENIGN, PATTERN_SPECS, SUSPICIOUS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
REFERENCE_DIR = DATA_DIR / "reference_patterns"
BENIGN_DIR = DATA_DIR / "benign_patterns"
_REQUIRED_KEYS = ("pattern_id", "name", "category", "required_node_roles", "required_edges")


@dataclass
class BankPattern:
    """Legacy compatibility container for dashboard and experiments."""

    meta: dict
    graph: TemporalGraph

    @property
    def name(self) -> str:
        return self.meta.get("name", "")

    @property
    def pattern_id(self) -> str:
        return self.meta.get("pattern_id", "")


def pattern_definitions() -> list[dict]:
    """Definitions for every built-in synthetic pattern, with stable IDs."""
    counters = {SUSPICIOUS: 0, BENIGN: 0}
    prefix = {SUSPICIOUS: "SUSP_SYN", BENIGN: "BENIGN_SYN"}
    definitions = []
    for generator_name, spec in PATTERN_SPECS.items():
        counters[spec.category] += 1
        edges = [{"source": e.source, "destination": e.destination, "edge_type": e.event_type,
                  "count": e.count, "interval_seconds": e.interval, "start_offset_seconds": e.start}
                 for e in spec.edges]
        definitions.append({
            "pattern_id": f"{prefix[spec.category]}_{counters[spec.category]:03d}",
            "name": spec.name, "category": spec.category, "technique": spec.technique,
            "description": spec.description, "source": "synthetic",
            "generator": generator_name,
            "required_node_roles": [{"role": r, "node_type": t} for r, t in spec.nodes.items()],
            "required_edges": edges,
            "temporal_constraints": [{"before_edge": i, "after_edge": i + 1} for i in range(len(edges) - 1)
                                     if edges[i]["start_offset_seconds"] < edges[i + 1]["start_offset_seconds"]],
            "optional_nodes": [],
        })
    return definitions


def write_default_pattern_bank(root: str | Path | None = None) -> list[Path]:
    """Write the built-in synthetic patterns as JSON files; returns the paths."""
    base = Path(root) if root else DATA_DIR
    written = []
    for definition in pattern_definitions():
        folder = base / ("reference_patterns" if definition["category"] == SUSPICIOUS else "benign_patterns")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{definition['pattern_id']}.json"
        path.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def validate_definition(definition: dict, origin: str = "<definition>") -> None:
    """Raise :class:`InvalidGraphError` if a definition is malformed."""
    if not isinstance(definition, dict):
        raise InvalidGraphError(f"{origin}: pattern must be a JSON object")
    missing = [k for k in _REQUIRED_KEYS if k not in definition]
    if missing:
        raise InvalidGraphError(f"{origin}: missing keys {missing}")
    if definition["category"] not in (SUSPICIOUS, BENIGN):
        raise InvalidGraphError(f"{origin}: category must be 'suspicious' or 'benign'")
    roles = {r.get("role") for r in definition["required_node_roles"]}
    if not definition["required_edges"]:
        raise InvalidGraphError(f"{origin}: required_edges is empty")
    for i, edge in enumerate(definition["required_edges"]):
        for key in ("source", "destination", "edge_type", "count", "interval_seconds", "start_offset_seconds"):
            if key not in edge:
                raise InvalidGraphError(f"{origin}: edge {i} lacks {key!r}")
        if edge["source"] not in roles or edge["destination"] not in roles:
            raise InvalidGraphError(f"{origin}: edge {i} references an undeclared role")
        if not isinstance(edge["count"], int) or edge["count"] < 1:
            raise InvalidGraphError(f"{origin}: edge {i} count must be an int >= 1")


def pattern_to_temporal_graph(definition: dict) -> TemporalGraph:
    """Canonical (jitter-free) typed graph of a definition as an official TemporalGraph."""
    validate_definition(definition)
    events = []
    for edge in definition["required_edges"]:
        for i in range(edge["count"]):
            moment = BASE_TIME + timedelta(seconds=edge["start_offset_seconds"] + i * edge["interval_seconds"])
            events.append(EventRecord(moment, edge["source"], edge["destination"], edge["edge_type"]))
    events.sort(key=lambda e: e.timestamp)
    graph = build_temporal_graph(events)
    roles = {r["role"]: r["node_type"] for r in definition["required_node_roles"]}
    present = set(graph.graph.nodes)
    tg = assign_node_attributes(
        graph,
        node_types={r: t for r, t in roles.items() if r in present},
        roles={r: r for r in roles if r in present})
    tg.graph.graph["pattern_id"] = definition.get("pattern_id")
    tg.graph.graph["name"] = definition.get("name")
    tg.graph.graph["category"] = definition.get("category")
    tg.graph.graph["description"] = definition.get("description")
    tg.graph.graph["technique"] = definition.get("technique")
    tg.graph.graph["meta"] = definition
    tg.meta = definition
    tg.pattern_id = definition.get("pattern_id", "")
    tg.name = definition.get("name", "")
    return tg


def load_pattern_definitions(directory: str | Path) -> list[dict]:
    """Read and validate every ``*.json`` file in a directory (sorted by name)."""
    folder = Path(directory)
    if not folder.is_dir():
        raise InvalidGraphError(f"pattern directory not found: {folder}")
    definitions = []
    for path in sorted(folder.glob("*.json")):
        try:
            definition = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InvalidGraphError(f"{path.name}: invalid JSON ({exc})") from exc
        validate_definition(definition, path.name)
        definitions.append(definition)
    return definitions


def definitions_to_bank(definitions: list[dict]) -> list[TemporalGraph]:
    """Turn definitions into anonymised, ready-to-match official TemporalGraph objects."""
    result = []
    for d in definitions:
        raw_tg = pattern_to_temporal_graph(d)
        anon = anonymize_graph(raw_tg)
        anon.meta = d
        anon.pattern_id = d.get("pattern_id", "")
        anon.name = d.get("name", "")
        result.append(anon)
    return result


def load_pattern_bank(directory: str | Path) -> list[TemporalGraph]:
    """Load a pattern directory as a list of anonymised official TemporalGraph objects."""
    return definitions_to_bank(load_pattern_definitions(directory))


def load_default_banks() -> tuple[list[TemporalGraph], list[TemporalGraph]]:
    """``(attack_bank, benign_bank)`` as official TemporalGraph dataclasses.

    Loaded from ``data/`` if present, else synthesized in memory.
    """
    def pick(folder: Path, category: str) -> list[TemporalGraph]:
        if folder.is_dir() and any(folder.glob("*.json")):
            return load_pattern_bank(folder)
        return definitions_to_bank([d for d in pattern_definitions() if d["category"] == category])
    return pick(REFERENCE_DIR, SUSPICIOUS), pick(BENIGN_DIR, BENIGN)


if __name__ == "__main__":  # python -m src.ingestion.pattern_bank
    for p in write_default_pattern_bank():
        print("wrote", p)
