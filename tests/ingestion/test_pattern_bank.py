"""Tests for src.ingestion.pattern_bank."""

import json
import tempfile
from pathlib import Path

import pytest

from src.core.exceptions import InvalidGraphError
from src.core.models import TemporalGraph
from src.ingestion.pattern_bank import (
    DATA_DIR, load_default_banks, load_pattern_bank, load_pattern_definitions,
    pattern_definitions, pattern_to_temporal_graph, validate_definition, write_default_pattern_bank)


def test_definitions_have_unique_ids_and_valid_structure():
    defs = pattern_definitions()
    assert len({d["pattern_id"] for d in defs}) == len(defs) == 8
    assert all(d["source"] == "synthetic" for d in defs)
    for d in defs:
        validate_definition(d)


def test_write_and_load_roundtrip():
    root = Path(tempfile.mkdtemp())
    paths = write_default_pattern_bank(root)
    assert len(paths) == 8
    attack = load_pattern_bank(root / "reference_patterns")
    benign = load_pattern_bank(root / "benign_patterns")
    assert (len(attack), len(benign)) == (5, 3)
    assert all(n.startswith("N_") for p in attack for n in p.graph.nodes)  # anonymised
    assert attack[0].graph.graph.get("pattern_id") == "SUSP_SYN_001"


def test_shipped_data_files_are_in_sync_with_generator_specs():
    shipped = {d["pattern_id"]: d for d in load_pattern_definitions(DATA_DIR / "reference_patterns")}
    shipped.update({d["pattern_id"]: d for d in load_pattern_definitions(DATA_DIR / "benign_patterns")})
    assert shipped == {d["pattern_id"]: d for d in pattern_definitions()}


def test_pattern_graph_is_canonical_and_deterministic():
    d = pattern_definitions()[0]
    a, b = pattern_to_temporal_graph(d), pattern_to_temporal_graph(d)
    assert a.events == b.events
    assert {x["role"] for _, x in a.graph.nodes(data=True)} == {r["role"] for r in d["required_node_roles"]}


def test_invalid_definitions_rejected():
    d = pattern_definitions()[0]
    for broken, fragment in [
        ({k: v for k, v in d.items() if k != "name"}, "missing keys"),
        ({**d, "category": "evil"}, "category"),
        ({**d, "required_edges": []}, "empty"),
        ({**d, "required_edges": [{**d["required_edges"][0], "source": "ghost"}]}, "undeclared"),
        ({**d, "required_edges": [{**d["required_edges"][0], "count": 0}]}, "count"),
        ([], "JSON object"),
    ]:
        with pytest.raises(InvalidGraphError, match=fragment):
            validate_definition(broken)


def test_bad_files_and_directories():
    folder = Path(tempfile.mkdtemp())
    (folder / "bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(InvalidGraphError, match="invalid JSON"):
        load_pattern_definitions(folder)
    with pytest.raises(InvalidGraphError, match="not found"):
        load_pattern_definitions(folder / "missing")


def test_default_banks_load():
    attack, benign = load_default_banks()
    assert len(attack) == 5 and len(benign) == 3
    assert all(isinstance(p, TemporalGraph) for p in attack + benign)
    assert all(p.graph.graph.get("meta") for p in attack + benign)
