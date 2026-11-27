"""LLM-assisted template authoring: ATT&CK technique / CTI text -> validated RefineMatch pattern.

Hand-writing templates is the bottleneck of query-graph systems (POIROT needed analysts to draw
them). Here Claude drafts a template under a strict JSON schema whose enums are RefineMatch's role
and event vocabulary, and every draft must pass three automatic gates before it is accepted:

1. **Well-formedness** -- ``Pattern.validate()`` (known roles / types, connected, no self-loops).
2. **Self-consistency** -- a synthetic instance is generated *from the template itself* and
   injected into benign traffic; the matcher must find it (catches unsatisfiable constraints).
3. **Specificity** -- the template must not fire on held-out benign windows (catches templates
   so loose that they describe normal traffic).

Failures are sent back to the model as feedback (up to ``max_rounds``). The LLM is never in the
detection loop: it only proposes, and the combinatorial matcher decides.

Requires ``pip install anthropic`` and credentials (ANTHROPIC_API_KEY or ``ant auth login``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from src.core.config import EVENT_TYPES, ROLES
from src.core.models import EventRecord, make_event
from src.graph.builder import GraphIndex, build_temporal_graph
from src.matching.matcher import PatternMatcher
from src.matching.pattern import EdgeSpec, NodeSpec, Pattern

MODEL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "snake_case identifier"},
        "tactic": {"type": "string"},
        "techniques": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
        "max_span_seconds": {"type": "number"},
        "nodes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string", "enum": ROLES},
                          "description": "allowed roles; empty list = any role"},
                "not_roles": {"type": "array", "items": {"type": "string", "enum": ROLES}},
                "location": {"type": "string", "enum": ["internal", "external", "any"]},
                "min_out_distinct": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"event_type": {"type": "string", "enum": EVENT_TYPES}, "count": {"type": "integer"}},
                    "required": ["event_type", "count"], "additionalProperties": False}},
            },
            "required": ["id", "roles", "not_roles", "location", "min_out_distinct"], "additionalProperties": False}},
        "edges": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "src": {"type": "string"}, "dst": {"type": "string"},
                "event_types": {"type": "array", "items": {"type": "string", "enum": EVENT_TYPES}},
                "order": {"type": "integer", "description": "causal step number, 1 = first"},
                "min_count": {"type": "integer"},
                "min_bytes": {"type": "integer"},
                "periodic": {"type": "boolean"},
                "weight": {"type": "number", "description": "how suspicious this step is alone (0.5-3)"},
                "essential": {"type": "boolean", "description": "the objective cannot be reached without it"},
            },
            "required": ["src", "dst", "event_types", "order", "min_count", "min_bytes", "periodic", "weight", "essential"],
            "additionalProperties": False}},
        "benign_lookalikes": {"type": "array", "items": {"type": "string"},
                              "description": "names of existing benign templates this could be confused with"},
    },
    "required": ["name", "tactic", "techniques", "description", "max_span_seconds", "nodes", "edges", "benign_lookalikes"],
    "additionalProperties": False,
}

SYSTEM = f"""You translate descriptions of adversary behaviour (MITRE ATT&CK techniques, threat reports) into
detection templates for RefineMatch, a temporal graph-matching detector over enterprise network/auth logs.

A template is a small directed graph. Nodes are hosts constrained by role; edges are observed events
between hosts with an event type, a causal order, and optional count / byte / periodicity thresholds.

Vocabulary (use nothing else):
- roles: {", ".join(ROLES)}
- event types: {", ".join(EVENT_TYPES)}  (auth_remote = remote logon via SMB/RDP/WinRM/SSH;
  http_upload = large outbound HTTP(S) transfer; conn = generic TCP connection)

Guidelines:
- Describe the *behaviour*, not a tool: keep role constraints as broad as the technique allows
  (attack templates should have high recall; sanctioned look-alikes are handled separately).
