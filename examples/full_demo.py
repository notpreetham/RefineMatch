"""End-to-end synthetic demo: every pattern, renamed identities, full pipeline.

Run from the project root:  python examples/full_demo.py
All data is SYNTHETIC; "suspicious" means "generated with a suspicious-like shape".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.anonymizer import anonymize_graph  # noqa: E402
from src.ingestion.pattern_bank import load_default_banks  # noqa: E402
from src.ingestion.synthetic_generator import PATTERN_NAMES, generate_synthetic_graph, pattern_category  # noqa: E402
from src.pipeline import analyze_observed  # noqa: E402
from src.robustness.mutation_engine import apply_mutations  # noqa: E402


def main() -> None:
    attack, benign = load_default_banks()
    print(f"{'pattern (synthetic label)':42s} {'closest suspicious-like':26s} struct  final  level")
    for name in PATTERN_NAMES:
        # new seed = new identities/timing/counts; then rename again and add 10% noise nodes
        graph = generate_synthetic_graph(name, 42)
        mutated = apply_mutations(graph, [{"type": "rename_identities"},
                                          {"type": "insert_benign_nodes", "percentage": 0.1}], seed=7)
        result = analyze_observed(anonymize_graph(mutated), attack, benign, identity_changed=True)
        print(f"{name + ' (' + pattern_category(name) + ')':42s} {result.best_attack.pattern.pattern_id:26s} "
              f"{result.score.structural_score:5.2f}  {result.score.final_score:5.2f}  {result.score.risk_level}")
    print("\nExample explanation (last pattern):")
    for key in ("summary", "structural_evidence", "temporal_evidence", "identity_independence_evidence",
                "benign_comparison", "disclaimer"):
        print(f"  - {result.explanation[key]}")


if __name__ == "__main__":
    main()
