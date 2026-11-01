"""Reproducible experiments (blueprint section 8.4) on SYNTHETIC data only.

IMPORTANT - what these results are and are not
----------------------------------------------
* All telemetry is synthetic (see ``synthetic_generator``). The "suspicious"
  patterns are illustrative shapes, and the test observations are drawn from
  the same generator family as the pattern bank. Results therefore show that
  the pipeline behaves as designed under controlled perturbation; they are NOT
  evidence of real-world detection performance, and no real public dataset
  (StreamSpot, DARPA TC/OpTC, ...) was evaluated.
* Protocol: for each condition, development seeds tune the risk weights and
  flag threshold (``tune_weights_and_threshold``); disjoint test seeds are then
  scored with those frozen settings. Baselines (similarity-only) get a tuned
  decision margin ``best_attack_sim - best_benign_sim > tau`` on the same dev
  seeds. Everything except runtime/memory numbers is deterministic.
* Sample sizes are small (a few instances per pattern), so differences between
  methods are indicative only; no significance testing is claimed.

CLI: ``python -m src.evaluation.experiments --output results [--quick] [--no-ged]``
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.core.config import DEFAULT_RISK_THRESHOLD
from src.evaluation.baselines import BASELINES
from src.evaluation.metrics import (
    calculate_robustness_curve, calculate_runtime, classification_report, matching_accuracy,
    measure_peak_memory)
from src.graph.anonymizer import anonymize_graph
from src.graph.graph_builder import build_temporal_graph
from src.ingestion.pattern_bank import BankPattern, load_default_banks
from src.ingestion.synthetic_generator import (
    PATTERN_NAMES, generate_synthetic_graph, pattern_category)
from src.core.models import TemporalGraph
from src.matching.graph_matcher import MatcherConfig
from src.pipeline import PairEvidence, analyze_observed, best_evidence, compute_pair_evidence
from src.robustness.mutation_engine import apply_mutations, rebuild_from_events, rename_identities
from src.scoring.risk_score import RiskWeights, level_for, tune_weights_and_threshold
from src.scoring.contrastive_score import normalize_contrastive

import dataclasses

DISCLAIMER = ("Synthetic-data demonstration only. Not evidence of real-world performance; "
              "no real public dataset was evaluated.")
AGIR, NO_INDIV, RANDOM_INDIV = (MatcherConfig(), MatcherConfig(selection="none"),
                                MatcherConfig(selection="random", seed=0))
MASKS = {  # (structural, temporal, frequency, contrastive) active components
    "structure_only": (1, 0, 0, 0), "structure+temporal": (1, 1, 0, 0),
    "structure+temporal+frequency": (1, 1, 1, 0), "full": (1, 1, 1, 1),
    "no_temporal": (1, 0, 1, 1), "no_frequency": (1, 1, 0, 1), "no_contrastive": (1, 1, 1, 0)}


# ----------------------------------------------------------------------- data
@dataclass
class Instance:
    pattern: str
    label: bool  # True = suspicious-like (synthetic label)
    observed: TemporalGraph


@dataclass
class Collected:
    instance: Instance
    attack: list[PairEvidence]
    benign: list[PairEvidence]
    seconds: float

    def true_evidence(self) -> PairEvidence:
        for item in self.attack + self.benign:
            if item.pattern.meta.get("generator") == self.instance.pattern:
                return item
        raise KeyError(self.instance.pattern)

    def sample(self) -> tuple[float, float, float, float]:
        top, benign = best_evidence(self.attack), best_evidence(self.benign)
        return (top.structural, top.temporal, top.frequency,
                top.structural - (benign.structural if benign else 0.0))


def neutralize(graph: TemporalGraph, strip_types: bool, strip_labels: bool) -> TemporalGraph:
    """Remove node types and/or event-type labels (structure-only stress condition)."""
    if not (strip_types or strip_labels):
        return graph
    events = [dataclasses.replace(e, event_type="event") if strip_labels else dataclasses.replace(e)
              for e in graph.events]
    result = rebuild_from_events(graph, events)
    if strip_types:
        for node in result.graph.nodes:
            result.graph.nodes[node]["node_type"] = "host"
    return result


@lru_cache(maxsize=None)
def banks(strip_types: bool, strip_labels: bool) -> tuple[list[BankPattern], list[BankPattern]]:
    attack, benign = load_default_banks()
    wrap = lambda bank: [
        BankPattern(
            p.meta if hasattr(p, "meta") else p.graph.graph.get("meta", {}),
            neutralize(p.graph if isinstance(getattr(p, "graph", None), TemporalGraph) else p, strip_types, strip_labels),
        )
        for p in bank
    ]
    return wrap(attack), wrap(benign)


def make_observed(pattern: str, seed: int, mutations: tuple = (), strip_types=False, strip_labels=False):
    graph = generate_synthetic_graph(pattern, seed)
    if mutations:
        graph = apply_mutations(graph, [dict(m) for m in mutations], seed * 13 + 1)
    return anonymize_graph(neutralize(graph, strip_types, strip_labels))


def collect(seeds, mutations=(), strip_types=False, strip_labels=False,
            config: MatcherConfig = AGIR) -> list[Collected]:
    attack, benign = banks(strip_types, strip_labels)
    out = []
    for pattern in PATTERN_NAMES:
        for seed in seeds:
            observed = make_observed(pattern, seed, mutations, strip_types, strip_labels)
            instance = Instance(pattern, pattern_category(pattern) == "suspicious", observed)
            def run():
                return ([compute_pair_evidence(p, observed, config) for p in attack],
                        [compute_pair_evidence(p, observed, config) for p in benign])
            (atk, ben), seconds = calculate_runtime(run)
            out.append(Collected(instance, atk, ben, seconds))
    return out


def masked(sample, mask):
    s, t, f, c = sample
    return (s * mask[0], t * mask[1], f * mask[2], c if mask[3] else -1.0)


@dataclass
class Fit:
    weights: RiskWeights
    threshold: float
    dev_f1: float
    guard: bool


def fit(dev: list[Collected], mask) -> Fit:
    samples = [masked(c.sample(), mask) for c in dev]
    weights, threshold, f1 = tune_weights_and_threshold(samples, [c.instance.label for c in dev],
                                                        step=0.1, guard=bool(mask[3]))
    return Fit(weights, threshold, f1, bool(mask[3]))


def predict(sample, fit_: Fit, mask) -> bool:
    s, t, f, c = masked(sample, mask)
    w = fit_.weights
    final = w.structural * s + w.temporal * t + w.frequency * f + w.contrastive * normalize_contrastive(c)
    return level_for(final, c, fit_.threshold, 0.0, fit_.guard) == "high"


def evaluate(test: list[Collected], fit_: Fit, mask) -> dict:
    labels = [c.instance.label for c in test]
    report = classification_report(labels, [predict(c.sample(), fit_, mask) for c in test])
    report.update(weights=dict(zip(("structural", "temporal", "frequency", "contrastive"), fit_.weights.as_tuple())),
                  threshold=fit_.threshold, dev_f1=fit_.dev_f1, n_test=len(test))
    return report


def role_truth(reference: Any, observed: Any) -> dict[str, str]:
    ref_g = reference.graph if isinstance(reference, TemporalGraph) else reference
    obs_g = observed.graph if isinstance(observed, TemporalGraph) else observed
    ref = {a["role"]: n for n, a in ref_g.nodes(data=True) if a.get("role")}
    obs = {a["role"]: n for n, a in obs_g.nodes(data=True) if a.get("role")}
    return {ref[r]: obs[r] for r in ref if r in obs}


def match_quality(test: list[Collected]) -> dict:
    sims, accs, indiv = [], [], []
    for c in test:
        ev = c.true_evidence()
        sims.append(ev.structural)
        accs.append(matching_accuracy(ev.details.match.node_mapping, role_truth(ev.pattern.graph, c.instance.observed)))
        indiv.append(ev.details.match.individualization_count)
    return {"mean_true_pattern_similarity": statistics.fmean(sims),
            "mean_role_exact_matching_accuracy": statistics.fmean(accs),
            "mean_individualizations": statistics.fmean(indiv),
            "runtime_seconds_mean": statistics.fmean(c.seconds for c in test)}


def _rows(table: dict) -> list[dict]:
    return [{"method": k, **v} for k, v in table.items()]


# ---------------------------------------------------------------- experiments
def exp1_identity_robustness(test_seeds) -> dict:
    """Rename all identifiers; compare scores, decisions and mapping."""
    attack, benign = load_default_banks()
    rows = {"anonymized_original": [], "renamed_raw_ids": [], "renamed_then_anonymized": []}
    for pattern in PATTERN_NAMES:
        for seed in test_seeds:
            base = generate_synthetic_graph(pattern, seed)
            renamed = rename_identities(base, seed + 1000)
            variants = {"anonymized_original": anonymize_graph(base), "renamed_raw_ids": renamed,
                        "renamed_then_anonymized": anonymize_graph(renamed)}
            for name, observed in variants.items():
                res = analyze_observed(observed, attack, benign)
                truth_ev = next(e for e in res.attack_evidence + res.benign_evidence
                                if e.pattern.meta["generator"] == pattern)
                acc = matching_accuracy(truth_ev.details.match.node_mapping,
                                        role_truth(truth_ev.pattern.graph, observed))
                rows[name].append((res.score.final_score, res.score.risk_level,
                                   res.best_attack.pattern.pattern_id, truth_ev.structural, acc))
    ref = rows["anonymized_original"]
    summary = {}
    for name, values in rows.items():
        summary[name] = {
            "n": len(values),
            "max_abs_final_score_difference_vs_original": max(abs(a[0] - b[0]) for a, b in zip(values, ref)),
            "same_risk_level_fraction": statistics.fmean(a[1] == b[1] for a, b in zip(values, ref)),
            "same_best_attack_pattern_fraction": statistics.fmean(a[2] == b[2] for a, b in zip(values, ref)),
            "mean_true_pattern_similarity": statistics.fmean(v[3] for v in values),
            "mean_role_exact_matching_accuracy": statistics.fmean(v[4] for v in values)}
    return {"name": "identity_robustness", "disclaimer": DISCLAIMER, "summary": summary,
            "note": "Role-exact accuracy is below 1 where automorphic nodes (e.g. identical servers) are "
                    "interchangeable; structural similarity is unaffected by that choice."}


def exp2_cr_vs_individualization(dev_seeds, test_seeds) -> dict:
    """CR only vs random individualization vs AGIR selection, under noise."""
    noise = ({"type": "insert_benign_nodes", "percentage": 0.2}, {"type": "delete_edges", "percentage": 0.1})
    out = {}
    for condition, (st, sl) in {"typed_noise": (False, False), "untyped_unlabeled_noise": (True, True)}.items():
        table = {}
        for name, config in (("cr_only", NO_INDIV), ("cr_random_individualization", RANDOM_INDIV),
                             ("cr_agir", AGIR)):
            dev = collect(dev_seeds, noise, st, sl, config)
            test = collect(test_seeds, noise, st, sl, config)
            fit_ = fit(dev, MASKS["full"])
            table[name] = {**evaluate(test, fit_, MASKS["full"]), **match_quality(test)}
            first = test[-1]
            ev_pat = first.true_evidence().pattern
            _, peak = measure_peak_memory(compute_pair_evidence, ev_pat, first.instance.observed, config)
            table[name]["peak_memory_bytes_one_match"] = peak
        out[condition] = _rows(table)
    return {"name": "cr_vs_individualization", "disclaimer": DISCLAIMER, "conditions": out,
            "mutations": [dict(m) for m in noise]}


def exp3_temporal_contribution(dev_seeds, test_seeds) -> dict:
    """Structure only / + temporal order / + frequency / + contrastive."""
    perturb = ({"type": "perturb_timestamps", "percentage": 0.3},
               {"type": "perturb_frequency", "percentage": 0.3})
    conditions = {"typed_clean": ((), False, False), "unlabeled_perturbed": (perturb, True, True)}
    out = {}
    for condition, (mut, st, sl) in conditions.items():
        dev = collect(dev_seeds, mut, st, sl)
        test = collect(test_seeds, mut, st, sl)
        table = {}
        for name in ("structure_only", "structure+temporal", "structure+temporal+frequency", "full"):
            table[name] = evaluate(test, fit(dev, MASKS[name]), MASKS[name])
        out[condition] = _rows(table)
    return {"name": "temporal_contribution", "disclaimer": DISCLAIMER, "conditions": out,
            "note": "'unlabeled_perturbed' removes node types and event-type labels, so structure alone "
                    "cannot separate benign and suspicious shapes that share a topology (e.g. client-server "
                    "vs beaconing); temporal/frequency evidence is what remains."}


def exp4_mutation_robustness(dev_seeds, test_seeds, levels=(0.05, 0.1, 0.2, 0.3)) -> dict:
    """Mutation levels with weights tuned on CLEAN dev data and then frozen."""
    dev = collect(dev_seeds)
    fit_ = fit(dev, MASKS["full"])
    out, curves = {}, {}
    kinds = ("insert_benign_nodes", "delete_edges", "perturb_timestamps", "perturb_frequency")
    clean = collect(test_seeds)
    out["clean"] = {**evaluate(clean, fit_, MASKS["full"]), **match_quality(clean)}
    for kind in kinds:
        per_level, sims = [], {}
        for level in levels:
            test = collect(test_seeds, ({"type": kind, "percentage": level},))
            quality = match_quality(test)
            per_level.append({"level": level, **evaluate(test, fit_, MASKS["full"]), **quality})
            sims[level] = [c.true_evidence().structural for c in test]
        out[kind] = per_level
        curves[kind] = calculate_robustness_curve(sims)
    out["identity_change_only"] = None
    renamed = collect(test_seeds, ({"type": "rename_identities"},))
    out["identity_change_only"] = {**evaluate(renamed, fit_, MASKS["full"]), **match_quality(renamed)}
    return {"name": "mutation_robustness", "disclaimer": DISCLAIMER, "levels": list(levels),
            "frozen_weights_tuned_on": "clean development seeds", "results": out,
            "robustness_curves_true_pattern_similarity": curves,
            "note": "delete_edges at 0.1 and 0.2 are the '10%/20% missing edges' cases."}


def exp5_cross_environment(dev_seeds, test_seeds) -> dict:
    """Reference = Network A (canonical bank); test = Network B (new identities, counts, timing, noise)."""
    scenarios = {
        "identifiers_only": (),
        "host_count_change": ({"type": "insert_benign_nodes", "percentage": 0.4},),
        "frequency_change": ({"type": "perturb_frequency", "percentage": 0.6},),
        "benign_topology_noise": ({"type": "insert_benign_nodes", "percentage": 0.2},
                                  {"type": "insert_edges", "percentage": 0.2}),
    }
    out = {}
    for typedness, (st, sl) in {"node_types_known": (False, False), "node_types_removed": (True, False)}.items():
        fit_ = fit(collect(dev_seeds, (), st, sl), MASKS["full"])
        rows = {}
        for name, mut in scenarios.items():
            test = collect(test_seeds, mut, st, sl)
            rows[name] = {**evaluate(test, fit_, MASKS["full"]), **match_quality(test)}
        out[typedness] = _rows(rows)
    return {"name": "cross_environment", "disclaimer": DISCLAIMER, "conditions": out,
            "note": "Both networks come from the same synthetic generator family; real cross-environment "
                    "variation is larger."}


def _margin_fit(dev_pairs, labels):
    best = (-1.0, 0.0)
    for i in range(-20, 21):
        tau = i / 20
        report = classification_report(labels, [m > tau for m in dev_pairs])
        if report["f1"] > best[0] + 1e-12:
            best = (report["f1"], tau)
    return best[1]


def exp6_baselines(dev_seeds, test_seeds, include_ged=True) -> dict:
    """RefineMatch vs implemented baselines on the same inputs and splits."""
    conditions = {"cross_env_typed": ((), False, False),
                  "unlabeled_noise_10": (({"type": "insert_benign_nodes", "percentage": 0.1},), True, True)}
    methods = {k: v for k, v in BASELINES.items() if include_ged or k != "graph_edit_distance"}
    out = {}
    for condition, (mut, st, sl) in conditions.items():
        attack, benign = banks(st, sl)
        dev_i = [Instance(p, pattern_category(p) == "suspicious", make_observed(p, s, mut, st, sl))
                 for p in PATTERN_NAMES for s in dev_seeds]
        test_i = [Instance(p, pattern_category(p) == "suspicious", make_observed(p, s, mut, st, sl))
                  for p in PATTERN_NAMES for s in test_seeds]
        rows = {}
        for name, method in methods.items():
            def margins(instances):
                values, skipped = [], 0
                for inst in instances:
                    a = [method(p.graph, inst.observed) for p in attack]
                    b = [method(p.graph, inst.observed) for p in benign]
                    if any(v is None for v in a + b):
                        skipped += 1
                        values.append(None)
                    else:
                        values.append(max(a) - (max(b) if b else 0.0))
                return values, skipped
            (dev_m, dev_skip), _ = calculate_runtime(margins, dev_i)
            (test_m, test_skip), seconds = calculate_runtime(margins, test_i)
            if dev_skip or test_skip:
                rows[name] = {"status": "skipped", "reason": "graph too large or no result within time limit",
                              "skipped_instances": dev_skip + test_skip}
                continue
            tau = _margin_fit(dev_m, [i.label for i in dev_i])
            report = classification_report([i.label for i in test_i], [m > tau for m in test_m])
            rows[name] = {**report, "tuned_margin": tau, "runtime_seconds_mean": seconds / len(test_i),
                          "n_test": len(test_i), "status": "ok"}
        # RefineMatch variants
        for name, config, mask in (("refinematch_structure_only_margin", AGIR, None),
                                   ("refinematch_full", AGIR, MASKS["full"])):
            dev = collect(dev_seeds, mut, st, sl, config)
            test, seconds = calculate_runtime(collect, test_seeds, mut, st, sl, config)
            if mask is None:  # same margin rule as the baselines, structural similarity only
                margin = lambda c: best_evidence(c.attack).structural - (best_evidence(c.benign).structural if c.benign else 0.0)
                tau = _margin_fit([margin(c) for c in dev], [c.instance.label for c in dev])
                report = classification_report([c.instance.label for c in test], [margin(c) > tau for c in test])
                report["tuned_margin"] = tau
            else:
                report = evaluate(test, fit(dev, mask), mask)
            rows[name] = {**report, "runtime_seconds_mean": seconds / len(test), "n_test": len(test), "status": "ok"}
        out[condition] = _rows(rows)
    return {"name": "baseline_comparison", "disclaimer": DISCLAIMER, "conditions": out,
            "baseline_notes": "graph2vec_style_wl is WL-subtree cosine similarity, not learned Graph2Vec; "
                              "GED is size/time limited; the GNN baseline is not implemented."}


def exp7_ablation(dev_seeds, test_seeds) -> dict:
    """Remove one component at a time on a hard condition (no labels, noise, timing/frequency drift)."""
    mut = ({"type": "insert_benign_nodes", "percentage": 0.1}, {"type": "perturb_timestamps", "percentage": 0.2},
           {"type": "perturb_frequency", "percentage": 0.2})
    rows = {}
    agir_dev, agir_test = collect(dev_seeds, mut, True, True, AGIR), collect(test_seeds, mut, True, True, AGIR)
    for name, mask in (("full (CR+AGIR+temporal+frequency+contrastive)", "full"), ("no_temporal", "no_temporal"),
                       ("no_frequency", "no_frequency"), ("no_contrastive", "no_contrastive"),
                       ("structure_only", "structure_only")):
        rows[name] = {**evaluate(agir_test, fit(agir_dev, MASKS[mask]), MASKS[mask]), **match_quality(agir_test)}
    for name, config in (("no_agir (CR only, full scoring)", NO_INDIV),
                         ("random_individualization (full scoring)", RANDOM_INDIV)):
        dev, test = collect(dev_seeds, mut, True, True, config), collect(test_seeds, mut, True, True, config)
        rows[name] = {**evaluate(test, fit(dev, MASKS["full"]), MASKS["full"]), **match_quality(test)}
    return {"name": "ablation", "disclaimer": DISCLAIMER, "rows": _rows(rows),
            "condition": "node types and event labels removed; 10% noise nodes; 20% timestamp and frequency perturbation"}


# ---------------------------------------------------------------------- runner
EXPERIMENTS = ("identity", "individualization", "temporal", "mutation", "cross_env", "baselines", "ablation")


def run_all_experiments(output_dir: str | Path = "results", quick: bool = False, include_ged: bool = True,
                        only: tuple[str, ...] | None = None) -> dict:
    """Run experiments and write ``experiments.json`` plus CSV tables to ``output_dir``."""
    dev, test = ((100,), (200, 201)) if quick else ((100, 101), (200, 201, 202))
    selected = only or EXPERIMENTS
    runners = {
        "identity": lambda: exp1_identity_robustness(test),
        "individualization": lambda: exp2_cr_vs_individualization(dev, test),
        "temporal": lambda: exp3_temporal_contribution(dev, test),
        "mutation": lambda: exp4_mutation_robustness(dev, test, (0.1, 0.3) if quick else (0.05, 0.1, 0.2, 0.3)),
        "cross_env": lambda: exp5_cross_environment(dev, test),
        "baselines": lambda: exp6_baselines(dev, test, include_ged),
        "ablation": lambda: exp7_ablation(dev, test),
    }
    unknown = [s for s in selected if s not in runners]
    if unknown:
        raise ValueError(f"unknown experiment(s) {unknown}; choose from {list(runners)}")
    results = {"disclaimer": DISCLAIMER, "quick_mode": quick, "dev_seeds": list(dev), "test_seeds": list(test),
               "default_flag_threshold": DEFAULT_RISK_THRESHOLD, "experiments": {}}
    for key in selected:
        print(f"running {key} ...", flush=True)
        results["experiments"][key] = runners[key]()
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "experiments.json").write_text(json.dumps(results, indent=2, sort_keys=True, default=float) + "\n",
                                             encoding="utf-8")
    _write_csvs(results, folder)
    return results


def _flatten_tables(results: dict) -> dict[str, list[dict]]:
    tables: dict[str, list[dict]] = {}
    for key, exp in results["experiments"].items():
        if "conditions" in exp:
            for condition, rows in exp["conditions"].items():
                tables[f"{key}__{condition}"] = rows
        if "rows" in exp:
            tables[key] = exp["rows"]
        if key == "mutation":
            flat = []
            for kind, value in exp["results"].items():
                for row in (value if isinstance(value, list) else [{"level": 0.0, **value}]):
                    flat.append({"mutation": kind, **row})
            tables["mutation"] = flat
    return tables


def _write_csvs(results: dict, folder: Path) -> None:
    for name, rows in _flatten_tables(results).items():
        rows = [{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()} for r in rows]
        columns = list(dict.fromkeys(k for r in rows for k in r))
        with (folder / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run RefineMatch synthetic-data experiments.")
    parser.add_argument("--output", default="results", help="output directory (default: results)")
    parser.add_argument("--quick", action="store_true", help="fewer seeds/levels for a fast run")
    parser.add_argument("--no-ged", action="store_true", help="skip the (slow) graph-edit-distance baseline")
    parser.add_argument("--only", default="", help=f"comma list from {','.join(EXPERIMENTS)}")
    args = parser.parse_args(argv)
    only = tuple(s for s in args.only.split(",") if s) or None
    run_all_experiments(args.output, args.quick, not args.no_ged, only)
    print(f"done. wrote {Path(args.output) / 'experiments.json'} and CSV tables. {DISCLAIMER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
