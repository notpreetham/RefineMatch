"""Tests for src.evaluation.experiments (helpers, determinism, CLI, regression for identity leak)."""

import json
import tempfile
from pathlib import Path

import pytest

from src.evaluation import experiments as ex
from src.evaluation.experiments import (
    MASKS, Fit, collect, evaluate, exp1_identity_robustness, fit, masked, neutralize, predict,
    role_truth, run_all_experiments, main)
from src.ingestion.synthetic_generator import generate_synthetic_graph
from src.scoring.risk_score import RiskWeights


def test_masking_zeroes_inactive_components():
    sample = (0.9, 0.8, 0.7, 0.5)
    assert masked(sample, MASKS["full"]) == sample
    assert masked(sample, MASKS["structure_only"]) == (0.9, 0.0, 0.0, -1.0)
    assert masked(sample, MASKS["no_contrastive"]) == (0.9, 0.8, 0.7, -1.0)


def test_predict_hand_checked_with_frozen_fit():
    f = Fit(RiskWeights(0.4, 0.2, 0.2, 0.2), 0.6, 1.0, True)
    assert predict((1.0, 1.0, 1.0, 1.0), f, MASKS["full"]) is True      # final 1.0, contrastive > 0
    assert predict((0.2, 0.2, 0.2, -0.5), f, MASKS["full"]) is False
    assert predict((1.0, 1.0, 1.0, -0.1), f, MASKS["full"]) is False    # guard: benign at least as similar
    assert predict((1.0, 1.0, 1.0, -0.1), Fit(f.weights, 0.6, 1.0, False), (1, 1, 1, 0)) is True


def test_neutralize_strips_labels_but_keeps_structure():
    g = generate_synthetic_graph("lateral_movement_like", 1)
    n = neutralize(g, True, True)
    assert sorted(n.graph.edges) == sorted(g.graph.edges)
    assert {a["node_type"] for _, a in n.graph.nodes(data=True)} == {"host"}
    assert {t for _, _, a in n.graph.edges(data=True) for t in a["edge_types"]} == {"event"}
    assert neutralize(g, False, False) is g
    assert {a["node_type"] for _, a in g.graph.nodes(data=True)} != {"host"}   # input untouched


def test_role_truth_pairs_nodes_by_role_only():
    a, b = generate_synthetic_graph("c2_like", 1), generate_synthetic_graph("c2_like", 2)
    truth = role_truth(a, b)
    assert len(truth) == 2 and all(a.graph.nodes[k]["role"] == b.graph.nodes[v]["role"] for k, v in truth.items())


def test_fit_and_evaluate_on_real_collected_data_are_deterministic():
    dev, test = collect((100,)), collect((200,))
    f1, f2 = fit(dev, MASKS["full"]), fit(dev, MASKS["full"])
    assert f1 == f2 and abs(sum(f1.weights.as_tuple()) - 1) < 1e-9
    report = evaluate(test, f1, MASKS["full"])
    assert report["n_test"] == 8 and report["tp"] + report["fp"] + report["tn"] + report["fn"] == 8
    assert report["f1"] == 1.0  # clean typed synthetic data is separable (documented as an easy case)


def test_identity_robustness_regression_raw_renamed_ids_match_original():
    summary = exp1_identity_robustness((200, 201))["summary"]
    for name in ("renamed_raw_ids", "renamed_then_anonymized"):
        assert summary[name]["max_abs_final_score_difference_vs_original"] < 1e-9
        assert summary[name]["same_risk_level_fraction"] == 1.0
        assert summary[name]["mean_role_exact_matching_accuracy"] == 1.0


def test_run_all_experiments_writes_files_and_is_deterministic():
    folder_a, folder_b = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
    first = run_all_experiments(folder_a, quick=True, only=("identity",))
    run_all_experiments(folder_b, quick=True, only=("identity",))
    assert (folder_a / "experiments.json").read_text() == (folder_b / "experiments.json").read_text()
    data = json.loads((folder_a / "experiments.json").read_text())
    assert "Synthetic-data demonstration only" in data["disclaimer"] and data["quick_mode"] is True
    assert first["experiments"]["identity"]["name"] == "identity_robustness"


def test_runner_rejects_unknown_experiment_and_cli_works():
    with pytest.raises(ValueError, match="unknown experiment"):
        run_all_experiments(tempfile.mkdtemp(), quick=True, only=("nope",))
    folder = tempfile.mkdtemp()
    assert main(["--output", folder, "--quick", "--only", "identity"]) == 0
    assert (Path(folder) / "experiments.json").is_file()
