"""Tests for src.matching.graph_matcher: positive, negative and difficult cases."""

import random
from datetime import datetime, timedelta

import networkx as nx
import pytest

from src.core.exceptions import InvalidGraphError
from src.core.models import EventRecord, MatchResult
from src.graph.anonymizer import anonymize_graph
from src.graph.graph_builder import build_temporal_graph
from src.matching.graph_matcher import MatcherConfig, match_graphs, match_graphs_detailed

T0 = datetime(2024, 1, 1)


def mk(spec):
    return build_temporal_graph(
        [EventRecord(T0 + timedelta(seconds=i), s, d, t) for i, (s, d, t) in enumerate(spec)])


APP = [("c", "w", "http"), ("w", "a1", "rpc"), ("w", "a2", "rpc"), ("a1", "db", "sql"), ("a2", "db", "sql")]
APP_RENAMED = [("x1", "x2", "http"), ("x2", "x4", "rpc"), ("x2", "x3", "rpc"), ("x4", "x5", "sql"), ("x3", "x5", "sql")]


def cyc(names):
    return [(names[i], names[(i + 1) % len(names)], "e") for i in range(len(names))]


def preserves_edges(ref, obs, mapping):
    return all(obs.graph.has_edge(mapping[u], mapping[v]) for u, v in ref.graph.edges)


def test_identity_renamed_graph_matches_perfectly_and_preserves_edges():
    ref, obs = mk(APP), mk(APP_RENAMED)
    result = match_graphs(ref, obs)
    assert isinstance(result, MatchResult)
    assert result.similarity == 1.0 and len(result.node_mapping) == 5
    assert preserves_edges(ref, obs, result.node_mapping)
    assert result.unmatched_reference_nodes == [] and result.unmatched_observed_nodes == []
    assert 0.0 < result.confidence <= 1.0


def test_similarity_independent_of_identifiers_and_anonymization():
    ref = mk(APP)
    sims = {match_graphs(ref, mk(spec)).similarity for spec in (
        APP_RENAMED,
        [(f"host-{ord(s[0])}{s}", f"host-{ord(d[0])}{d}", t) for s, d, t in APP],
    )}
    assert sims == {1.0}
    assert match_graphs(anonymize_graph(ref), anonymize_graph(mk(APP_RENAMED))).similarity == 1.0


def test_random_renamings_always_give_perfect_similarity():
    rng = random.Random(5)
    ref = mk(APP)
    for _ in range(10):
        names = {n: f"id{rng.random():.6f}" for n in "c w a1 a2 db".split()}
        obs = mk([(names[s], names[d], t) for s, d, t in APP])
        assert match_graphs(ref, obs).similarity == 1.0


def test_noise_nodes_reduce_similarity_slightly_but_pattern_is_found():
    ref = mk(APP)
    noisy = mk(APP_RENAMED + [("n1", "x2", "dns"), ("x5", "n2", "ntp")])
    result = match_graphs(ref, noisy)
    assert 0.85 < result.similarity < 1.0
    assert preserves_edges(ref, noisy, result.node_mapping)
    assert set(result.unmatched_observed_nodes) == {"n1", "n2"}


def test_deleted_edges_lower_similarity():
    ref = mk(APP)
    partial = mk(APP_RENAMED[:-1])
    full = match_graphs(ref, mk(APP_RENAMED)).similarity
    assert match_graphs(ref, partial).similarity < full


def test_unrelated_structure_scores_low():
    ref = mk(APP)
    scan = mk([("s", f"t{i}", "probe") for i in range(5)])
    result = match_graphs(ref, scan)
    assert result.similarity < 0.2 and result.node_mapping == {}


def test_edge_type_changes_matter():
    ref = mk(APP)
    changed = mk([(s, d, "other" if t == "sql" else t) for s, d, t in APP_RENAMED])
    assert match_graphs(ref, changed).similarity < match_graphs(ref, mk(APP_RENAMED)).similarity


