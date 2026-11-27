"""WL-subtree-style kernels over (temporal) colour histograms."""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, Iterable, List, Optional


def color_histogram(levels: List[Dict[str, int]], nodes: Optional[Iterable[str]] = None,
                    min_level: int = 1) -> Counter:
    """Histogram of (level, colour) pairs over ``nodes`` (all nodes if None)."""
    hist = Counter()
    for k, lv in enumerate(levels):
        if k < min_level:
            continue
        for v, c in lv.items():
            if nodes is None or v in nodes:
                hist[(k, c)] += 1
    return hist


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def containment(small: Counter, big: Counter) -> float:
    """Fraction of ``small``'s colour mass also present in ``big`` (multiset containment)."""
    tot = sum(small.values())
    if not tot:
        return 0.0
    return sum(min(v, big.get(k, 0)) for k, v in small.items()) / tot


def hashed_features(hist: Counter, dim: int = 1024) -> List[float]:
    """Fixed-length feature vector (feature hashing) for learning baselines."""
    vec = [0.0] * dim
    for (k, c), v in hist.items():
        vec[(c ^ (k * 0x9E3779B97F4A7C15)) % dim] += v
    s = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / s for x in vec]
