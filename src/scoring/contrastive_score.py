"""Contrastive comparison against an attack-like bank and a benign bank.

``contrastive = attack_similarity - benign_similarity`` in [-1, 1] (raw
difference; use :func:`normalize_contrastive` for [0, 1]). Positive values mean
the observation resembles the suspicious-like bank more than the benign bank.
The bank similarities are STRUCTURAL similarities from the graph matcher. This
is evidence for analyst review, not proof of an attack, and a benign bank that
lacks the observed behaviour will make anything look "suspicious".
"""

from __future__ import annotations

from src.core.exceptions import InvalidScoreInputError
from src.core.models import MatchResult, TemporalGraph
from src.matching.graph_matcher import MatcherConfig, match_graphs_detailed


def find_best_pattern_match(
    observed: TemporalGraph,
    patterns: list[TemporalGraph],
    config: MatcherConfig | None = None,
) -> tuple[float, int | None, MatchResult | None]:
    """Best ``(similarity, pattern_index, match)``; ``(0.0, None, None)`` for an empty bank."""
    best: tuple[float, int | None, MatchResult | None] = (0.0, None, None)
    for index, pattern in enumerate(patterns):
        match = match_graphs_detailed(pattern, observed, config).match
        if best[1] is None or match.similarity > best[0]:
            best = (match.similarity, index, match)
    return best


def find_best_attack_similarity(observed: TemporalGraph, attack_patterns: list[TemporalGraph]) -> float:
    """Highest structural similarity to any attack-like pattern (0.0 if none)."""
    return find_best_pattern_match(observed, attack_patterns)[0]


def find_best_benign_similarity(observed: TemporalGraph, benign_patterns: list[TemporalGraph]) -> float:
    """Highest structural similarity to any benign pattern (0.0 if none)."""
    return find_best_pattern_match(observed, benign_patterns)[0]


def calculate_contrastive_score(attack_similarity: float, benign_similarity: float) -> float:
    """``attack_similarity - benign_similarity`` in [-1, 1]; inputs must be in [0, 1]."""
    for name, value in (("attack_similarity", attack_similarity), ("benign_similarity", benign_similarity)):
        if not isinstance(value, (int, float)) or value != value or not -1e-9 <= value <= 1 + 1e-9:
            raise InvalidScoreInputError(f"{name} must be a number in [0, 1], got {value!r}")
    return float(attack_similarity) - float(benign_similarity)


def normalize_contrastive(contrastive: float) -> float:
    """Map a contrastive score from [-1, 1] to [0, 1]."""
    return max(0.0, min(1.0, (contrastive + 1.0) / 2.0))
