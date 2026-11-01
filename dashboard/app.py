"""RefineMatch dashboard (Streamlit). Run from the project root:

    streamlit run dashboard/app.py

Demo mode needs no API keys, network, or downloaded datasets: a synthetic
pattern is loaded automatically. All results come from the real backend in
``dashboard/service.py`` and ``src/``. Findings are suspicious-pattern flags
for analyst review, never confirmed attacks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from dashboard import service  # noqa: E402
from src.core.exceptions import RefineMatchError  # noqa: E402
from src.ingestion.synthetic_generator import generate_synthetic_events, pattern_category  # noqa: E402

DEMO = {"pattern": "c2_like", "seed": 1}


def _state():
    return st.session_state


def load_data(source: str, pattern: str, seed: int, upload, window: tuple[float, float],
              mask_identities: bool, ignore_types: bool) -> None:
    """Load events, apply the window, build the observed graph and store it in session state."""
    if source == "Upload CSV":
        if upload is None:
            raise RefineMatchError("choose a CSV file first")
        events = service.load_events_from_upload(upload.getvalue(), getattr(upload, "name", "upload.csv"))
        pattern_for_types = None
    else:
        events = generate_synthetic_events(pattern, seed)
        pattern_for_types = pattern
    windowed = service.window_events(events, window[0], window[1])
    if not windowed:
        raise RefineMatchError("the selected time window contains no events")
    state = _state()
    state["events"] = windowed
    state["observed"] = service.build_observed(windowed, pattern_for_types, seed, mask_identities, ignore_types)
    state["ignore_types"] = ignore_types
    state["label"] = f"synthetic: {pattern} (seed {seed})" if pattern_for_types else "uploaded CSV"
    state["synthetic_category"] = pattern_category(pattern) if pattern_for_types else None
    state.pop("analysis", None)


def ensure_default() -> None:
    """Auto-load the demo data on first run so every screen works immediately."""
    if "observed" not in _state():
        load_data("Synthetic demo", DEMO["pattern"], DEMO["seed"], None, (0.0, 1.0), True, False)


def need_data() -> bool:
    ensure_default()
    return "observed" in _state()


def get_analysis():
    state = _state()
    if "analysis" not in state:
        state["analysis"] = service.run_analysis(state["observed"], state.get("ignore_types", False))
    return state["analysis"]


def screen_input() -> None:
    st.header("1. Input")
    st.caption("Demo mode uses SYNTHETIC data generated locally. Nothing is downloaded or sent anywhere.")
    source = st.radio("Dataset", ["Synthetic demo", "Upload CSV"], index=0)
    pattern, seed, upload = DEMO["pattern"], DEMO["seed"], None
    if source == "Synthetic demo":
        pattern = st.selectbox("Synthetic pattern", service.synthetic_sources(),
                               index=service.synthetic_sources().index(DEMO["pattern"]))
        seed = int(st.number_input("Seed", min_value=0, max_value=10_000, value=DEMO["seed"], step=1))
        st.caption(f"Synthetic label of this pattern: **{pattern_category(pattern)}** "
                   "(illustrative shape, not real attack data).")
    else:
        upload = st.file_uploader("CSV with timestamp, source, destination, event_type "
                                  "(+ optional protocol, ports, bytes, duration)", type=["csv"])
    window = st.slider("Temporal window (fraction of the time span, start inclusive / end exclusive)",
                       0.0, 1.0, (0.0, 1.0), 0.05)
    mask = st.checkbox("Identity masking (replace hostnames/IPs with abstract IDs)", value=True)
    ignore = st.checkbox("Ignore node types (use for CSV data that has no type information)", value=False)
    if st.button("Load / apply"):
        try:
            load_data(source, pattern, seed, upload, window, mask, ignore)
            st.success(f"Loaded {len(_state()['events'])} events from {_state()['label']}.")
        except RefineMatchError as exc:
            st.error(str(exc))
        except FileNotFoundError as exc:
            st.error(str(exc))
    if need_data():
        st.info(f"Current data: {_state()['label']} - {len(_state()['events'])} events, "
                f"{_state()['observed'].graph.number_of_nodes()} nodes.")


def screen_events() -> None:
    st.header("2. Raw events")
    if not need_data():
        return
    rows = service.events_table(_state()["events"])
    st.caption(f"Showing up to 500 of {len(_state()['events'])} events; pair_frequency = events for that source->destination.")
    st.dataframe(rows)


def screen_graph() -> None:
    st.header("3. Graph")
    if not need_data():
        return
    observed = _state()["observed"]
    st.pyplot(service.draw_graph(observed, title="Observed communication graph (edge label = event count)"))
    nodes, edges = service.graph_tables(observed)
    left, right = st.columns(2)
    with left:
        st.subheader("Nodes")
        st.dataframe(nodes)
    with right:
        st.subheader("Directed edges")
        st.dataframe(edges)


def screen_refinement() -> None:
    st.header("4. Color Refinement (1-WL)")
    if not need_data():
        return
    rows, classes = service.refinement_rows(_state()["observed"])
    st.dataframe(rows)
    st.caption("Colors are structural signatures (type, degree, edge types, neighbour colors), never identifiers. "
               "1-WL cannot distinguish every pair of non-isomorphic graphs.")
    with st.expander("Final color classes (nodes sharing a class are structurally indistinguishable)"):
        st.json(classes)


def screen_agir() -> None:
    st.header("5. AGIR - ambiguity-guided individualization")
    if not need_data():
        return
    budget = int(st.slider("Max individualizations", 0, 10, 5, 1))
    rows, summary = service.agir_rows(_state()["observed"], budget)
    st.write(summary)
    if rows:
        st.dataframe(rows)
    else:
        st.info("No worthwhile ambiguity: no individualization was needed within this budget.")
    st.caption("AGIR is a heuristic, budgeted search; it does not guarantee a complete isomorphism decision.")


def screen_matching() -> None:
    st.header("6. Matching")
    if not need_data():
        return
    result = get_analysis()
    st.write(f"Closest suspicious-like pattern: **{result.best_attack.pattern.name}** "
             f"({result.best_attack.pattern.pattern_id}, {result.best_attack.pattern.meta.get('source', 'unknown')} source)")
    st.metric("Structural similarity", f"{result.match.similarity:.3f}")
    st.write(f"Matched {len(result.match.matched_nodes)} pattern node(s); "
             f"{len(result.match.unmatched_reference_nodes)} pattern node(s) and "
             f"{len(result.match.unmatched_observed_nodes)} observed node(s) unmatched; "
             f"{result.match.individualization_count} individualization step(s); "
             f"match confidence {result.match.confidence:.2f} (heuristic, not a probability).")
    left, right = st.columns(2)
    with left:
        st.pyplot(service.draw_graph(result.best_attack.pattern.graph, title="Reference pattern"))
    with right:
        st.pyplot(service.draw_graph(result.observed, result.match.node_mapping,
                                     title="Observed (grey = unmatched)"))
    st.subheader("Node correspondence")
    st.dataframe(service.correspondence_rows(result))
    st.subheader("Similarity to every pattern in the banks")
    st.dataframe(service.pattern_comparison_rows(result))


def screen_risk() -> None:
    st.header("7. Risk")
    if not need_data():
        return
    result = get_analysis()
    st.metric("Final risk level", result.score.risk_level.upper())
    st.metric("Final score", f"{result.score.final_score:.3f}")
    st.warning(service.FLAG_NOTE)
    st.dataframe(service.risk_rows(result))
    explanation = result.explanation
    st.subheader("Explanation")
    st.write(explanation["summary"])
    for key in ("structural_evidence", "temporal_evidence", "identity_independence_evidence", "benign_comparison"):
        st.write(f"- {explanation[key]}")
    st.caption(explanation["disclaimer"])
    if _state().get("synthetic_category"):
        st.caption(f"For reference, this synthetic pattern was generated with the label "
                   f"'{_state()['synthetic_category']}'.")


def screen_mutation() -> None:
    st.header("8. Mutation demo")
    if not need_data():
        return
    label = st.selectbox("Mutation", list(service.MUTATION_CHOICES))
    percentage = float(st.slider("Percentage (ignored for renaming)", 0.0, 0.5, 0.2, 0.05))
    seed = int(st.number_input("Mutation seed", min_value=0, max_value=10_000, value=0, step=1))
    if st.button("Apply mutation and re-match"):
        demo = service.mutation_demo(_state()["observed"], service.MUTATION_CHOICES[label], percentage, seed,
                                     _state().get("ignore_types", False))
        kind = "identity-only change (structure unchanged)" if demo["identity_only"] else "structural change"
        st.write(f"Type: **{kind}**; mutated graph has {demo['mutated_nodes']} nodes and {demo['mutated_events']} events.")
        st.dataframe([
            {"metric": "structural similarity", "before": round(demo["before"].score.structural_score, 3),
             "after": round(demo["after"].score.structural_score, 3)},
            {"metric": "final score", "before": round(demo["before"].score.final_score, 3),
             "after": round(demo["after"].score.final_score, 3)},
            {"metric": "risk level", "before": demo["before"].score.risk_level, "after": demo["after"].score.risk_level}])


def screen_evaluation() -> None:
    st.header("9. Evaluation")
    st.warning("Results below are from SYNTHETIC data only and are not evidence of real-world performance.")
    results = service.load_experiment_results()
    if results is None:
        st.info("No results found. Generate them with: python -m src.evaluation.experiments --quick")
        if st.button("Run quick experiments now (about 1-2 minutes)"):
            from src.evaluation.experiments import run_all_experiments
            run_all_experiments(service.RESULTS_PATH.parent, quick=True, include_ged=False)
            st.success("Done. Reload this screen.")
        return
    experiments = results["experiments"]
    st.caption(f"Quick mode: {results['quick_mode']}; dev seeds {results['dev_seeds']}, test seeds {results['test_seeds']}.")
    if "baselines" in experiments:
        condition = st.selectbox("Baseline comparison condition", list(experiments["baselines"]["conditions"]))
        st.dataframe(service.table_for(results, "baselines", condition))
    if "ablation" in experiments:
        st.subheader("Ablation")
        st.dataframe(service.table_for(results, "ablation"))
    curve = service.robustness_chart_data(results)
    if curve:
        st.subheader("Robustness curve (mean similarity to the true pattern vs mutation level)")
        levels = curve.pop("levels")
        st.line_chart({"level": levels, **curve}, x="level")
    if "cross_env" in experiments:
        st.subheader("Cross-environment matching")
        condition = st.selectbox("Cross-environment condition", list(experiments["cross_env"]["conditions"]))
        st.dataframe(service.table_for(results, "cross_env", condition))


SCREENS = {
    "1. Input": screen_input, "2. Raw events": screen_events, "3. Graph": screen_graph,
    "4. Color Refinement": screen_refinement, "5. AGIR": screen_agir, "6. Matching": screen_matching,
    "7. Risk": screen_risk, "8. Mutation demo": screen_mutation, "9. Evaluation": screen_evaluation,
}


def main() -> None:
    st.set_page_config(page_title="RefineMatch", layout="wide")
    st.title("RefineMatch - identity-independent attack-pattern matching")
    st.caption("Research prototype. Flags are suspicious-pattern findings for analyst review, not confirmed attacks.")
    choice = st.sidebar.radio("Screen", list(SCREENS))
    try:
        SCREENS[choice]()
    except RefineMatchError as exc:
        st.error(f"Input problem: {exc}")


if __name__ == "__main__":
    main()
