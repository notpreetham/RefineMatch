"""Analyst-facing explanations. Wording is deliberately non-conclusive.

The generator never states that an attack occurred; it reports how similar the
behaviour is to a *suspicious-like synthetic or curated pattern*, how that
compares with benign patterns, and what the temporal evidence says.
"""

from __future__ import annotations

from src.core.models import MatchResult, ScoreResult

DISCLAIMER = ("This is a suspicious-pattern flag for analyst review, not a confirmed attack. "
              "Similarity to a pattern does not prove malicious intent.")


def _band(value: float) -> str:
    return "high" if value >= 0.8 else "moderate" if value >= 0.5 else "low"


def generate_match_explanation(
    match: MatchResult,
    score: ScoreResult,
    pattern_name: str | None = None,
    benign_pattern_name: str | None = None,
    identity_changed: bool | None = None,
) -> dict:
    """Build the explanation dict (keys per blueprint section 9, plus extras)."""
    name = pattern_name or "an unnamed suspicious-like pattern"
    structural = (f"Structural similarity to {name} is {score.structural_score:.2f} "
                  f"({_band(score.structural_score)}); {len(match.matched_nodes)} reference node(s) "
                  f"matched, {len(match.unmatched_reference_nodes)} unmatched, "
                  f"{len(match.unmatched_observed_nodes)} extra observed node(s) ignored.")
    temporal = (f"Event-order and ordering consistency score {score.temporal_score:.2f} "
                f"({_band(score.temporal_score)}); frequency-shape similarity {score.frequency_score:.2f} "
                f"({_band(score.frequency_score)}).")
    identity = ("Matching used only node types, edge types, direction, degrees and refinement colors; "
                "hostnames, IP addresses and other identifiers were not used.")
    if identity_changed is True:
        identity += " Identifiers differ between the observed graph and the reference pattern."
    elif identity_changed is False:
        identity += " Identifiers were unchanged in this comparison."
    if match.individualization_count:
        identity += f" {match.individualization_count} ambiguity-guided individualization step(s) were used."
    benign_name = f" ({benign_pattern_name})" if benign_pattern_name else ""
    if score.contrastive_score > 0:
        benign = (f"The closest benign pattern{benign_name} is less similar ({score.benign_similarity:.2f}) "
                  f"than the suspicious-like pattern ({score.attack_similarity:.2f}).")
    else:
        benign = (f"The closest benign pattern{benign_name} is at least as similar "
                  f"({score.benign_similarity:.2f}) as the suspicious-like pattern "
                  f"({score.attack_similarity:.2f}); this weakens the evidence.")
    factors = [
        ("structural match", score.structural_score), ("temporal evidence", score.temporal_score),
        ("frequency match", score.frequency_score), ("contrast vs benign", (score.contrastive_score + 1) / 2)]
    top = max(factors, key=lambda item: item[1])
    summary = {"high": f"Flagged for analyst investigation: behaviour resembles {name}.",
               "medium": f"Borderline: partial resemblance to {name}; review if context warrants.",
               "low": f"Low resemblance to {name}; no flag raised."}[score.risk_level]
    return {
        "matched_pattern": pattern_name,
        "structural_evidence": structural,
        "temporal_evidence": temporal,
        "identity_independence_evidence": identity,
        "benign_comparison": benign,
        "risk_level": score.risk_level,
        "final_score": score.final_score,
        "strongest_factor": top[0],
        "summary": summary,
        "disclaimer": DISCLAIMER,
    }
