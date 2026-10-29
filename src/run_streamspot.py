"""StreamSpot End-to-End Execution Script.

Parses real-world StreamSpot provenance graphs, executes 1-WL Color Refinement,
breaks structural symmetries using AGIR, and solves 1-to-1 node correspondence
using the Hungarian algorithm.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.models import MatchResult
from src.ingestion.streamspot_adapter import (
    list_streamspot_graph_ids,
    parse_streamspot_file,
)
from src.matching.candidate_generation import generate_candidates
from src.matching.node_assignment import assign_nodes
from src.refinement.color_refinement import initialize_colors, refine_once
from src.refinement.individualization import individualize_graph
from src.scoring.structural_score import calculate_structural_similarity


DEFAULT_STREAMSPOT_PATH = PROJECT_ROOT / "data" / "streamspot" / "all.tsv"


def run_streamspot_pipeline(
    dataset_path: str | Path = DEFAULT_STREAMSPOT_PATH,
    max_agir_iterations: int = 20,
) -> None:
    """Run RefineMatch end-to-end on StreamSpot graphs."""
    path = Path(dataset_path)

    # 1. Dataset verification & graceful exit if missing
    if not path.is_file():
        print("=" * 75)
        print("ERROR: StreamSpot Dataset Not Found")
        print("=" * 75)
        print(f"Looked for dataset at: {path.resolve()}")
        print("\nPlease download the StreamSpot dataset (all.tsv) and place it here:")
        print(f"  --> {path.parent.resolve() / 'all.tsv'}")
        print("\nExpected format: Headerless TSV with columns:")
        print("  source_id \\t source_type \\t destination_id \\t destination_type \\t edge_type \\t graph_id")
        print("=" * 75)
        sys.exit(1)

    print("=" * 75)
    print("RefineMatch: Real-World StreamSpot Pipeline Execution")
    print("=" * 75)
    print(f"Reading dataset: {path}")

    # 2. Extract graph IDs
    graph_ids = list_streamspot_graph_ids(str(path))
    if len(graph_ids) < 2:
        print(f"\n[ERROR] Found {len(graph_ids)} graph ID(s) in {path}. Need at least 2 graphs to perform matching.")
        sys.exit(1)

    ref_graph_id = graph_ids[0]
    obs_graph_id = graph_ids[1]

    print(f"\nDiscovered {len(graph_ids)} graphs in dataset.")
    print(f"  * Reference Pattern (Attack Target) : Graph ID '{ref_graph_id}'")
    print(f"  * Observed Network Telemetry Log    : Graph ID '{obs_graph_id}'")

    # 3. Parse graphs into TemporalGraph data contracts
    print("\n[Step 1] Ingesting graphs into TemporalGraph models...")
    ref_pattern = parse_streamspot_file(str(path), target_graph_id=ref_graph_id)
    obs_graph = parse_streamspot_file(str(path), target_graph_id=obs_graph_id)

    print(f"  Reference Graph : {ref_pattern.graph.number_of_nodes()} nodes, {ref_pattern.graph.number_of_edges()} edges, {len(ref_pattern.events)} events")
    print(f"  Observed Graph  : {obs_graph.graph.number_of_nodes()} nodes, {obs_graph.graph.number_of_edges()} edges, {len(obs_graph.events)} events")

    # 4. Refinement Phase (Member 1: 1-WL)
    print("\n[Step 2] Executing 1-WL Color Refinement (Member 1)...")
    ref_colors = initialize_colors(ref_pattern)
    ref_colors = refine_once(ref_pattern, ref_colors)

    obs_colors = initialize_colors(obs_graph)
    obs_colors = refine_once(obs_graph, obs_colors)

    print(f"  Reference color classes : {len(ref_colors.color_classes)} (stable={ref_colors.stable})")
    print(f"  Observed color classes  : {len(obs_colors.color_classes)} (stable={obs_colors.stable})")

    # 5. AGIR Phase (Member 2: Ambiguity-Guided Individualization)
    print("\n[Step 3] Executing AGIR Phase on Observed Graph (Member 2)...")
    agir_steps = 0
    while not obs_colors.stable and agir_steps < max_agir_iterations:
        indiv_res = individualize_graph(obs_graph, obs_colors)
        if indiv_res.stable:
            obs_colors = indiv_res
            break
        obs_colors = refine_once(obs_graph, indiv_res)
        agir_steps += 1

    print(f"  Observed AGIR completed in {agir_steps} individualization step(s). Final stable={obs_colors.stable}.")

    # Also resolve any remaining reference ambiguity for symmetrical pairing
    ref_steps = 0
    while not ref_colors.stable and ref_steps < max_agir_iterations:
        indiv_res = individualize_graph(ref_pattern, ref_colors)
        if indiv_res.stable:
            ref_colors = indiv_res
            break
        ref_colors = refine_once(ref_pattern, indiv_res)
        ref_steps += 1

    # 6. Matching Phase: Candidate Generation & Hungarian Assignment (Member 2)
    print("\n[Step 4] Candidate Generation & Hungarian Bipartite Matching (Member 2)...")
    candidates = generate_candidates(
        reference_graph=ref_pattern.graph,
        observed_graph=obs_graph.graph,
        reference_colors=ref_colors.node_colors,
        observed_colors=obs_colors.node_colors,
        allow_relaxed=True,
    )

    mapping = assign_nodes(
        candidate_map=candidates,
        reference_graph=ref_pattern.graph,
        observed_graph=obs_graph.graph,
        reference_colors=ref_colors.node_colors,
        observed_colors=obs_colors.node_colors,
    )

    # 7. Structural Scoring
    matched_nodes = sorted(mapping.keys())
    unmatched_obs = sorted(set(obs_graph.graph.nodes) - set(mapping.values()))
    unmatched_ref = sorted(set(ref_pattern.graph.nodes) - set(matched_nodes))

    confidence = len(matched_nodes) / max(1, ref_pattern.graph.number_of_nodes())

    match_result = MatchResult(
        similarity=0.0,
        node_mapping=mapping,
        matched_nodes=matched_nodes,
        unmatched_observed_nodes=unmatched_obs,
        unmatched_reference_nodes=unmatched_ref,
        individualization_count=agir_steps + ref_steps,
        confidence=confidence,
    )

    similarity_score = calculate_structural_similarity(ref_pattern, obs_graph, match_result)
    match_result.similarity = similarity_score

    # 8. Formatted Results Output
    print("\n" + "=" * 75)
    print("STREAMSPOT MATCH RESULTS")
    print("=" * 75)
    print(f"Target Reference Graph ID    : {ref_graph_id}")
    print(f"  - Nodes                    : {ref_pattern.graph.number_of_nodes()}")
    print(f"  - Edges                    : {ref_pattern.graph.number_of_edges()}")
    print(f"\nObserved Graph ID            : {obs_graph_id}")
    print(f"  - Nodes                    : {obs_graph.graph.number_of_nodes()}")
    print(f"  - Edges                    : {obs_graph.graph.number_of_edges()}")
    print("-" * 75)
    print(f"Total 1-to-1 Node Pairs      : {len(mapping)}")
    print(f"Reference Coverage           : {confidence * 100:.2f}%")
    print(f"Final Structural Similarity  : {similarity_score:.4f} / 1.0000")
    print("-" * 75)
    print("Sample Node Mapping (first 10 pairs):")
    for ref_node, obs_node in list(sorted(mapping.items()))[:10]:
        print(f"    {ref_node:>16}  <--->  {obs_node:<16}")
    if len(mapping) > 10:
        print(f"    ... and {len(mapping) - 10} more node pairs.")
    print("=" * 75)


def main() -> None:
    """CLI entry point."""
    target_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STREAMSPOT_PATH
    run_streamspot_pipeline(target_path)


if __name__ == "__main__":
    main()
