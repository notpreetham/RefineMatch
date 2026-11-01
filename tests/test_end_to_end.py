"""Integration test: CSV file -> ingestion -> graph -> anonymize -> match -> score -> explanation."""

import tempfile
from pathlib import Path

from src.evaluation.experiments import banks
from src.graph.anonymizer import anonymize_graph, create_identity_mapping
from src.graph.graph_builder import build_temporal_graph
from src.ingestion.csv_parser import events_to_csv, load_events_from_csv
from src.ingestion.dataset_loader import load_dataset
from src.ingestion.pattern_bank import load_default_banks
from src.ingestion.synthetic_generator import BENIGN_PATTERNS, SUSPICIOUS_PATTERNS, generate_synthetic_events
from src.pipeline import analyze_observed, prepare_observed
from src.refinement.color_refinement import color_refine


def test_csv_to_explanation_for_every_synthetic_pattern():
    attack, benign = load_default_banks()
    folder = Path(tempfile.mkdtemp())
    for name in SUSPICIOUS_PATTERNS + BENIGN_PATTERNS:
        path = folder / f"{name}.csv"
        events_to_csv(generate_synthetic_events(name, 77), str(path))
        events = load_dataset("csv", str(path))
        assert events == load_events_from_csv(str(path))
        # no node types supplied (a plain CSV), so match against the type-neutral banks
        neutral_attack, neutral_benign = banks(True, False)
        observed = prepare_observed(events, node_types=None)
        result = analyze_observed(observed, neutral_attack, neutral_benign)
        assert result.explanation["risk_level"] == result.score.risk_level
        assert "not a confirmed attack" in result.explanation["disclaimer"]
        assert 0.0 <= result.score.final_score <= 1.0


def test_identity_independence_end_to_end():
    events = generate_synthetic_events("external_to_internal_chain", 5)
    graph = build_temporal_graph(events)
    anon = anonymize_graph(graph)
    mapping = create_identity_mapping(graph)
    original = color_refine(graph.graph).node_colors
    anonymised = color_refine(anon.graph).node_colors
    assert all(original[o] == anonymised[a] for o, a in mapping.items())   # signatures ignore identifiers
    attack, benign = load_default_banks()
    a = analyze_observed(prepare_observed(events), attack, benign)
    b = analyze_observed(prepare_observed(generate_synthetic_events("external_to_internal_chain", 6)), attack, benign)
    assert a.score.risk_level == b.score.risk_level and a.best_attack.pattern.pattern_id == b.best_attack.pattern.pattern_id
