"""Dashboard tests: backend service functions, plus a smoke run of every screen.

REAL Streamlit is not required here: ``StubStreamlit`` implements just the calls
``dashboard/app.py`` makes (returning default widget values, recording output).
This verifies the app code paths run against the real backend; it does NOT
prove the real Streamlit server starts (run ``streamlit run dashboard/app.py``).
"""

import importlib
import sys
import tempfile
import types
from pathlib import Path

import pytest

from dashboard import service
from src.core.exceptions import InvalidEventError
from src.evaluation.experiments import run_all_experiments
from src.ingestion.synthetic_generator import generate_synthetic_events

CSV = (b"timestamp,source,destination,event_type\n"
       b"2024-01-01T00:00:00Z,a,b,http\n2024-01-01T00:00:10Z,b,c,sql\n2024-01-01T00:00:20Z,a,b,http\n")


def test_upload_parsing_and_errors():
    events = service.load_events_from_upload(CSV, "x.csv")
    assert len(events) == 3 and events[0].source == "a"
    with pytest.raises(InvalidEventError, match="missing required"):
        service.load_events_from_upload(b"timestamp,source\n1,a\n")
    with pytest.raises(InvalidEventError):
        service.load_events_from_upload(b"")
    with pytest.raises(InvalidEventError, match="line 2"):
        service.load_events_from_upload(b"timestamp,source,destination,event_type\nbad,a,b,x\n")


def test_window_events_fractions():
    events = generate_synthetic_events("c2_like", 1)
    assert len(service.window_events(events, 0.0, 1.0)) == len(events)
    half = service.window_events(events, 0.0, 0.5)
    assert 0 < len(half) < len(events)
    assert service.window_events([], 0.0, 1.0) == []
    assert service.window_events(events, 0.5, 0.5) == []


def test_tables_and_masking():
    events = generate_synthetic_events("normal_database_access", 2)
    masked = service.build_observed(events, "normal_database_access", 2, mask_identities=True)
    raw = service.build_observed(events, "normal_database_access", 2, mask_identities=False)
    assert all(n.startswith("N_") for n in masked.graph.nodes) and not any(n.startswith("N_") for n in raw.graph.nodes)
    nodes, edges = service.graph_tables(masked)
    assert {r["node_type"] for r in nodes} == {"application_server", "database", "client"}
    assert sum(e["weight"] for e in edges) == len(events)
    rows = service.events_table(events)
    assert rows[0]["pair_frequency"] >= 1 and len(rows) == len(events)


def test_refinement_agir_and_analysis_rows_come_from_backend():
    events = generate_synthetic_events("scanning_like", 3)
    observed = service.build_observed(events, "scanning_like", 3)
    rows, classes = service.refinement_rows(observed)
    assert rows[0]["iteration"] == 0 and rows[-1]["iteration"] == "converged"
    assert any(len(v) == 8 for v in classes.values())            # the eight probed targets
    agir, summary = service.agir_rows(observed, 3)
    assert summary["individualizations"] == len(agir) <= 3
    result = service.run_analysis(observed)
    assert result.score.risk_level == "high" and result.explanation["matched_pattern"]
    assert len(service.correspondence_rows(result)) == len(result.match.node_mapping)
    assert [r["factor"] for r in service.risk_rows(result)][-1] == "Final score"
    assert len(service.pattern_comparison_rows(result)) == 8


def test_mutation_demo_labels_identity_only_and_keeps_score_for_rename():
    observed = service.build_observed(generate_synthetic_events("c2_like", 4), "c2_like", 4)
    rename = service.mutation_demo(observed, "rename_identities", 0.0, 1)
    assert rename["identity_only"] and rename["before"].score.final_score == rename["after"].score.final_score
    delete = service.mutation_demo(observed, "delete_edges", 0.5, 1)
    assert not delete["identity_only"]
    with pytest.raises(InvalidEventError):
        service.mutation_demo(observed, "explode", 0.1, 1)


