"""Evaluation metrics. All rates are in [0, 1]; undefined ratios (0/0) return 0.0."""

from __future__ import annotations

import statistics
import time
import tracemalloc
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from src.core.exceptions import InvalidScoreInputError


def _counts(**values: int) -> None:
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InvalidScoreInputError(f"{name} must be a non-negative int, got {value!r}")


def precision(tp: int, fp: int) -> float:
    """TP / (TP + FP)."""
    _counts(tp=tp, fp=fp)
    return tp / (tp + fp) if tp + fp else 0.0


def recall(tp: int, fn: int) -> float:
    """TP / (TP + FN) (true-positive rate)."""
    _counts(tp=tp, fn=fn)
    return tp / (tp + fn) if tp + fn else 0.0


def f1_score(tp: int, fp: int, fn: int) -> float:
    """Harmonic mean of precision and recall."""
    p, r = precision(tp, fp), recall(tp, fn)
    return 2 * p * r / (p + r) if p + r else 0.0


def false_positive_rate(fp: int, tn: int) -> float:
    """FP / (FP + TN)."""
    _counts(fp=fp, tn=tn)
    return fp / (fp + tn) if fp + tn else 0.0


def false_negative_rate(fn: int, tp: int) -> float:
    """FN / (FN + TP)."""
    _counts(fn=fn, tp=tp)
    return fn / (fn + tp) if fn + tp else 0.0


def confusion_counts(y_true: Sequence[bool], y_pred: Sequence[bool]) -> dict[str, int]:
    """Confusion counts (positive class = ``True`` = suspicious-like)."""
    if len(y_true) != len(y_pred):
        raise InvalidScoreInputError("y_true and y_pred must have equal length")
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    return {"tp": tp, "fp": fp, "tn": len(y_true) - tp - fp - fn, "fn": fn}


def classification_report(y_true: Sequence[bool], y_pred: Sequence[bool]) -> dict[str, float]:
    """Counts plus precision, recall, F1, FPR and FNR."""
    c = confusion_counts(y_true, y_pred)
    return {**c, "precision": precision(c["tp"], c["fp"]), "recall": recall(c["tp"], c["fn"]),
            "f1": f1_score(c["tp"], c["fp"], c["fn"]),
            "fpr": false_positive_rate(c["fp"], c["tn"]), "fnr": false_negative_rate(c["fn"], c["tp"])}


def calculate_runtime(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """Call ``func`` and return ``(result, wall-clock seconds)``."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    return result, time.perf_counter() - start


def measure_peak_memory(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, int]:
    """Call ``func`` and return ``(result, peak Python-allocated bytes)`` via tracemalloc."""
    already = tracemalloc.is_tracing()
    if not already:
        tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        result = func(*args, **kwargs)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        if not already:
            tracemalloc.stop()
    return result, peak


def matching_accuracy(predicted: Mapping[str, str], truth: Mapping[str, str]) -> float:
    """Share of ground-truth pairs the predicted mapping reproduces (1.0 if truth is empty).

    Caveat: structurally equivalent (automorphic) nodes are interchangeable, so
    swapping them counts as an error here although the structure is identical.
    """
    if not truth:
        return 1.0
    return sum(1 for k, v in truth.items() if predicted.get(k) == v) / len(truth)


def calculate_robustness_curve(results: Mapping[float, Sequence[float]]) -> list[dict[str, float]]:
    """Summarise ``{noise level: [scores]}`` as a sorted list of mean/min/max/std points."""
    curve = []
    for level in sorted(results):
        values = list(results[level])
        if not values:
            raise InvalidScoreInputError(f"no scores for level {level}")
        curve.append({"level": level, "mean": statistics.fmean(values), "min": min(values),
                      "max": max(values), "std": statistics.pstdev(values), "n": len(values)})
    return curve
