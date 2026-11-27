"""Synthetic enterprise traffic with injected, ATT&CK-mapped attacks and *hard negatives*.

Hard negatives are benign activities that are structurally similar to attacks (admin jump-host
chains look like lateral movement, monitoring sweeps look like scans, cloud sync looks like
exfiltration, service-ticket renewal looks like Kerberoasting, update polling looks like C2
beaconing). They are what makes alert fatigue real and what the contrastive scorer targets.

Everything is seeded and reproducible. Ground truth is written to ``EventRecord.label`` and to
:class:`LabeledWindow`; detectors never read either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import numpy as np

from src.core.models import EventRecord, make_event as _ev

ATTACK_KINDS = ["lateral_movement", "kerberoasting", "network_scan", "exfiltration", "c2_beaconing"]
HARD_NEGATIVE_KINDS = ["admin_jump", "monitoring_sweep", "cloud_sync", "ticket_renewal", "update_polling",
                       "noncausal_logons"]
EPOCH = 1_700_000_000.0


@dataclass
class LabeledWindow:
    events: List[EventRecord]
    start: float
    end: float
    is_attack: bool
    kind: str                           # attack kind, hard-negative kind, or "benign"
    attack_nodes: Set[str] = field(default_factory=set)


class SyntheticEnterprise:
    def __init__(self, n_workstations: int = 40, n_servers: int = 6, n_external: int = 30, n_saas: int = 6,
                 seed: int = 0):
        self.rng = np.random.default_rng(seed)
        self.workstations = [f"WS{i:03d}" for i in range(n_workstations)]
        self.servers = [f"SRV{i:02d}" for i in range(n_servers)]
        self.externals = [f"EXT{i:03d}" for i in range(n_external)]
        self.saas = [f"SAAS{i:02d}" for i in range(n_saas)]
        self.roles: Dict[str, str] = {}
        for w in self.workstations:
            self.roles[w] = "workstation"
        for s in self.servers:
            self.roles[s] = "server"
        for e in self.externals:
            self.roles[e] = "external"
        for s in self.saas:
            self.roles[s] = "saas"
        self.roles.update({"DC01": "dc", "DNS01": "dns", "FS01": "fileserver", "JUMP01": "jumphost",
                           "MON01": "monitoring", "BAK01": "backup", "ADM01": "admin_ws", "ADM02": "admin_ws",
                           "HD01": "helpdesk"})
        self.internal = [n for n, r in self.roles.items() if r not in ("external", "saas")]
        self._fresh_ext = 0

    def new_external(self) -> str:
        self._fresh_ext += 1
        name = f"EVIL{self._fresh_ext:03d}"
        self.roles[name] = "external"
        return name

    # ------------------------------------------------------------------ benign background
    def benign_events(self, s0: float, length: float, rng: np.random.Generator,
                      hard: Optional[Set[str]] = None) -> List[EventRecord]:
        hard = hard or set()
        E: List[EventRecord] = []
        u = lambda: s0 + rng.uniform(0, length)
        for w in self.workstations:
            E.append(_ev(u(), w, "DC01", "kerberos_tgt", port=88))
            for _ in range(rng.integers(1, 5)):
                E.append(_ev(u(), w, "DC01", "kerberos_tgs", port=88))
            for _ in range(rng.integers(4, 12)):
                E.append(_ev(u(), w, "DNS01", "dns", 120, port=53))
            for _ in range(rng.integers(3, 12)):
                dst = self.externals[rng.integers(len(self.externals))] if rng.random() < 0.7 else \
                    self.saas[rng.integers(len(self.saas))]
                E.append(_ev(u(), w, dst, "http", int(rng.integers(2_000, 400_000)), port=443))
            for _ in range(rng.integers(0, 4)):
                E.append(_ev(u(), w, "FS01", "smb_file", int(rng.integers(10_000, 5_000_000)), port=445))
            for _ in range(rng.integers(0, 4)):
                E.append(_ev(u(), w, self.servers[rng.integers(len(self.servers))], "conn", 30_000, port=8443))
            if rng.random() < 0.08:  # small legit uploads
                E.append(_ev(u(), w, self.saas[rng.integers(len(self.saas))], "http_upload",
                             int(rng.integers(1_000_000, 8_000_000)), port=443))
        for srv in self.servers:
            E.append(_ev(u(), srv, "DC01", "kerberos_tgt", port=88))
            for _ in range(rng.integers(1, 4)):
                E.append(_ev(u(), srv, "DC01", "kerberos_tgs", port=88))
            for _ in range(rng.integers(1, 4)):
                E.append(_ev(u(), srv, "DNS01", "dns", 120, port=53))
        for adm in ("ADM01", "ADM02"):
            E.append(_ev(u(), adm, "DC01", "kerberos_tgt", port=88))
            E.append(_ev(u(), adm, "DNS01", "dns", 120, port=53))
        # backup job: large SMB reads from servers
        t = s0 + rng.uniform(0, length * 0.5)
        for srv in self.servers:
            t += rng.uniform(10, 60)
            E.append(_ev(t, "BAK01", srv, "smb_file", int(rng.integers(50_000_000, 400_000_000)), port=445))
        # helpdesk remote support: single hop
        if rng.random() < 0.5:
            E.append(_ev(u(), "HD01", self.workstations[rng.integers(len(self.workstations))], "auth_remote", port=3389))

        # occasionally-present benign look-alikes (always present when requested as hard negatives)
        if "admin_jump" in hard or rng.random() < 0.15:
            E += self.admin_jump(s0, length, rng)
        if "monitoring_sweep" in hard or rng.random() < 0.15:
            E += self.monitoring_sweep(s0, length, rng)
        if "cloud_sync" in hard or rng.random() < 0.10:
            E += self.cloud_sync(s0, length, rng)
        if "ticket_renewal" in hard or rng.random() < 0.15:
            E += self.ticket_renewal(s0, length, rng)
        if "update_polling" in hard or rng.random() < 0.15:
            E += self.update_polling(s0, length, rng)
        if "noncausal_logons" in hard or rng.random() < 0.15:
            E += self.noncausal_logons(s0, length, rng)
        return E

    def noncausal_logons(self, s0, length, rng):
        """Two unrelated remote logons that form a chain *only if time is ignored*: b logs into a
        server early, and much later a different user on a logs into b (e.g. a developer pairing session)."""
        a, b = (str(x) for x in rng.choice(self.workstations, size=2, replace=False))
        srv = self.servers[rng.integers(len(self.servers))]
        t = s0 + rng.uniform(0, length * 0.3)
        return [_ev(t, b, srv, "auth_remote", port=3389),
                _ev(t + rng.uniform(length * 0.3, length * 0.6), a, b, "auth_remote", port=3389)]

    def admin_jump(self, s0, length, rng):
        adm = ["ADM01", "ADM02"][rng.integers(2)]
        t = s0 + rng.uniform(0, length * 0.4)
        E = [_ev(t, adm, "JUMP01", "auth_remote", port=3389)]
        for srv in rng.choice(self.servers, size=int(rng.integers(1, 4)), replace=False):
            t += rng.uniform(60, 600)
            E.append(_ev(t, "JUMP01", str(srv), "auth_remote", port=5985))
        return E

    def monitoring_sweep(self, s0, length, rng):
        t = s0 + rng.uniform(0, length * 0.5)
        E = []
        for h in self.internal:
            if h == "MON01":
                continue
            t += rng.uniform(0.2, 2.0)
            E.append(_ev(t, "MON01", h, "conn", 200, port=int(rng.choice([22, 135, 161, 445])), duration=0.01))
        return E

    def cloud_sync(self, s0, length, rng):
        w = self.workstations[rng.integers(len(self.workstations))]
        t = s0 + rng.uniform(0, length * 0.5)
        E = []
        for _ in range(int(rng.integers(2, 6))):
            t += rng.uniform(5, 60)
            E.append(_ev(t, w, "FS01", "smb_file", int(rng.integers(20_000_000, 200_000_000)), port=445))
        t += rng.uniform(30, 300)
        E.append(_ev(t, w, self.saas[rng.integers(len(self.saas))], "http_upload",
                     int(rng.integers(30_000_000, 300_000_000)), port=443))
        return E

    def ticket_renewal(self, s0, length, rng):
        srv = self.servers[rng.integers(len(self.servers))]
        t = s0 + rng.uniform(0, length * 0.6)
        E = [_ev(t, srv, "DC01", "ldap", 4_000, port=389)]
        for _ in range(int(rng.integers(12, 30))):
            t += rng.uniform(0.5, 6)
            E.append(_ev(t, srv, "DC01", "kerberos_tgs", port=88))
        return E

    def update_polling(self, s0, length, rng):
        w = self.workstations[rng.integers(len(self.workstations))]
        dst = self.saas[0]
        t = s0 + rng.uniform(0, 120)
        E = []
        while t < s0 + length:
            E.append(_ev(t, w, dst, "http", 1_500, port=443))
            t += 300 + rng.normal(0, 3)
        return E

    # ------------------------------------------------------------------ attacks
    def attack_events(self, kind: str, s0: float, length: float, rng: np.random.Generator,
                      attacker: Optional[str] = None, stealth: float = 0.0):
        """Return (events, attacker_nodes). ``stealth`` in [0,1] weakens the attack signal
        (fewer hops / targets / tickets / beacons, more jitter)."""
        lab = f"attack:{kind}"
        a = attacker or self.workstations[rng.integers(len(self.workstations))]
        others = [w for w in self.workstations if w != a]
        t = s0 + rng.uniform(0, length * 0.3)
        E: List[EventRecord] = []
        nodes = {a}
        if kind == "lateral_movement":
            hops = list(rng.choice(others, size=2, replace=False)) + [self.servers[rng.integers(len(self.servers))]]
            if stealth > 0.5:
                hops = hops[:2]
            cur = a
            for h in hops:
                h = str(h)
                t += rng.uniform(60, 600)
                E.append(_ev(t, cur, "DC01", "kerberos_tgs", label=lab, port=88))
                t += rng.uniform(1, 10)
                E.append(_ev(t, cur, h, "auth_remote", label=lab, port=445))
                nodes.add(h)
                cur = h
        elif kind == "kerberoasting":
            E.append(_ev(t, a, "DC01", "ldap", 60_000, label=lab, port=389))
            n = int(rng.integers(12, 30) * (1 - 0.6 * stealth))
            for _ in range(max(n, 3)):
                t += rng.uniform(0.2, 4)
                E.append(_ev(t, a, "DC01", "kerberos_tgs", label=lab, port=88))
            nodes.add("DC01")
        elif kind == "network_scan":
            n = int(rng.integers(20, 35) * (1 - 0.7 * stealth))
            for h in rng.choice([x for x in self.internal if x != a], size=max(n, 3), replace=False):
                t += rng.uniform(0.5, 8)
                E.append(_ev(t, a, str(h), "conn", 120, label=lab, port=int(rng.choice([22, 135, 445, 3389])),
                             duration=0.01))
        elif kind == "exfiltration":
            for _ in range(int(rng.integers(3, 8))):
                t += rng.uniform(5, 60)
                E.append(_ev(t, a, "FS01", "smb_file", int(rng.integers(100_000_000, 900_000_000)), label=lab, port=445))
            dst = self.new_external() if stealth < 0.5 else self.saas[rng.integers(len(self.saas))]
            t += rng.uniform(60, 600)
            E.append(_ev(t, a, dst, "http_upload", int(rng.integers(300_000_000, 2_000_000_000)), label=lab, port=443))
            nodes |= {"FS01", dst}
        elif kind == "c2_beaconing":
            dst = self.new_external()
            period = float(rng.choice([30, 60, 120]))
            n = int(rng.integers(15, 40) * (1 - 0.6 * stealth))
            jitter = 0.02 + 0.4 * stealth
            for _ in range(max(n, 4)):
                E.append(_ev(t, a, dst, "http", 800, label=lab, port=443))
                t += period * (1 + rng.normal(0, jitter))
            nodes.add(dst)
        else:
            raise ValueError(kind)
        return E, nodes


def generate_benchmark(n_benign: int = 30, n_attack_per_kind: int = 10, n_hard_per_kind: int = 6,
                       seed: int = 7, window: float = 3600.0, stealth: float = 0.0,
                       enterprise: Optional[SyntheticEnterprise] = None) -> List[LabeledWindow]:
    """Independent windows: pure benign, hard negatives (one look-alike each) and attacks."""
    ent = enterprise or SyntheticEnterprise(seed=seed)
    rng = np.random.default_rng(seed + 1)
    out: List[LabeledWindow] = []
    s0 = EPOCH
    plan = [("benign", None)] * n_benign
    plan += [("hard", k) for k in HARD_NEGATIVE_KINDS for _ in range(n_hard_per_kind)]
    plan += [("attack", k) for k in ATTACK_KINDS for _ in range(n_attack_per_kind)]
    for typ, kind in plan:
        if typ == "hard":
            ev = ent.benign_events(s0, window, rng, hard={kind})
            out.append(LabeledWindow(sorted(ev, key=lambda e: e.ts), s0, s0 + window, False, kind))
        elif typ == "attack":
            ev = ent.benign_events(s0, window, rng)
            aev, nodes = ent.attack_events(kind, s0, window, rng, stealth=stealth)
            ev = [e for e in ev + aev if e.ts < s0 + window]
            out.append(LabeledWindow(sorted(ev, key=lambda e: e.ts), s0, s0 + window, True, kind, nodes))
        else:
            ev = ent.benign_events(s0, window, rng)
            out.append(LabeledWindow(sorted(ev, key=lambda e: e.ts), s0, s0 + window, False, "benign"))
        s0 += window
    return out


def generate_campaign(seed: int = 11, window: float = 3600.0, n_benign_before: int = 2,
                      enterprise: Optional[SyntheticEnterprise] = None):
    """A multi-stage intrusion spread across consecutive windows:
    scan -> kerberoasting -> lateral movement -> exfiltration (+ C2 throughout).
    Returns (events, list of (stage, start, end, nodes))."""
    ent = enterprise or SyntheticEnterprise(seed=seed)
    rng = np.random.default_rng(seed)
    patient0 = ent.workstations[3]
    s0 = EPOCH
    events: List[EventRecord] = []
    stages = []
    last_hop = patient0
    for _ in range(n_benign_before):
        events += ent.benign_events(s0, window, rng)
        s0 += window
    for stage in ["network_scan", "kerberoasting", "lateral_movement", "exfiltration"]:
        events += ent.benign_events(s0, window, rng)
        attacker = patient0 if stage != "exfiltration" else last_hop
        aev, nodes = ent.attack_events(stage, s0, window, rng, attacker=attacker)
        if stage == "lateral_movement":
            hops = [e.destination for e in aev if e.event_type == "auth_remote"]
            last_hop = hops[-1] if hops else patient0
        events += [e for e in aev if e.ts < s0 + window]
        stages.append((stage, s0, s0 + window, nodes))
        s0 += window
    events.sort(key=lambda e: e.ts)
    return events, stages, ent
