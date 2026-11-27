r"""Temporal (causal) colour refinement -- TCR.

Classic 1-WL colour refinement ignores time, so it cannot tell a causal chain
``A->B (t=1), B->C (t=2)`` (an attacker hopping) from the non-causal ``B->C (t=1), A->B (t=2)``.

Definition
----------
Events are tuples ``e = (u, w, tau, t)`` with a total order (t, seq). Every node carries, at every
level k, a colour that is a *step function of time*:

    c^0_v(t)  = H(role(v))                                      (constant)
    S^k_v(t)  = {{ (dir_e, tau_e, c^{k-1}_{other(e)}(t_e^-)) : e incident to v, (t_e,seq_e) <= t }}
    c^k_v(t)  = H(c^{k-1}_v(t), S^k_v(t))

where ``c(t_e^-)`` is the colour of the other endpoint *strictly before* the event. So the message
carried by an event only contains history that could have causally influenced it: c^k_v(+inf)
summarises all *time-respecting* walks of length <= k ending at v.

Properties (tested in tests/test_refinement.py)
---------------------------------------------
P1  TCR separates causal from non-causal chains that static WL conflates. The two are
    incomparable in general (static WL also "sees" future context that TCR deliberately
    ignores); the product colouring (TCR, static) refines both.
P2  Append-locality: when events arrive in time order, a new event changes the colour functions of
    its two endpoints only (all other nodes' colours depend on the past strictly before their own
    events, which the new event cannot alter). Hence an event costs O(K) hash updates, independent
    of graph size -- versus O(K * |k-hop neighbourhood|) for incremental static WL.
P3  Batch (level-by-level) and incremental (event-by-event) computation give identical colours.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from src.core.config import DEFAULT_MULTIPLICITY, DEFAULT_TCR_DEPTH
from src.core.models import EventRecord, RefinementResult, TemporalGraph
from src.refinement.hashing import MASK, color_str, h64, item_contribution, mult_bucket


def _initial_color(role: str) -> int:
    return h64("role", role)


class _Timeline:
    __slots__ = ("keys", "colors")

    def __init__(self):
        self.keys: List[Tuple[float, int]] = []
        self.colors: List[int] = []


def _result_from_levels(levels: List[Dict[str, int]], depth: int) -> RefinementResult:
    final = {v: color_str(c) for v, c in levels[-1].items()}
    classes: Dict[str, List[str]] = defaultdict(list)
    for v, c in final.items():
        classes[c].append(v)
    n_prev = len(set(levels[-2].values())) if len(levels) > 1 else 0
    stable = n_prev == len(classes)
    history = [{v: color_str(c) for v, c in lv.items()} for lv in levels]
    return RefinementResult(node_colors=final, color_classes=dict(classes), iterations=depth,
                            stable=stable, history=history)


class TemporalColorRefiner:
    """Incremental TCR. Feed events in (t, seq) order with :meth:`add_event`."""

    def __init__(self, roles: Dict[str, str], depth: int = DEFAULT_TCR_DEPTH, multiplicity: str = DEFAULT_MULTIPLICITY):
        self.roles = roles
        self.K = depth
        self.mode = multiplicity
        self.seq = 0
        self.last_key = (float("-inf"), -1)
        # level k (1..K) state
        self.counts = [defaultdict(Counter) for _ in range(self.K + 1)]
        self.S = [defaultdict(int) for _ in range(self.K + 1)]
        self.tl = [defaultdict(_Timeline) for _ in range(self.K + 1)]
        self.base_cache: Dict[Tuple[int, str], int] = {}
        self.hash_ops = 0
        self.nodes = set()

    # colour of v at level k before any event (S = empty at all levels)
    def base(self, k: int, v: str) -> int:
        key = (k, v)
        if key not in self.base_cache:
            self.base_cache[key] = _initial_color(self.roles.get(v, "workstation")) if k == 0 else h64(self.base(k - 1, v), 0)
        return self.base_cache[key]

    def color_before(self, k: int, v: str, t: float) -> int:
        if k == 0:
            return self.base(0, v)
        tl = self.tl[k].get(v)
        if tl is None:
            return self.base(k, v)
        i = bisect_left(tl.keys, (t, -1)) - 1
        return tl.colors[i] if i >= 0 else self.base(k, v)

    def color_at(self, k: int, v: str, key: Tuple[float, int]) -> int:
        if k == 0:
            return self.base(0, v)
        tl = self.tl[k].get(v)
        if tl is None:
            return self.base(k, v)
        i = bisect_right(tl.keys, key) - 1
        return tl.colors[i] if i >= 0 else self.base(k, v)

    def _bump(self, k: int, v: str, item: int):
        cnt = self.counts[k][v]
        old = cnt[item]
        cnt[item] = old + 1
        ob, nb = mult_bucket(old, self.mode), mult_bucket(old + 1, self.mode)
        if ob != nb:
            self.S[k][v] = (self.S[k][v] - item_contribution(item, ob) + item_contribution(item, nb)) & MASK

    def add_event(self, e: EventRecord):
        t = e.ts
        key = (t, self.seq)
        if key < self.last_key:
            raise ValueError("events must be added in time order")
        self.last_key = key
        self.seq += 1
        u, w, tau = e.source, e.destination, e.event_type
        self.nodes.update((u, w))
        for k in range(1, self.K + 1):
            item_u = h64("out", tau, self.color_before(k - 1, w, t))
            item_w = h64("in", tau, self.color_before(k - 1, u, t))
            for v, item in ((u, item_u), (w, item_w)):
                self._bump(k, v, item)
                c = h64(self.color_at(k - 1, v, key), self.S[k][v])
                tl = self.tl[k][v]
                tl.keys.append(key)
                tl.colors.append(c)
                self.hash_ops += 4

    def final_levels(self) -> List[Dict[str, int]]:
        levels = []
        for k in range(self.K + 1):
            lv = {}
            for v in self.nodes:
                tl = self.tl[k].get(v) if k > 0 else None
                lv[v] = tl.colors[-1] if tl and tl.colors else self.base(k, v)
            levels.append(lv)
        return levels

    def result(self) -> RefinementResult:
        return _result_from_levels(self.final_levels(), self.K)


def _sorted_events(events: Iterable[EventRecord]) -> List[EventRecord]:
    return sorted(events, key=lambda e: e.ts)  # stable: preserves input order on ties


def temporal_color_refinement(tg_or_events, roles: Optional[Dict[str, str]] = None,
                              depth: int = DEFAULT_TCR_DEPTH, multiplicity: str = DEFAULT_MULTIPLICITY,
                              return_levels: bool = False):
    """Batch TCR, computed level by level (independent implementation from the incremental one)."""
    if isinstance(tg_or_events, TemporalGraph):
        events = tg_or_events.events
        roles = roles or {n: d.get("role", "workstation") for n, d in tg_or_events.graph.nodes(data=True)}
    else:
        events = list(tg_or_events)
        roles = roles or {}
    events = _sorted_events(events)
    nodes = sorted({x for e in events for x in (e.source, e.destination)})
    keys = [(e.ts, i) for i, e in enumerate(events)]
    inc = defaultdict(list)  # node -> list of event indices
    for i, e in enumerate(events):
        inc[e.source].append(i)
        if e.destination != e.source:
            inc[e.destination].append(i)

    # level 0
    base = {v: _initial_color(roles.get(v, "workstation")) for v in nodes}
    prev_keys: Dict[str, List[Tuple[float, int]]] = {v: [] for v in nodes}
    prev_cols: Dict[str, List[int]] = {v: [] for v in nodes}
    prev_base = dict(base)
    levels = [dict(base)]

    def q_before(v, t, pk, pc, pb):
        i = bisect_left(pk[v], (t, -1)) - 1
        return pc[v][i] if i >= 0 else pb[v]

    def q_at(v, key, pk, pc, pb):
        i = bisect_right(pk[v], key) - 1
        return pc[v][i] if i >= 0 else pb[v]

    for k in range(1, depth + 1):
        cur_base = {v: h64(prev_base[v], 0) for v in nodes}
        cur_keys = {v: [] for v in nodes}
        cur_cols = {v: [] for v in nodes}
        counts = defaultdict(Counter)
        S = defaultdict(int)
        for i, e in enumerate(events):
            t, key = e.ts, keys[i]
            u, w, tau = e.source, e.destination, e.event_type
            item_u = h64("out", tau, q_before(w, t, prev_keys, prev_cols, prev_base))
            item_w = h64("in", tau, q_before(u, t, prev_keys, prev_cols, prev_base))
            for v, item in ((u, item_u), (w, item_w)):
                old = counts[v][item]
                counts[v][item] = old + 1
                ob, nb = mult_bucket(old, multiplicity), mult_bucket(old + 1, multiplicity)
                if ob != nb:
                    S[v] = (S[v] - item_contribution(item, ob) + item_contribution(item, nb)) & MASK
                cur_keys[v].append(key)
                cur_cols[v].append(h64(q_at(v, key, prev_keys, prev_cols, prev_base), S[v]))
        levels.append({v: (cur_cols[v][-1] if cur_cols[v] else cur_base[v]) for v in nodes})
        prev_keys, prev_cols, prev_base = cur_keys, cur_cols, cur_base

    res = _result_from_levels(levels, depth)
    return (res, levels) if return_levels else res


def static_color_refinement(tg_or_events, roles: Optional[Dict[str, str]] = None, depth: int = DEFAULT_TCR_DEPTH,
                            multiplicity: str = DEFAULT_MULTIPLICITY, return_levels: bool = False):
    """Classic directed, edge-labelled 1-WL on the time-aggregated multigraph (ablation baseline)."""
    if isinstance(tg_or_events, TemporalGraph):
        events = tg_or_events.events
        roles = roles or {n: d.get("role", "workstation") for n, d in tg_or_events.graph.nodes(data=True)}
    else:
        events = list(tg_or_events)
        roles = roles or {}
    nodes = sorted({x for e in events for x in (e.source, e.destination)})
    adj = defaultdict(Counter)  # v -> Counter[(dir, type, other)]
    for e in events:
        adj[e.source][("out", e.event_type, e.destination)] += 1
        adj[e.destination][("in", e.event_type, e.source)] += 1
    col = {v: _initial_color(roles.get(v, "workstation")) for v in nodes}
    levels = [dict(col)]
    for _ in range(depth):
        new = {}
        for v in nodes:
            items = Counter()
            for (d, tau, o), m in adj[v].items():
                items[h64(d, tau, col[o])] += m
            S = 0
            for it, m in items.items():
                S = (S + item_contribution(it, mult_bucket(m, multiplicity))) & MASK
            new[v] = h64(col[v], S)
        col = new
        levels.append(dict(col))
    res = _result_from_levels(levels, depth)
    return (res, levels) if return_levels else res
