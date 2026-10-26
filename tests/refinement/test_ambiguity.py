import networkx as nx
from src.core.models import RefinementResult
from src.refinement.ambiguity import find_ambiguous_classes, rank_ambiguous_classes


def test_ambiguity_detection_and_ranking():
    # Build a tiny 4-node cycle graph
    g = nx.cycle_graph(4, create_using=nx.DiGraph)

    # Mock RefinementResult where nodes 0, 1, 2 share 'color_A', and node 3 has unique 'color_B'
    mock_refinement = RefinementResult(
        node_colors={"0": "color_A", "1": "color_A", "2": "color_A", "3": "color_B"},
        color_classes={"color_A": ["0", "1", "2"], "color_B": ["3"]},
        iterations=2,
        stable=True,
    )

    ambiguous = find_ambiguous_classes(mock_refinement)
    assert "color_A" in ambiguous
    assert "color_B" not in ambiguous
    assert len(ambiguous["color_A"]) == 3

    ranked = rank_ambiguous_classes(g, mock_refinement)
    assert len(ranked) == 1
    assert ranked[0][0] == "color_A"