# ------------------------------------------------------------------- smoke run
class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class StubStreamlit(types.ModuleType):
    def __init__(self, screen, click=True):
        super().__init__("streamlit")
        self.screen, self.click, self.session_state, self.log = screen, click, {}, []
        self.sidebar = types.SimpleNamespace(radio=lambda label, options, index=0: self.screen)

    def radio(self, label, options, index=0, **k):
        return options[index]

    def selectbox(self, label, options, index=0, **k):
        return options[index]

    def number_input(self, label, min_value=None, max_value=None, value=0, step=1, **k):
        return value

    def slider(self, label, mn, mx, value, step=None, **k):
        return value

    def checkbox(self, label, value=False, **k):
        return value

    def button(self, label, **k):
        return self.click

    def file_uploader(self, *a, **k):
        return None

    def columns(self, n, **k):
        return [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]

    def expander(self, *a, **k):
        return _Ctx()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: self.log.append((name, a, k))


def run_screen(screen, click=True):
    stub = StubStreamlit(screen, click)
    original = sys.modules.get("streamlit")
    sys.modules["streamlit"] = stub
    sys.modules.pop("dashboard.app", None)
    try:
        app = importlib.import_module("dashboard.app")
        app.main()
    finally:  # never leave the stub behind (a real Streamlit install must keep working)
        if original is not None:
            sys.modules["streamlit"] = original
        else:
            sys.modules.pop("streamlit", None)
    return stub, app


@pytest.mark.parametrize("screen", ["1. Input", "2. Raw events", "3. Graph", "4. Color Refinement", "5. AGIR",
                                    "6. Matching", "7. Risk", "8. Mutation demo"])
def test_every_backend_screen_runs_against_the_real_pipeline(screen):
    stub, app = run_screen(screen)
    names = [c[0] for c in stub.log]
    assert "error" not in names, stub.log
    expected = {"1. Input": "info", "5. AGIR": "info"}.get(screen)  # status-only screens for the default demo
    assert (expected in names) if expected else any(n in names for n in ("dataframe", "pyplot", "metric"))
    assert "observed" in stub.session_state


def test_risk_screen_shows_disclaimer_and_matching_uses_real_pattern_name():
    stub, _ = run_screen("7. Risk")
    text = " ".join(str(c) for c in stub.log)
    assert "not that an attack occurred" in text
    metrics = [c for c in stub.log if c[0] == "metric"]
    assert metrics[0][1][1] in ("HIGH", "MEDIUM", "LOW")
    stub, _ = run_screen("6. Matching")
    assert any("Closest suspicious-like pattern" in str(c) for c in stub.log)


def test_csv_upload_path_and_bad_upload_handled():
    stub, app = run_screen("1. Input", click=False)
    good = types.SimpleNamespace(getvalue=lambda: CSV, name="t.csv")
    app.load_data("Upload CSV", "", 0, good, (0.0, 1.0), True, True)
    assert stub.session_state["label"] == "uploaded CSV" and len(stub.session_state["events"]) == 3
    with pytest.raises(Exception):
        app.load_data("Upload CSV", "", 0, None, (0.0, 1.0), True, False)
    with pytest.raises(Exception):
        app.load_data("Synthetic demo", "c2_like", 1, None, (0.5, 0.5), True, False)


def test_evaluation_screen_missing_results_and_with_real_results():
    original = service.RESULTS_PATH
    try:
        service.RESULTS_PATH = Path(tempfile.mkdtemp()) / "nope.json"
        stub, _ = run_screen("9. Evaluation", click=False)
        assert any(c[0] == "info" and "No results found" in c[1][0] for c in stub.log)
        folder = Path(tempfile.mkdtemp())
        run_all_experiments(folder, quick=True, include_ged=False, only=("mutation", "ablation"))
        service.RESULTS_PATH = folder / "experiments.json"
        stub, _ = run_screen("9. Evaluation", click=False)
        names = [c[0] for c in stub.log]
        assert "line_chart" in names and names.count("dataframe") >= 1 and "error" not in names
        results = service.load_experiment_results(service.RESULTS_PATH)
        assert service.table_for(results, "ablation")[0]["method"].startswith("full")
    finally:
        service.RESULTS_PATH = original
