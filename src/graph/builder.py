"""Temporal graph construction, role inference and windowing."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Tuple

import networkx as nx

from src.core.config import DEFAULT_TEMPORAL_WINDOW_SECONDS, EXTERNAL_ROLES
from src.core.models import EventRecord, TemporalGraph

SERVICE_ROLE = {"kerberos_tgt": "dc", "kerberos_tgs": "dc", "ldap": "dc", "dns": "dns", "smb_file": "fileserver"}


def infer_roles(events: List[EventRecord], known: Optional[Dict[str, str]] = None,
                internal_prefixes: Tuple[str, ...] = ()) -> Dict[str, str]:
    """Assign a role to every node.

    ``known`` (an asset inventory / CMDB export) always wins. Otherwise roles are inferred from the
    services a node *answers* (destination of kerberos -> dc, dns -> dns, smb -> fileserver), from
    being the target of many distinct clients (server), or default to workstation. Nodes that never
    initiate and are not internal-looking are external. Inference only depends on in-bound
    service usage, which an attacker cannot cheaply forge (see robustness.certify)."""
    known = known or {}
    served = defaultdict(Counter)
    initiates = Counter()
    in_clients = defaultdict(set)
    for e in events:
        served[e.destination][e.event_type] += 1
        initiates[e.source] += 1
        in_clients[e.destination].add(e.source)
    nodes = set(served) | set(initiates)
    roles = {}
    for n in nodes:
        if n in known:
            roles[n] = known[n]
            continue
        svc = served.get(n, Counter())
        best = None
        for etype, role in SERVICE_ROLE.items():
            if svc.get(etype, 0) >= 5:
                best = role if best is None or svc[etype] > svc.get(best, 0) else best
        if best:
            roles[n] = best
        elif initiates[n] == 0 and internal_prefixes and not n.startswith(internal_prefixes):
            roles[n] = "external"
        elif len(in_clients.get(n, ())) >= 10 and initiates[n] < len(in_clients[n]):
            roles[n] = "server"
        else:
            roles[n] = "workstation"
    return roles


def build_temporal_graph(events: List[EventRecord], roles: Optional[Dict[str, str]] = None,
                         start: Optional[float] = None, end: Optional[float] = None) -> TemporalGraph:
    evs = [e for e in events if (start is None or e.ts >= start) and (end is None or e.ts < end)]
    evs.sort(key=lambda e: e.ts)
    roles = roles if roles is not None else infer_roles(evs)
    g = nx.DiGraph()
    for e in evs:
        for n in (e.source, e.destination):
            if n not in g:
                r = roles.get(n, "workstation")
                g.add_node(n, role=r, internal=r not in EXTERNAL_ROLES)
        if g.has_edge(e.source, e.destination):
            d = g[e.source][e.destination]
            d["weight"] += 1
            d["last_seen"] = e.timestamp
            d["types"][e.event_type] += 1
            d["times"].append(e.ts)
            d["bytes_total"] += e.bytes or 0
        else:
            g.add_edge(e.source, e.destination, weight=1, first_seen=e.timestamp, last_seen=e.timestamp,
                       types=Counter({e.event_type: 1}), times=[e.ts], bytes_total=e.bytes or 0,
                       protocol=e.protocol)
    st = datetime.fromtimestamp(start, tz=timezone.utc) if start is not None else (evs[0].timestamp if evs else None)
    en = datetime.fromtimestamp(end, tz=timezone.utc) if end is not None else (evs[-1].timestamp if evs else None)
    return TemporalGraph(graph=g, events=evs, start_time=st, end_time=en)


def windows(events: List[EventRecord], size: float = DEFAULT_TEMPORAL_WINDOW_SECONDS,
            step: Optional[float] = None, start: Optional[float] = None) -> Iterator[Tuple[float, float, List[EventRecord]]]:
    """Sliding (step < size) or tumbling (step == size, default) windows over a time-sorted stream."""
    if not events:
        return
    step = step or size
    times = [e.ts for e in events]
    t = start if start is not None else times[0]
    while t <= times[-1]:
        lo, hi = bisect_left(times, t), bisect_left(times, t + size)
        yield t, t + size, events[lo:hi]
        t += step


class GraphIndex:
    """Typed, time-sorted adjacency used by the pattern matcher.

    out[v][etype][w] -> sorted list of (ts, bytes); inc[w][etype][v] likewise."""

    def __init__(self, tg: TemporalGraph):
        self.roles = {n: d.get("role", "workstation") for n, d in tg.graph.nodes(data=True)}
        self.out: Dict[str, Dict[str, Dict[str, List[Tuple[float, int]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self.inc: Dict[str, Dict[str, Dict[str, List[Tuple[float, int]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for e in tg.events:
            self.out[e.source][e.event_type][e.destination].append((e.ts, e.bytes or 0))
            self.inc[e.destination][e.event_type][e.source].append((e.ts, e.bytes or 0))
        self.nodes = list(tg.graph.nodes())

    def out_distinct(self, v: str, etype: str) -> int:
        return len(self.out.get(v, {}).get(etype, {}))

    def in_distinct(self, v: str, etype: str) -> int:
        return len(self.inc.get(v, {}).get(etype, {}))

    def events_between(self, v: str, w: str, etypes) -> List[Tuple[float, int, str]]:
        res = []
        tv = self.out.get(v, {})
        for et in etypes:
            for ts, b in tv.get(et, {}).get(w, []):
                res.append((ts, b, et))
        res.sort()
        return res

    def out_neighbors(self, v: str, etypes) -> set:
        tv = self.out.get(v, {})
        s = set()
        for et in etypes:
            s.update(tv.get(et, {}).keys())
        return s

    def in_neighbors(self, w: str, etypes) -> set:
        tw = self.inc.get(w, {})
        s = set()
        for et in etypes:
            s.update(tw.get(et, {}).keys())
        return s