def test_one_wl_hard_case_c6_vs_two_c3_is_not_called_identical():
    c6 = mk(cyc(list("abcdef")))
    two_c3 = mk(cyc(list("abc")) + cyc(list("def")))
    assert not nx.is_isomorphic(c6.graph, two_c3.graph)
    assert match_graphs(c6, two_c3).similarity < 1.0
    assert match_graphs(c6, mk(cyc(list("uvwxyz")))).similarity == 1.0


def test_symmetric_twins_are_resolved_with_paired_individualization():
    details = match_graphs_detailed(mk(APP), mk(APP_RENAMED))
    assert details.match.individualization_count == len(details.trace) >= 1
    step = details.trace[0]
    assert step.candidate_pairs_after < step.candidate_pairs_before


def test_cr_only_config_does_not_individualize_but_still_matches_symmetric_case():
    details = match_graphs_detailed(mk(APP), mk(APP_RENAMED), MatcherConfig(selection="none"))
    assert details.match.individualization_count == 0 and details.match.similarity == 1.0


def test_individualization_budget_is_respected():
    star = mk([("h", f"l{i}", "e") for i in range(6)])
    obs = mk([("H", f"L{i}", "e") for i in range(6)])
    for budget in (0, 1, 2):
        d = match_graphs_detailed(star, obs, MatcherConfig(max_individualizations=budget))
        assert d.match.individualization_count <= budget
    d = match_graphs_detailed(star, obs, MatcherConfig(max_branch_evaluations=1))
    assert d.branch_evaluations <= 1


def test_random_selection_is_reproducible():
    cfg = MatcherConfig(selection="random", seed=3)
    a = match_graphs_detailed(mk(APP), mk(APP_RENAMED), cfg)
    b = match_graphs_detailed(mk(APP), mk(APP_RENAMED), cfg)
    assert a.match == b.match


def test_deterministic_default_matching():
    a, b = match_graphs(mk(APP), mk(APP_RENAMED)), match_graphs(mk(APP), mk(APP_RENAMED))
    assert a == b


def test_graphs_of_different_sizes_and_empty_inputs():
    empty = build_temporal_graph([])
    assert match_graphs(empty, empty).similarity == 1.0
    assert match_graphs(empty, mk(APP)).similarity == 0.0
    r = match_graphs(mk(APP), empty)
    assert r.similarity == 0.0 and r.unmatched_reference_nodes == sorted("c w a1 a2 db".split())
    big = mk(APP_RENAMED + [(f"n{i}", f"n{i + 1}", "dns") for i in range(10)])
    assert match_graphs(mk(APP), big).similarity > 0.9


def test_validation():
    with pytest.raises(InvalidGraphError):
        match_graphs("x", mk(APP))
    with pytest.raises(InvalidGraphError):
        match_graphs_detailed(mk(APP), mk(APP), MatcherConfig(selection="nope"))
    with pytest.raises(InvalidGraphError):
        match_graphs_detailed(mk(APP), mk(APP), MatcherConfig(max_individualizations=-1))


def test_deleted_edge_still_finds_most_of_the_pattern():
    ref = mk(APP)
    partial = mk([s for s in APP_RENAMED if s != ("x2", "x4", "rpc")])
    result = match_graphs(ref, partial)
    assert len(result.node_mapping) >= 4 and 0.5 < result.similarity < 1.0


def test_symmetric_twin_assignment_follows_time_not_names():
    # Observed twins carry names that sort in the OPPOSITE order of their timing.
    ref = mk([("c", "w", "http"), ("w", "a1", "rpc"), ("w", "a2", "rpc"), ("a1", "db", "sql"), ("a2", "db", "sql")])
    obs = mk([("c2", "w2", "http"), ("w2", "zz", "rpc"), ("w2", "aa", "rpc"), ("zz", "d2", "sql"), ("aa", "d2", "sql")])
    result = match_graphs(ref, obs)
    assert result.node_mapping["a1"] == "zz" and result.node_mapping["a2"] == "aa"
