"""Tests for src.robustness.mutation_engine."""

import pytest

from src.core.exceptions import InvalidGraphError
from src.graph.anonymizer import anonymize_graph
from src.ingestion.synthetic_generator import generate_synthetic_graph
from src.matching.graph_matcher import match_graphs
from src.robustness.mutation_engine import (
    apply_mutations, delete_edges, insert_benign_nodes, insert_edges, is_identity_only,
    perturb_frequency, perturb_timestamps, rename_identities, rewire_edges)

G = generate_synthetic_graph("multi_server_application", 3)


def snapshot(tg):
    return (sorted(tg.graph.nodes), sorted((u, v, a["weight"]) for u, v, a in tg.graph.edges(data=True)),
            [(e.timestamp, e.source, e.destination, e.event_type) for e in tg.events])


@pytest.mark.parametrize("fn", [insert_benign_nodes, insert_edges, delete_edges, rewire_edges,
                                perturb_timestamps, perturb_frequency])
def test_mutations_are_reproducible_and_do_not_modify_input(fn):
    before = snapshot(G)
    a, b, c = fn(G, 0.3, 11), fn(G, 0.3, 11), fn(G, 0.3, 12)
    assert snapshot(a) == snapshot(b) and snapshot(G) == before
    assert snapshot(a) != snapshot(G)
    assert a.graph.number_of_edges() >= 0 and snapshot(c) is not None


def test_rename_is_identity_only_and_structure_preserving():
    renamed = rename_identities(G, 5)
    assert not set(renamed.graph.nodes) & set(G.graph.nodes)
    assert renamed.graph.number_of_edges() == G.graph.number_of_edges()
    assert {a["role"] for _, a in renamed.graph.nodes(data=True)} == {a["role"] for _, a in G.graph.nodes(data=True)}
    assert {a["original_id"] for _, a in renamed.graph.nodes(data=True)} == set(G.graph.nodes)
    assert snapshot(rename_identities(G, 5)) == snapshot(renamed) != snapshot(rename_identities(G, 6))
    assert match_graphs(anonymize_graph(G), anonymize_graph(renamed)).similarity == 1.0
    assert is_identity_only([{"type": "rename_identities"}])
    assert not is_identity_only([{"type": "rename_identities"}, {"type": "delete_edges", "percentage": 0.1}])


def test_insert_benign_nodes_adds_noise_only():
    noisy = insert_benign_nodes(G, 0.4, 1)
    new = set(noisy.graph.nodes) - set(G.graph.nodes)
    assert len(new) == 2 and all(n.startswith("noise-") for n in new)
    assert all(noisy.graph.nodes[n]["role"] is None for n in new)
    assert all(G.graph.has_edge(u, v) or u in new or v in new for u, v in noisy.graph.edges)
    assert len(noisy.events) > len(G.events)
    assert all(G.start_time <= e.timestamp <= G.end_time for e in noisy.events)


def test_delete_edges_counts():
    n_edges = G.graph.number_of_edges()
    assert delete_edges(G, 0.0, 1).graph.number_of_edges() == n_edges
    assert delete_edges(G, 0.4, 1).graph.number_of_edges() == n_edges - 2   # round(0.4*5)=2
    assert delete_edges(G, 1.0, 1).graph.number_of_edges() == 0
    assert delete_edges(G, 0.01, 1).graph.number_of_edges() == n_edges - 1  # at least one if p>0


def test_edge_weights_stay_consistent_with_events_after_mutation():
    for fn in (perturb_frequency, delete_edges, insert_edges, rewire_edges):
        m = fn(G, 0.5, 4)
        for u, v, a in m.graph.edges(data=True):
            assert a["weight"] == sum(1 for e in m.events if (e.source, e.destination) == (u, v))


def test_perturb_frequency_keeps_edges_and_changes_counts():
    m = perturb_frequency(G, 1.0, 2)
    assert sorted(m.graph.edges) == sorted(G.graph.edges)
    assert any(m.graph.edges[e]["weight"] != G.graph.edges[e]["weight"] for e in G.graph.edges)
    assert all(a["weight"] >= 1 for _, _, a in m.graph.edges(data=True))


def test_perturb_timestamps_keeps_structure_changes_times_within_limit():
    m = perturb_timestamps(G, 1.0, 2, max_shift_seconds=5.0)
    assert sorted(m.graph.edges) == sorted(G.graph.edges) and len(m.events) == len(G.events)
    shifts = [abs((a.timestamp - b.timestamp).total_seconds()) for a, b in zip(G.events, m.events)]
    assert max(shifts) <= 5.0 and max(shifts) > 0


def test_insert_edges_and_rewire_change_topology():
    assert insert_edges(G, 0.4, 1).graph.number_of_edges() == G.graph.number_of_edges() + 2
    assert sorted(rewire_edges(G, 0.4, 1).graph.edges) != sorted(G.graph.edges)


def test_apply_mutations_sequence_reproducible_and_validated():
    spec = [{"type": "rename_identities"}, {"type": "insert_benign_nodes", "percentage": 0.2},
            {"type": "perturb_timestamps", "percentage": 0.2, "max_shift_seconds": 3.0}]
    assert snapshot(apply_mutations(G, spec, 9)) == snapshot(apply_mutations(G, spec, 9))
    assert snapshot(apply_mutations(G, spec, 9)) != snapshot(apply_mutations(G, spec, 10))
    assert snapshot(apply_mutations(G, [], 1)) == snapshot(G)
    with pytest.raises(InvalidGraphError, match="unknown mutation"):
        apply_mutations(G, [{"type": "explode"}], 1)
    with pytest.raises(InvalidGraphError, match="percentage"):
        apply_mutations(G, [{"type": "delete_edges"}], 1)


def test_input_validation_and_empty_graph():
    with pytest.raises(InvalidGraphError):
        delete_edges(G, 1.5, 1)
    with pytest.raises(InvalidGraphError):
        delete_edges(G, 0.1, "1")
    with pytest.raises(InvalidGraphError):
        delete_edges("graph", 0.1, 1)
    from src.graph.graph_builder import build_temporal_graph
    empty = build_temporal_graph([])
    for fn in (insert_benign_nodes, delete_edges, perturb_frequency, perturb_timestamps):
        assert fn(empty, 0.5, 1).graph.number_of_nodes() == 0
    assert rename_identities(empty, 1).graph.number_of_nodes() == 0
