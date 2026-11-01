"""Main execution pipeline for RefineMatch.

Integrates:
- Member 1: Weisfeiler-Leman Color Refinement (initialize_colors, refine_once)
- Member 2: AGIR Ambiguity Individualization & Hungarian Node Assignment
- Member 3: Pattern Bank & Telemetry Ingestion (pattern_to_temporal_graph, synthetic_generator)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.models import MatchResult
from src.graph.anonymizer import anonymize_graph
from src.ingestion.pattern_bank import pattern_definitions, pattern_to_temporal_graph
from src.ingestion.synthetic_generator import generate_synthetic_graph
from src.matching.candidate_generation import generate_candidates
from src.matching.node_assignment import assign_nodes
from src.refinement.ambiguity import find_ambiguous_classes
from src.refinement.color_refinement import initialize_colors, refine_once
from src.refinement.individualization import individualize_graph
from src.scoring.structural_score import calculate_structural_similarity


def run_pipeline(
    pattern_id: str = "SUSP_SYN_003",
    generator_name: str = "scanning_like",
    seed: int = 42,
    max_individualizations: int = 10,
) -> tuple[MatchResult, float]:
    """Execute end-to-end matching pipeline across Members 1, 2, and 3."""
    print("=" * 70)
    print("RefineMatch End-to-End Pipeline Execution")
    print("=" * 70)

    # ----------------------------------------------------------------------- #
    # Step 1: Ingestion & Pattern Loading (Member 3)
    # ----------------------------------------------------------------------- #
    print("\n[Step 1 - Member 3] Ingesting Reference Pattern & Observed Telemetry...")
    all_defs = pattern_definitions()
    matching_defs = [d for d in all_defs if d.get("pattern_id") == pattern_id]
    if not matching_defs:
        # Fallback to the first available pattern definition
        pat_def = all_defs[0]
    else:
        pat_def = matching_defs[0]

    # Load reference attack pattern as official TemporalGraph
    ref_pattern = pattern_to_temporal_graph(pat_def)
    print(f"  Loaded reference pattern : '{pat_def['name']}' ({pat_def['pattern_id']})")
    print(f"  Reference graph nodes    : {len(ref_pattern.graph.nodes)} | Edges: {len(ref_pattern.graph.edges)}")

    # Ingest / synthesize observed network graph and anonymize identities
    raw_observed = generate_synthetic_graph(generator_name, seed=seed)
    observed = anonymize_graph(raw_observed)
    print(f"  Synthesized observed graph (seed={seed})")
    print(f"  Observed graph nodes     : {len(observed.graph.nodes)} | Edges: {len(observed.graph.edges)}")

    # ----------------------------------------------------------------------- #
    # Step 2: Base 1-WL Color Refinement (Member 1)
    # ----------------------------------------------------------------------- #
    print("\n[Step 2 - Member 1] Running 1-WL Color Refinement (Round 0 & 1)...")
    ref_res = initialize_colors(ref_pattern)
    ref_res = refine_once(ref_pattern, ref_res)

    obs_res = initialize_colors(observed)
    obs_res = refine_once(observed, obs_res)

    print(f"  Reference classes after 1-WL : {len(ref_res.color_classes)} (stable={ref_res.stable})")
    print(f"  Observed classes after 1-WL  : {len(obs_res.color_classes)} (stable={obs_res.stable})")

    # ----------------------------------------------------------------------- #
    # Step 3: AGIR Ambiguity Resolution Loop (Member 2 + Member 1)
    # ----------------------------------------------------------------------- #
    print("\n[Step 3 - Member 2 & 1] Executing AGIR Individualization & Refinement Loop...")
    ref_amb = find_ambiguous_classes(ref_res)
    obs_amb = find_ambiguous_classes(obs_res)
    print(f"  Initial ambiguous classes in reference: {len(ref_amb)}")
    print(f"  Initial ambiguous classes in observed : {len(obs_amb)}")

    # AGIR while loop: individualize and re-run refine_once until stable
    stable = False
    step_count = 0
    while not stable and step_count < max_individualizations:
        ambiguous = find_ambiguous_classes(ref_res)
        if not ambiguous:
            stable = True
            break
        print(f"  [AGIR Iteration {step_count + 1}] Individualizing ambiguous class: {list(ambiguous.keys())[0][:8]}...")
        ref_res = individualize_graph(ref_pattern, ref_res)
        ref_res = refine_once(ref_pattern, ref_res)
        step_count += 1
        if not find_ambiguous_classes(ref_res):
            stable = True

    print(f"  AGIR Phase complete in {step_count} individualization step(s). Final stable={stable}.")

    # ----------------------------------------------------------------------- #
    # Step 4: Candidate Generation & Hungarian Assignment (Member 2)
    # ----------------------------------------------------------------------- #
    print("\n[Step 4 - Member 2] Candidate Pruning & Optimal Hungarian Node Assignment...")
    candidates = generate_candidates(
        reference_graph=ref_pattern.graph,
        observed_graph=observed.graph,
        reference_colors=ref_res.node_colors,
        observed_colors=obs_res.node_colors,
        allow_relaxed=True,
    )

    mapping = assign_nodes(
        candidate_map=candidates,
        reference_graph=ref_pattern.graph,
        observed_graph=observed.graph,
        reference_colors=ref_res.node_colors,
        observed_colors=obs_res.node_colors,
    )

    # ----------------------------------------------------------------------- #
    # Step 5: Structural Scoring & Results Compilation
    # ----------------------------------------------------------------------- #
    ref_nodes = set(ref_pattern.graph.nodes)
    obs_nodes = set(observed.graph.nodes)
    matched_nodes = sorted(mapping.keys())
    unmatched_ref = sorted(ref_nodes - set(matched_nodes))
    unmatched_obs = sorted(obs_nodes - set(mapping.values()))

    # Calculate confidence metric
    if ref_nodes and matched_nodes:
        uniqueness = sum(1.0 / max(1, len(candidates.get(u, [None]))) for u in matched_nodes) / len(matched_nodes)
        confidence = (len(matched_nodes) / len(ref_nodes)) * uniqueness
    else:
        confidence = 0.0

    match_result = MatchResult(
        similarity=0.0,
        node_mapping=mapping,
        matched_nodes=matched_nodes,
        unmatched_observed_nodes=unmatched_obs,
        unmatched_reference_nodes=unmatched_ref,
        individualization_count=step_count,
        confidence=confidence,
    )

    similarity_score = calculate_structural_similarity(ref_pattern, observed, match_result)
    match_result.similarity = similarity_score

    # ----------------------------------------------------------------------- #
    # Step 6: Console Output of Mapping & Structural Score
    # ----------------------------------------------------------------------- #
    print("\n" + "=" * 70)
    print("FINAL MATCH RESULTS")
    print("=" * 70)
    print(f"Structural Similarity Score : {similarity_score:.4f} / 1.0000")
    print(f"Match Confidence            : {confidence:.4f}")
    print(f"Matched Node Pairs ({len(mapping)}):")
    for ref_node, obs_node in sorted(mapping.items()):
        print(f"    {ref_node:>10}  <--->  {obs_node:<10}")

    if unmatched_ref:
        print(f"Unmatched Reference Nodes   : {unmatched_ref}")
    if unmatched_obs:
        print(f"Unmatched Observed Nodes    : {unmatched_obs}")
    print("=" * 70)

    return match_result, similarity_score


def main() -> None:
    """Entry point for command line invocation."""
    run_pipeline()


if __name__ == "__main__":
    main()
