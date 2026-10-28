"""Tests for 1-to-1 node assignment using the Hungarian algorithm."""

from src.matching.node_assignment import assign_nodes


def test_assign_nodes_optimal_1_to_1():
    # 3 reference nodes, 4 observed nodes
    reference_nodes = ["ref_A", "ref_B", "ref_C"]
    observed_nodes = ["obs_1", "obs_2", "obs_3", "obs_4"]

    # ref_A has multiple choices: ["obs_1", "obs_2"]
    # ref_B only has one choice: ["obs_1"]
    # ref_C has one choice: ["obs_3"]
    # obs_4 is an extra node with no match
    candidates = {
        "ref_A": ["obs_1", "obs_2"],
        "ref_B": ["obs_1"],
        "ref_C": ["obs_3"],
    }

    mapping, similarity = assign_nodes(reference_nodes, observed_nodes, candidates)

    # ref_B must take obs_1, allowing ref_A to take obs_2 (optimal bipartite resolution)
    assert mapping["ref_B"] == "obs_1"
    assert mapping["ref_A"] == "obs_2"
    assert mapping["ref_C"] == "obs_3"

    # Ensure no observed node is assigned twice (strict 1-to-1)
    assigned_obs = list(mapping.values())
    assert len(assigned_obs) == len(set(assigned_obs))

    # All 3 reference nodes matched successfully
    assert similarity == 1.0


def test_assign_nodes_partial_match():
    reference_nodes = ["ref_1", "ref_2", "ref_3"]
    observed_nodes = ["obs_1", "obs_2"]

    # ref_1 and ref_2 compete for obs_1; ref_3 has no candidates
    candidates = {
        "ref_1": ["obs_1"],
        "ref_2": ["obs_1"],
        "ref_3": [],
    }

    mapping, similarity = assign_nodes(reference_nodes, observed_nodes, candidates)

    # Only one of ref_1/ref_2 can get obs_1
    assert len(mapping) == 1
    assert "ref_3" not in mapping
    assert mapping.get("ref_1") == "obs_1" or mapping.get("ref_2") == "obs_1"

    # Similarity score should be 1 / 3
    assert round(similarity, 4) == round(1.0 / 3.0, 4)


def test_assign_nodes_empty_inputs():
    # Empty reference nodes
    mapping, similarity = assign_nodes([], ["obs_1"], {})
    assert mapping == {}
    assert similarity == 0.0

    # Empty observed nodes
    mapping, similarity = assign_nodes(["ref_1"], [], {"ref_1": []})
    assert mapping == {}
    assert similarity == 0.0
