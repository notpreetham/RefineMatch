"""Backend functions for the Streamlit dashboard (no Streamlit import, fully testable).

Every number shown in the UI is computed here by the real pipeline modules;
nothing is hard-coded. ``results/experiments.json`` is only displayed if it was
produced by ``python -m src.evaluation.experiments``.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402

from src.core.exceptions import InvalidEventError  # noqa: E402
from src.core.models import EventRecord, TemporalGraph  # noqa: E402
from src.evaluation.experiments import banks, neutralize  # noqa: E402
from src.graph.anonymizer import anonymize_graph  # noqa: E402
from src.graph.graph_builder import build_temporal_graph  # noqa: E402
from src.graph.temporal_graph import get_temporal_window  # noqa: E402
from src.ingestion.csv_parser import parse_event_rows  # noqa: E402
from src.ingestion.synthetic_generator import (  # noqa: E402
    PATTERN_NAMES, generate_synthetic_graph, pattern_category)
from src.pipeline import AnalysisResult, analyze_observed  # noqa: E402
from src.refinement.color_refinement import refinement_history  # noqa: E402
from src.refinement.individualization import agir_refine_with_trace  # noqa: E402
from src.robustness.mutation_engine import MUTATIONS, apply_mutations  # noqa: E402

RESULTS_PATH = Path(__file__).resolve().parents[1] / "results" / "experiments.json"
FLAG_NOTE = ("A 'high' level is a suspicious-pattern FLAG for analyst review. It means the behaviour "
             "resembles a synthetic/curated pattern, not that an attack occurred.")
MUTATION_CHOICES = {"Rename identities": "rename_identities", "Insert benign nodes": "insert_benign_nodes",
                    "Delete edges": "delete_edges", "Perturb timestamps": "perturb_timestamps",
                    "Perturb frequency": "perturb_frequency"}


def synthetic_sources() -> list[str]:
    """Selectable synthetic pattern names (all synthetic)."""
    return list(PATTERN_NAMES)


def load_events_from_upload(raw: bytes, name: str = "upload.csv") -> list[EventRecord]:
    """Parse uploaded CSV bytes with the same validation as the file parser."""
    import csv, io
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise InvalidEventError(f"{name}: empty file or missing header")
    rows = [{(k or "").strip().lower(): v for k, v in row.items()} for row in reader]
    missing = [c for c in ("timestamp", "source", "destination", "event_type")
               if c not in {(h or "").strip().lower() for h in reader.fieldnames}]
    if missing:
        raise InvalidEventError(f"{name}: missing required column(s) {missing}")
    return parse_event_rows(rows, origin=name)


def window_events(events: list[EventRecord], start_fraction: float, end_fraction: float) -> list[EventRecord]:
    """Events within a window given as fractions of the full time span (half-open; 1.0 includes the end)."""
    if not events:
        return []
    first = min(e.timestamp for e in events)
    last = max(e.timestamp for e in events)
    span = last - first
    start = first + span * start_fraction
    end = first + span * end_fraction + (timedelta(microseconds=1) if end_fraction >= 1.0 else timedelta(0))
    return get_temporal_window(events, start, end)


def events_table(events: list[EventRecord], limit: int = 500) -> list[dict]:
    """Event rows with per-pair frequency."""
    freq = Counter((e.source, e.destination) for e in events)
    ordered = sorted(events, key=lambda e: e.timestamp)[:limit]
    return [{"timestamp": e.timestamp.isoformat(), "source": e.source, "destination": e.destination,
             "event_type": e.event_type, "pair_frequency": freq[(e.source, e.destination)]} for e in ordered]


def build_observed(events: list[EventRecord], synthetic_pattern: str | None = None, seed: int = 0,
                   mask_identities: bool = True, ignore_types: bool = False) -> TemporalGraph:
    """Events (optionally typed from a synthetic pattern) -> graph; identities masked on request."""
    if synthetic_pattern is not None:
        typed = generate_synthetic_graph(synthetic_pattern, seed)
        keep = {e.source for e in events} | {e.destination for e in events}
        graph = build_temporal_graph(events)
        for node in graph.graph.nodes:
            if node in typed.graph:
                for key in ("node_type", "role"):
                    graph.graph.nodes[node][key] = typed.graph.nodes[node][key]
    else:
        graph = build_temporal_graph(events)
    if ignore_types:
        graph = neutralize(graph, True, False)
    return anonymize_graph(graph) if mask_identities else graph


def graph_tables(tg: TemporalGraph) -> tuple[list[dict], list[dict]]:
    """Node rows and edge rows for display."""
    nodes = [{"node": n, "node_type": a.get("node_type"), "role": a.get("role"),
              "in_degree": tg.graph.in_degree(n), "out_degree": tg.graph.out_degree(n)}
             for n, a in tg.graph.nodes(data=True)]
    edges = [{"source": u, "destination": v, "edge_types": json.dumps(a.get("edge_types", {})),
              "weight": a["weight"], "first_seen": a["first_seen"].isoformat()}
             for u, v, a in tg.graph.edges(data=True)]
    return nodes, edges


def draw_graph(tg: TemporalGraph, mapping: dict[str, str] | None = None, title: str = ""):
    """Matplotlib figure of the directed graph (edge labels = event count)."""
    figure, axis = plt.subplots(figsize=(6, 4))
    graph = tg.graph
    if graph.number_of_nodes():
        pos = nx.spring_layout(graph, seed=7)
        matched = set(mapping.values()) if mapping else set()
        colors = ["#4c9be8" if (not mapping or n in matched) else "#bbbbbb" for n in graph.nodes]
        nx.draw_networkx(graph, pos, ax=axis, node_color=colors, node_size=500, font_size=7, arrows=True)
        nx.draw_networkx_edge_labels(graph, pos, ax=axis, font_size=6,
                                     edge_labels={(u, v): a["weight"] for u, v, a in graph.edges(data=True)})
    axis.set_title(title or "Communication graph")
    axis.axis("off")
    return figure


def refinement_rows(tg: TemporalGraph) -> tuple[list[dict], dict[str, list[str]]]:
    """Per-round unique-color counts and the final color classes."""
    history = refinement_history(tg.graph)
    rows = [{"iteration": i, "unique_colors": len(set(c.values())),
             "largest_class": max(Counter(c.values()).values(), default=0)} for i, c in enumerate(history)]
    rows.append({"iteration": "converged", "unique_colors": rows[-1]["unique_colors"] if rows else 0,
                 "largest_class": rows[-1]["largest_class"] if rows else 0})
    classes: dict[str, list[str]] = {}
    for node, color in (history[-1] if history else {}).items():
        classes.setdefault(color[:8], []).append(node)
    return rows, classes


def agir_rows(tg: TemporalGraph, max_individualizations: int) -> tuple[list[dict], dict]:
    """AGIR trace rows and a summary."""
    result, trace = agir_refine_with_trace(tg.graph, max_individualizations)
    rows = [{"step": s.step, "ambiguous_class": s.color_class[:8], "class_size": s.class_size,
             "ambiguity_score": round(s.ambiguity_score, 3), "candidates": ", ".join(s.candidates),
             "selected_node": s.selected_node, "refinement_gain": s.refinement_gain,
             "ambiguous_nodes_before": s.ambiguous_nodes_before, "ambiguous_nodes_after": s.ambiguous_nodes_after}
            for s in trace]
    return rows, {"individualizations": len(trace), "classes_after": len(result.color_classes), "stable": result.stable}


def run_analysis(observed: TemporalGraph, ignore_types: bool = False) -> AnalysisResult:
    """Match against the default attack-like and benign banks (neutralised if ``ignore_types``)."""
    attack, benign = banks(ignore_types, False)
    return analyze_observed(observed, attack, benign)


def correspondence_rows(result: AnalysisResult) -> list[dict]:
    """Reference -> observed node correspondence for the best pattern."""
    ref = result.best_attack.pattern.graph.graph
    return [{"pattern_node": r, "pattern_node_type": ref.nodes[r].get("node_type"), "observed_node": o,
             "observed_node_type": result.observed.graph.nodes[o].get("node_type")}
            for r, o in sorted(result.match.node_mapping.items())]


def risk_rows(result: AnalysisResult) -> list[dict]:
    """Score components for display."""
    s = result.score
    return [{"factor": "Structural match", "value": round(s.structural_score, 3)},
            {"factor": "Temporal match", "value": round(s.temporal_score, 3)},
            {"factor": "Frequency match", "value": round(s.frequency_score, 3)},
            {"factor": "Attack-like similarity", "value": round(s.attack_similarity, 3)},
            {"factor": "Benign similarity", "value": round(s.benign_similarity, 3)},
            {"factor": "Contrastive (attack - benign)", "value": round(s.contrastive_score, 3)},
            {"factor": "Final score", "value": round(s.final_score, 3)}]


def pattern_comparison_rows(result: AnalysisResult) -> list[dict]:
    """Similarity of the observation to every bank pattern."""
    return [{"pattern": e.pattern.name, "category": e.pattern.meta["category"],
             "structural_similarity": round(e.structural, 3), "temporal": round(e.temporal, 3),
             "frequency": round(e.frequency, 3)} for e in result.attack_evidence + result.benign_evidence]


def mutation_demo(observed: TemporalGraph, mutation: str, percentage: float, seed: int,
                  ignore_types: bool = False) -> dict:
    """Before/after analysis for one mutation (identity-only vs structural change is labelled)."""
    if mutation not in ("rename_identities", *MUTATIONS):
        raise InvalidEventError(f"unknown mutation {mutation!r}")
    spec = {"type": mutation} if mutation == "rename_identities" else {"type": mutation, "percentage": percentage}
    mutated = apply_mutations(observed, [spec], seed)
    before, after = run_analysis(observed, ignore_types), run_analysis(anonymize_graph(mutated), ignore_types)
    return {"identity_only": mutation == "rename_identities", "before": before, "after": after,
            "mutated_nodes": mutated.graph.number_of_nodes(), "mutated_events": len(mutated.events)}


def load_experiment_results(path: Path | None = None) -> dict | None:
    """Parsed ``experiments.json`` or ``None`` if it has not been generated."""
    target = path or RESULTS_PATH
    if not target.is_file():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def table_for(results: dict, key: str, condition: str | None = None) -> list[dict]:
    """A displayable table from experiment results (flat scalar columns only)."""
    exp = results["experiments"][key]
    rows = exp["conditions"][condition] if condition else exp.get("rows", [])
    return [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if not isinstance(v, (dict, list))}
            for row in rows]


def robustness_chart_data(results: dict) -> dict[str, list[float]] | None:
    """``{mutation: mean true-pattern similarity per level}`` and the shared levels."""
    exp = results["experiments"].get("mutation")
    if not exp:
        return None
    curves = exp["robustness_curves_true_pattern_similarity"]
    return {kind: [p["mean"] for p in points] for kind, points in curves.items()} | {
        "levels": [p["level"] for p in next(iter(curves.values()))]}