- Use only observable network/auth events; drop host-only steps (process injection etc.).
- 1-4 nodes, 1-4 edges. Give later steps larger `order`.
- Thresholds must be realistic for one hour of traffic. Mark as essential only steps the objective needs.
"""


@dataclass
class GenerationResult:
    pattern: Optional[Pattern]
    accepted: bool
    rounds: int
    feedback: List[List[str]] = field(default_factory=list)
    raw: List[dict] = field(default_factory=list)


def pattern_from_llm_json(d: dict) -> Pattern:
    nodes = {}
    for n in d["nodes"]:
        loc = n.get("location", "any")
        nodes[n["id"]] = NodeSpec(roles=set(n["roles"]) or None, not_roles=set(n.get("not_roles", [])),
                                  internal=None if loc == "any" else (loc == "internal"),
                                  min_out_distinct={m["event_type"]: int(m["count"]) for m in n.get("min_out_distinct", [])})
    edges = [EdgeSpec(e["src"], e["dst"], set(e["event_types"]), order=int(e["order"]),
                      min_count=max(1, int(e["min_count"])), min_bytes=max(0, int(e["min_bytes"])),
                      periodic=bool(e["periodic"]), weight=float(e["weight"]) or 1.0, essential=bool(e["essential"]))
             for e in d["edges"]]
    return Pattern(name=d["name"], kind="attack", nodes=nodes, edges=edges, tactic=d.get("tactic", ""),
                   techniques=list(d.get("techniques", [])), max_span=float(d.get("max_span_seconds", 3600)),
                   description=d.get("description", ""), benign_counterparts=list(d.get("benign_lookalikes", [])))


def synthesize_instance(p: Pattern, roles: Dict[str, str], t0: float) -> List[EventRecord]:
    """Concrete events that satisfy pattern p, using hosts of the right roles from ``roles``."""
    by_role: Dict[str, List[str]] = {}
    for h, r in sorted(roles.items()):
        by_role.setdefault(r, []).append(h)
    used, assign = set(), {}
    for n, spec in p.nodes.items():
        cands = sorted(spec.roles) if spec.roles else [r for r in by_role if r not in spec.not_roles]
        if spec.internal is not None:
            cands = [r for r in cands if (r not in ("external", "saas")) == spec.internal]
        cands = [r for r in cands if r not in spec.not_roles]
        host = next((h for r in cands for h in by_role.get(r, []) if h not in used), None)
        if host is None:
            host = f"SYN_{n}"
            roles[host] = cands[0] if cands else "workstation"
        used.add(host)
        assign[n] = host
    evs, t = [], t0
    span = max(1.0, p.max_span * 0.5 / max(1, len({e.order for e in p.edges})))
    for o in sorted({e.order for e in p.edges}):
        for e in [e for e in p.edges if e.order == o]:
            et = sorted(e.types)[0]
            for k in range(e.min_count + (1 if e.periodic else 0)):
                gap = (span / (e.min_count + 1)) if e.periodic else 1.0
                evs.append(make_event(t + k * gap, assign[e.src], assign[e.dst], et,
                                      max(e.min_bytes, 1000) if e.min_bytes else 1000, label="attack:synthetic"))
            t += span
    for n, spec in p.nodes.items():   # satisfy fan-out constraints
        for et, cnt in spec.min_out_distinct.items():
            targets = [h for h in sorted(roles) if h != assign[n] and roles[h] not in ("external", "saas")][:cnt]
            for i, h in enumerate(targets):
                evs.append(make_event(t0 + i, assign[n], h, et, 100, label="attack:synthetic"))
    return sorted(evs, key=lambda e: e.ts)


def validate_template(p: Pattern, roles: Dict[str, str], benign_windows: List[List[EventRecord]]) -> List[str]:
    problems = p.validate()
    if problems:
        return problems
    base = benign_windows[0] if benign_windows else []
    t0 = base[0].ts + 60 if base else 1_700_000_000.0
    r = dict(roles)
    inst = synthesize_instance(p, r, t0)
    tg = build_temporal_graph(sorted(base + inst, key=lambda e: e.ts), r)
    if PatternMatcher(GraphIndex(tg)).match(p, relax=False).similarity < 1.0:
        problems.append("self-consistency: a synthetic instance built from the template is not matched "
                        "(constraints are contradictory or the causal order/span is infeasible)")
    fires = 0
    for w in benign_windows[1:]:
        if PatternMatcher(GraphIndex(build_temporal_graph(w, roles))).match(p, relax=False).similarity >= 1.0:
            fires += 1
    if benign_windows[1:] and fires / len(benign_windows[1:]) > 0.2:
        problems.append(f"specificity: fires on {fires}/{len(benign_windows) - 1} benign windows; tighten roles, "
                        "thresholds or add a causal step")
    return problems


def generate_template(description: str, roles: Dict[str, str], benign_windows: List[List[EventRecord]],
                      benign_names: Optional[List[str]] = None, max_rounds: int = 3,
                      client=None, model: str = MODEL) -> GenerationResult:
    """Draft -> validate -> feedback loop. ``client`` defaults to ``anthropic.Anthropic()``."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    user = (f"Technique / behaviour to model:\n{description}\n\n"
            f"Existing benign templates you may list as look-alikes: {', '.join(benign_names or [])}")
    messages = [{"role": "user", "content": user}]
    res = GenerationResult(None, False, 0)
    for rnd in range(1, max_rounds + 1):
        resp = client.beta.messages.create(
            model=model, max_tokens=16000, system=SYSTEM, messages=messages,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        res.rounds = rnd
        if resp.stop_reason == "refusal":
            res.feedback.append(["model declined the request"])
            return res
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
            p = pattern_from_llm_json(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as ex:
            problems, p, data = [f"could not parse template: {ex}"], None, {}
        else:
            problems = validate_template(p, roles, benign_windows)
        res.raw.append(data)
        res.feedback.append(problems)
        res.pattern = p
        if p is not None and not problems:
            res.accepted = True
            return res
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": "The template failed validation:\n- " + "\n- ".join(problems) +
                                                    "\nReturn a corrected template."})
    return res
