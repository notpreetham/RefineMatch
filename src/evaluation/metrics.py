"""Detection metrics (no sklearn dependency)."""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np


def roc_auc(y: Sequence[int], s: Sequence[float]) -> float:
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # Mann-Whitney U with tie handling
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def average_precision(y: Sequence[int], s: Sequence[float]) -> float:
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    order = np.argsort(-s, kind="mergesort")
    y = y[order]
    if y.sum() == 0:
        return float("nan")
    tp = np.cumsum(y)
    prec = tp / np.arange(1, len(y) + 1)
    return float((prec * y).sum() / y.sum())


def at_threshold(y: Sequence[int], s: Sequence[float], thr: float) -> Dict[str, float]:
    y, s = np.asarray(y), np.asarray(s, dtype=float)
    pred = s >= thr
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    tn = int((~pred & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return dict(threshold=thr, precision=prec, recall=rec, f1=f1, fpr=fpr, tp=tp, fp=fp, fn=fn, tn=tn)


def threshold_for_fpr(benign_scores: Sequence[float], target_fpr: float = 0.05) -> float:
    """Smallest threshold whose FPR on calibration benign scores is <= target."""
    b = np.sort(np.asarray(benign_scores, dtype=float))
    if len(b) == 0:
        return 0.5
    k = int(np.ceil((1 - target_fpr) * len(b))) - 1
    k = min(max(k, 0), len(b) - 1)
    return float(np.nextafter(b[k], np.inf))


def summarize(y, s, thr) -> Dict[str, float]:
    d = at_threshold(y, s, thr)
    d.update(auc=roc_auc(y, s), ap=average_precision(y, s))
    return d
