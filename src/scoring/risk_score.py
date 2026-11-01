"""Risk aggregation into an explainable, NON-CONCLUSIVE suspicious-pattern level.

final = w_s*structural + w_t*temporal + w_f*frequency + w_c*normalized_contrastive

Weights are configurable and must sum to 1. The defaults in ``config`` are
PROVISIONAL, not validated. :func:`tune_weights_and_threshold` fits weights and
a flag threshold on a labelled development set by exhaustive grid search
(deterministic); validate on held-out data before relying on them.

Levels: ``high`` (final >= flag threshold, "flag for analyst review"),
``medium``, ``low``. A guard downgrades ``high`` to ``medium`` when the
observation is NOT more similar to the suspicious-like bank than to the benign
bank (contrastive <= 0). A flag is a prioritisation hint, never a confirmed
attack.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product

from src.core.config import DEFAULT_MEDIUM_RISK_THRESHOLD, DEFAULT_RISK_THRESHOLD, DEFAULT_RISK_WEIGHTS
from src.core.exceptions import InvalidScoreInputError
from src.core.models import ScoreResult
from src.scoring.contrastive_score import calculate_contrastive_score, normalize_contrastive


@dataclass(frozen=True)
class RiskWeights:
    """Non-negative weights for (structural, temporal, frequency, contrastive), summing to 1."""

    structural: float = DEFAULT_RISK_WEIGHTS[0]
    temporal: float = DEFAULT_RISK_WEIGHTS[1]
    frequency: float = DEFAULT_RISK_WEIGHTS[2]
    contrastive: float = DEFAULT_RISK_WEIGHTS[3]

    def __post_init__(self) -> None:
        values = self.as_tuple()
        if any((not isinstance(v, (int, float))) or math.isnan(v) or v < 0 for v in values):
            raise InvalidScoreInputError(f"risk weights must be non-negative numbers, got {values}")
        if abs(sum(values) - 1.0) > 1e-6:
            raise InvalidScoreInputError(f"risk weights must sum to 1, got {sum(values):.6f}")

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.structural, self.temporal, self.frequency, self.contrastive)


def _unit(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or math.isnan(value) \
            or not -1e-9 <= value <= 1 + 1e-9:
        raise InvalidScoreInputError(f"{name} must be a number in [0, 1], got {value!r}")
    return max(0.0, min(1.0, float(value)))


def level_for(final: float, contrastive: float, flag_threshold: float = DEFAULT_RISK_THRESHOLD,
              medium_threshold: float = DEFAULT_MEDIUM_RISK_THRESHOLD, guard: bool = True) -> str:
    """Risk level for a final score (see module docstring for the guard)."""
    if final >= flag_threshold:
        return "medium" if guard and contrastive <= 0 else "high"
    return "medium" if final >= medium_threshold else "low"


def calculate_risk_score(
    structural_score: float,
    temporal_score: float,
    frequency_score: float,
    attack_similarity: float,
    benign_similarity: float,
    weights: RiskWeights | None = None,
    use_contrastive_guard: bool = True,
    flag_threshold: float = DEFAULT_RISK_THRESHOLD,
    medium_threshold: float = DEFAULT_MEDIUM_RISK_THRESHOLD,
) -> ScoreResult:
    """Combine evidence into a :class:`ScoreResult` (all inputs in [0, 1])."""
    s = _unit("structural_score", structural_score)
    t = _unit("temporal_score", temporal_score)
    f = _unit("frequency_score", frequency_score)
    attack = _unit("attack_similarity", attack_similarity)
    benign = _unit("benign_similarity", benign_similarity)
    w = weights or RiskWeights()
    contrastive = calculate_contrastive_score(attack, benign)
    final = (w.structural * s + w.temporal * t + w.frequency * f
             + w.contrastive * normalize_contrastive(contrastive))
    final = max(0.0, min(1.0, final))
    return ScoreResult(
        structural_score=s, temporal_score=t, frequency_score=f,
        attack_similarity=attack, benign_similarity=benign, contrastive_score=contrastive,
        risk_level=level_for(final, contrastive, flag_threshold, medium_threshold, use_contrastive_guard),
        final_score=final)


def _f1(tp: int, fp: int, fn: int) -> float:
    return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)


def tune_weights_and_threshold(
    samples: list[tuple[float, float, float, float]],
    labels: list[bool],
    step: float = 0.1,
    guard: bool = True,
) -> tuple[RiskWeights, float, float]:
    """Grid-search weights and flag threshold maximising F1 on a labelled dev set.

    ``samples`` are ``(structural, temporal, frequency, contrastive_raw)`` with
    contrastive in [-1, 1]; ``labels`` True = suspicious. Returns
    ``(weights, threshold, f1)``. Among equal-F1 candidates the one closest to
    the documented defaults (L1 distance of weights plus threshold distance) is
    chosen, which avoids degenerate single-component weightings on separable
    data; remaining ties go to the earlier grid point, so results are
    deterministic. Raises on empty or mismatched data.
    """
    if not samples or len(samples) != len(labels):
        raise InvalidScoreInputError("samples and labels must be non-empty and equal in length")
    if not 0 < step <= 0.5:
        raise InvalidScoreInputError("step must be in (0, 0.5]")
    n = round(1 / step)
    thresholds = [round(0.30 + 0.05 * i, 2) for i in range(13)]
    best = (-1.0, None, None, math.inf)
    for a, b, c in product(range(n + 1), repeat=3):
        if a + b + c > n:
            continue
        w = (a * step, b * step, c * step, (n - a - b - c) * step)
        finals = [w[0] * s + w[1] * t + w[2] * f + w[3] * normalize_contrastive(k)
                  for s, t, f, k in samples]
        for threshold in thresholds:
            tp = fp = fn = 0
            for final, (_, _, _, k), label in zip(finals, samples, labels):
                predicted = final >= threshold and (k > 0 or not guard)
                tp += predicted and label
                fp += predicted and not label
                fn += (not predicted) and label
            score = _f1(tp, fp, fn)
            distance = (sum(abs(x - d) for x, d in zip(w, DEFAULT_RISK_WEIGHTS))
                        + abs(threshold - DEFAULT_RISK_THRESHOLD))
            if score > best[0] + 1e-12 or (abs(score - best[0]) <= 1e-12 and distance < best[3] - 1e-12):
                best = (score, w, threshold, distance)
    score, w, threshold, _ = best
    return RiskWeights(*w), threshold, score
