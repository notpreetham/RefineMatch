"""Reference patterns (attack and benign templates) as small temporal graphs with constraints."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Set

from src.core.config import EVENT_TYPES, EXTERNAL_ROLES, ROLES


@dataclass
class NodeSpec:
    roles: Optional[Set[str]] = None          # allowed roles (None = any)
    not_roles: Set[str] = field(default_factory=set)
    internal: Optional[bool] = None           # True internal only, False external only
    min_out_distinct: Dict[str, int] = field(default_factory=dict)  # event type -> distinct targets

    def accepts(self, role: str, out_distinct) -> bool:
        if self.roles is not None and role not in self.roles:
            return False
        if role in self.not_roles:
            return False
        if self.internal is not None and (role not in EXTERNAL_ROLES) != self.internal:
            return False
        for et, n in self.min_out_distinct.items():
            if out_distinct(et) < n:
                return False
        return True


@dataclass
class EdgeSpec:
    src: str
    dst: str
    types: Set[str]
    order: int = 0                 # temporal order: edges with smaller order must happen first
    min_count: int = 1
    min_bytes: int = 0             # at least one qualifying event must carry >= min_bytes
    periodic: bool = False         # >= min_count events form a periodic subsequence ...
    max_cv: float = 0.15           # ... with every gap within +-max_cv of the period
    weight: float = 1.0            # importance (how suspicious this step is on its own)
    essential: bool = False        # the attack objective requires >= 1 such event (cannot be fully avoided)

    def __post_init__(self):  # canonical numeric types (stable serialisation / signatures)
        self.types = set(self.types)
        self.order, self.min_count, self.min_bytes = int(self.order), int(self.min_count), int(self.min_bytes)
        self.max_cv, self.weight = float(self.max_cv), float(self.weight)
        self.periodic, self.essential = bool(self.periodic), bool(self.essential)


@dataclass
class Pattern:
    name: str
    kind: str                      # "attack" | "benign"
    nodes: Dict[str, NodeSpec]
    edges: List[EdgeSpec]
    tactic: str = ""
    techniques: List[str] = field(default_factory=list)
    max_span: float = 3600.0
    description: str = ""
    benign_counterparts: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.max_span = float(self.max_span)

    @property
    def total_weight(self) -> float:
        return sum(e.weight for e in self.edges) or 1.0

    def validate(self) -> List[str]:
        """Return a list of problems (empty if the pattern is well formed)."""
        errs = []
        if self.kind not in ("attack", "benign"):
            errs.append(f"kind must be attack|benign, got {self.kind}")
        if not self.edges:
            errs.append("pattern has no edges")
        for n, spec in self.nodes.items():
            for r in (spec.roles or set()) | spec.not_roles:
                if r not in ROLES:
                    errs.append(f"node {n}: unknown role {r}")
            for et in spec.min_out_distinct:
                if et not in EVENT_TYPES:
                    errs.append(f"node {n}: unknown event type {et}")
        for e in self.edges:
            if e.src not in self.nodes or e.dst not in self.nodes:
                errs.append(f"edge {e.src}->{e.dst} references unknown node")
            if e.src == e.dst:
                errs.append(f"self loop on {e.src}")
            for et in e.types:
                if et not in EVENT_TYPES:
                    errs.append(f"edge {e.src}->{e.dst}: unknown event type {et}")
        # connectivity
        if self.nodes and self.edges:
            adj = {n: set() for n in self.nodes}
            for e in self.edges:
                if e.src in adj and e.dst in adj:
                    adj[e.src].add(e.dst)
                    adj[e.dst].add(e.src)
            start = next(iter(self.nodes))
            seen, stack = {start}, [start]
            while stack:
                for m in adj[stack.pop()]:
                    if m not in seen:
                        seen.add(m)
                        stack.append(m)
            if seen != set(self.nodes):
                errs.append("pattern is not connected")
        return errs

    # ---------------------------------------------------------------- (de)serialisation
    def to_dict(self) -> dict:
        d = asdict(self)
        for n in d["nodes"].values():
            n["roles"] = sorted(n["roles"]) if n["roles"] is not None else None
            n["not_roles"] = sorted(n["not_roles"])
        for e in d["edges"]:
            e["types"] = sorted(e["types"])
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_dict(d: dict) -> "Pattern":
        nodes = {}
        for n, s in d["nodes"].items():
            nodes[n] = NodeSpec(roles=set(s["roles"]) if s.get("roles") is not None else None,
                                not_roles=set(s.get("not_roles", [])), internal=s.get("internal"),
                                min_out_distinct={k: int(v) for k, v in (s.get("min_out_distinct") or {}).items()})
        edges = [EdgeSpec(src=e["src"], dst=e["dst"], types=set(e["types"]), order=int(e.get("order", 0)),
                          min_count=int(e.get("min_count", 1)), min_bytes=int(e.get("min_bytes", 0)),
                          periodic=bool(e.get("periodic", False)), max_cv=float(e.get("max_cv", 0.15)),
                          weight=float(e.get("weight", 1.0)), essential=bool(e.get("essential", False)))
                 for e in d["edges"]]
        return Pattern(name=d["name"], kind=d["kind"], nodes=nodes, edges=edges, tactic=d.get("tactic", ""),
                       techniques=list(d.get("techniques", [])), max_span=float(d.get("max_span", 3600)),
                       description=d.get("description", ""),
                       benign_counterparts=list(d.get("benign_counterparts", [])))

    @staticmethod
    def from_json(s: str) -> "Pattern":
        return Pattern.from_dict(json.loads(s))
