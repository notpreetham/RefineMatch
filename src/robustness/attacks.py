"""Empirical adversarial perturbations used to stress-test detectors (and to check that the
certified bounds are never violated)."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import numpy as np

from src.core.models import EventRecord, make_event


def _attack_events(events: List[EventRecord]) -> List[int]:
    return [i for i, e in enumerate(events) if e.label and e.label.startswith("attack")]


def delete_attack_events(events: List[EventRecord], k: int, rng: np.random.Generator,
                         protect_essential: bool = True) -> List[EventRecord]:
    """The adversary avoids k of its own events (chosen at random)."""
    idx = _attack_events(events)
    if not idx:
        return list(events)
    k = min(k, len(idx) - (1 if protect_essential else 0))
    drop = set(rng.choice(idx, size=max(0, k), replace=False).tolist()) if k > 0 else set()
    return [e for i, e in enumerate(events) if i not in drop]


def insert_noise(events: List[EventRecord], hosts: List[str], targets: List[str], n: int,
                 rng: np.random.Generator, etypes=("conn", "http", "dns", "smb_file")) -> List[EventRecord]:
    """The adversary pads its traffic with n benign-looking events from compromised hosts."""
    if not events or n <= 0:
        return list(events)
    t0, t1 = events[0].ts, events[-1].ts
    extra = [make_event(rng.uniform(t0, t1), str(rng.choice(hosts)), str(rng.choice(targets)),
                        str(rng.choice(list(etypes))), int(rng.integers(100, 100_000)), label="attack:noise")
             for _ in range(n)]
    return sorted(list(events) + extra, key=lambda e: e.ts)


def benign_mimicry(events: List[EventRecord], attacker: str, roles: Dict[str, str], n: int,
                   rng: np.random.Generator) -> List[EventRecord]:
    """The adversary fabricates events that complete benign look-alike templates around itself
    (uploads to sanctioned SaaS, periodic polling, sessions via the jump host...)."""
    if not events or n <= 0:
        return list(events)
    saas = [h for h, r in roles.items() if r == "saas"] or ["SAAS00"]
    jump = [h for h, r in roles.items() if r == "jumphost"] or ["JUMP01"]
    t0, t1 = events[0].ts, events[-1].ts
    extra = []
    for i in range(n):
        t = rng.uniform(t0, t1)
        kind = i % 3
        if kind == 0:
            extra.append(make_event(t, attacker, str(rng.choice(saas)), "http_upload", 50_000_000, label="attack:mimicry"))
        elif kind == 1:
            extra.append(make_event(t, attacker, str(rng.choice(saas)), "http", 1_500, label="attack:mimicry"))
        else:
            extra.append(make_event(t, attacker, str(rng.choice(jump)), "auth_remote", label="attack:mimicry"))
    return sorted(list(events) + extra, key=lambda e: e.ts)


def timing_jitter(events: List[EventRecord], sigma: float, rng: np.random.Generator) -> List[EventRecord]:
    """Shift each attack event by N(0, sigma) seconds (may reorder causal steps)."""
    out = []
    for e in events:
        if e.label and e.label.startswith("attack"):
            out.append(make_event(e.ts + rng.normal(0, sigma), e.source, e.destination, e.event_type, e.bytes, e.label,
                                  e.destination_port, e.duration))
        else:
            out.append(e)
    return sorted(out, key=lambda e: e.ts)


def beacon_jitter(events: List[EventRecord], n_extra: int, rng: np.random.Generator) -> List[EventRecord]:
    """Insert off-schedule beacons on every attacker->C2 channel to break periodicity."""
    att = [e for e in events if e.label == "attack:c2_beaconing"]
    if not att or n_extra <= 0:
        return list(events)
    s, d = att[0].source, att[0].destination
    t0, t1 = att[0].ts, att[-1].ts
    extra = [make_event(rng.uniform(t0, t1), s, d, "http", 800, label="attack:c2_beaconing") for _ in range(n_extra)]
    return sorted(list(events) + extra, key=lambda e: e.ts)
