"""Baseline detectors (all expose ``fit(windows, roles)`` and ``score(events) -> float``).

* ``WLHistogramAnomaly``   -- UNICORN-style: graph-level WL colour histograms, anomaly = distance to
                              nearest benign histogram (unsupervised). ``temporal=True`` uses TCR.
* ``DegreeZScore``         -- per-host statistical outlier detection on volume / fan-out features.
* ``RuleBaseline``         -- Sigma-style threshold rules for the same five behaviours, no context.
* ``SupervisedWLLogReg``   -- host-level WL colours + statistics, logistic regression trained WITH attack
                              labels (GNN-node-classifier stand-in; RefineMatch uses no labels).

Re-implementations of published systems (UNICORN, Euler, KAIROS) on real datasets are left to the
real-data harness; these baselines isolate the ideas those systems are built on.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Dict, List, Optional

import numpy as np

from src.core.models import EventRecord
from src.matching.matcher import _cv
from src.refinement.kernel import color_histogram, cosine
from src.refinement.temporal import static_color_refinement, temporal_color_refinement


class WLHistogramAnomaly:
    def __init__(self, temporal: bool = False, depth: int = 2, multiplicity: str = "log"):
        self.temporal, self.depth, self.mode = temporal, depth, multiplicity
        self.name = "TCR-histogram anomaly" if temporal else "WL-histogram anomaly (UNICORN-style)"
        self.bank: List[Counter] = []

    def _hist(self, events, roles):
        fn = temporal_color_refinement if self.temporal else static_color_refinement
        _, lv = fn(events, roles, depth=self.depth, multiplicity=self.mode, return_levels=True)
        return color_histogram(lv)

    def fit(self, windows: List[List[EventRecord]], roles: Dict[str, str]):
        self.roles = roles
        self.bank = [self._hist(w, roles) for w in windows]
        return self

    def score(self, events: List[EventRecord]) -> float:
        h = self._hist(events, self.roles)
        return 1.0 - max((cosine(h, b) for b in self.bank), default=0.0)


def _host_features(events: List[EventRecord]) -> Dict[str, np.ndarray]:
    types = ["auth_remote", "kerberos_tgs", "ldap", "conn", "smb_file", "http", "http_upload"]
    cnt = defaultdict(Counter)
    dst = defaultdict(lambda: defaultdict(set))
    byt = Counter()
    for e in events:
        cnt[e.source][e.event_type] += 1
        dst[e.source][e.event_type].add(e.destination)
        byt[e.source] += e.bytes or 0
    out = {}
    for h in cnt:
        f = [math.log1p(cnt[h][t]) for t in types] + [math.log1p(len(dst[h][t])) for t in types] + [math.log1p(byt[h])]
        out[h] = np.array(f)
    return out


class DegreeZScore:
    name = "Per-host z-score"

    def fit(self, windows, roles):
        self.roles = roles
        by_role = defaultdict(list)
        for w in windows:
            for h, f in _host_features(w).items():
                by_role[roles.get(h, "workstation")].append(f)
        self.mu = {r: np.mean(v, axis=0) for r, v in by_role.items()}
        self.sd = {r: np.std(v, axis=0) + 0.25 for r, v in by_role.items()}
        return self

    def score(self, events):
        best = 0.0
        for h, f in _host_features(events).items():
            r = self.roles.get(h, "workstation")
            if r not in self.mu:
                continue
            z = float(np.max((f - self.mu[r]) / self.sd[r]))
            best = max(best, z)
        return 1 - math.exp(-max(0.0, best) / 6.0)


class RuleBaseline:
    """Context-free threshold rules (what a SIEM correlation search would do)."""
    name = "Threshold rules (Sigma-style)"

    def fit(self, windows, roles):
        self.roles = roles
        return self

    def score(self, events):
        roles = self.roles
        auth_out = defaultdict(set)
        auth_in = defaultdict(set)
        tgs = Counter()
        conn = defaultdict(set)
        http = defaultdict(list)
        fired = 0
        for e in events:
            if e.event_type == "auth_remote":
                auth_out[e.source].add(e.destination)
                auth_in[e.destination].add(e.source)
            elif e.event_type == "kerberos_tgs":
                tgs[e.source] += 1
            elif e.event_type == "conn":
                conn[e.source].add(e.destination)
            elif e.event_type == "http_upload" and (e.bytes or 0) >= 100_000_000 and roles.get(e.destination) in ("external", "saas"):
                fired += 1
            elif e.event_type == "http" and roles.get(e.destination) in ("external", "saas"):
                http[(e.source, e.destination)].append(e.ts)
        # remote-logon chain: a host that received a remote logon then made one
        fired += sum(1 for h in auth_out if auth_in.get(h))
        fired += sum(1 for h, c in tgs.items() if c >= 10)
        fired += sum(1 for h, d in conn.items() if len(d) >= 15)
        fired += sum(1 for k, ts in http.items() if len(ts) >= 8 and _cv(sorted(ts)) <= 0.1)
        return 1.0 if fired else 0.0


class SupervisedWLLogReg:
    """Supervised *host-level* classifier: 1-WL colours (levels 1-2, hashed one-hot) + volume / fan-out
    statistics -> class-weighted logistic regression; window score = max host probability.

    1-WL colours bound what a message-passing GNN can distinguish, so this is a lightweight stand-in
    for a supervised GNN node classifier (Euler / E-GraphSAGE family). Unlike RefineMatch it is
    trained WITH attack labels (attacker hosts)."""
    name = "Host WL features + logistic regression (supervised)"

    def __init__(self, dim: int = 256, epochs: int = 1500, lr: float = 0.1, l2: float = 1e-2, temporal: bool = False):
        self.dim, self.epochs, self.lr, self.l2, self.temporal = dim, epochs, lr, l2, temporal

    def _hosts(self, events):
        fn = temporal_color_refinement if self.temporal else static_color_refinement
        _, lv = fn(events, self.roles, depth=2, multiplicity="log", return_levels=True)
        out = {}
        for h, f in _host_features(events).items():
            v = np.zeros(self.dim)
            for k in (1, 2):
                v[lv[k][h] % self.dim] += 1
            out[h] = np.concatenate([f, v])
        return out

    def fit_supervised(self, labeled_windows, roles):
        self.roles = roles
        X, y = [], []
        for w in labeled_windows:
            for h, x in self._hosts(w.events).items():
                X.append(x)
                y.append(float(w.is_attack and h in w.attack_nodes))
        X, y = np.stack(X), np.array(y)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-6
        Z = (X - self.mu) / self.sd
        pw = (1 - y.mean()) / max(y.mean(), 1e-6)
        self.w, self.b = np.zeros(Z.shape[1]), 0.0
        for _ in range(self.epochs):
            p = 1 / (1 + np.exp(-(Z @ self.w + self.b)))
            g = (p - y) * np.where(y == 1, pw, 1.0)
            self.w -= self.lr * (Z.T @ g / len(y) + self.l2 * self.w)
            self.b -= self.lr * g.mean()
        return self

    def score(self, events):
        hx = self._hosts(events)
        if not hx:
            return 0.0
        M = (np.stack(list(hx.values())) - self.mu) / self.sd
        return float((1 / (1 + np.exp(-(M @ self.w + self.b)))).max())
