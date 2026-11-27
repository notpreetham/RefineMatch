"""Privacy-preserving threat sharing: turn one local detection into a signed, anonymised template.

Instead of sharing raw logs or IOCs (IPs / hashes that attackers rotate in minutes), an
organisation shares the *behavioural structure* of what it saw: roles, event types, causal order,
generalised counts and sizes -- never host names, addresses, users or exact timestamps. Partners
match it with the same IR matcher on their own data.

* ``canonical_hash`` -- TCR colour histogram of the template's prototype instance: identical for
  structurally identical templates regardless of node naming (deduplication across feeds).
* ``sign`` / ``verify`` -- HMAC over the canonical JSON with a community key (integrity, origin).
* ``privacy_report`` -- anonymity-set size of every role in the sharer's own window (how many
  hosts could each template node be); nodes below ``k`` are flagged before export.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from collections import Counter
from typing import Dict, Optional

from src.core.models import make_event
from src.graph.builder import GraphIndex
from src.matching.matcher import PatternMatcher
from src.matching.pattern import EdgeSpec, NodeSpec, Pattern
from src.refinement.temporal import temporal_color_refinement
from src.scoring.contrastive import Detection


def detection_to_template(det: Detection, matcher: PatternMatcher, generalize: float = 0.5) -> Pattern:
    ix, emb, base = matcher.ix, det.embedding, det.pattern
    names = {p: f"n{i}" for i, p in enumerate(sorted(emb.mapping))}
    nodes = {}
    for p, v in emb.mapping.items():
        spec = base.nodes.get(p, NodeSpec())
        mod = {et: max(1, int(math.floor(ix.out_distinct(v, et) * generalize))) for et in spec.min_out_distinct}
        if p in emb.alternatives:  # interchangeable targets (e.g. scan victims): generalise to any host
            role = ix.roles.get(v, "workstation")
            nodes[names[p]] = NodeSpec(roles=None, internal=role not in ("external", "saas"), min_out_distinct=mod)
        else:
            nodes[names[p]] = NodeSpec(roles={ix.roles.get(v, "workstation")}, min_out_distinct=mod)
    edges = []
    for e in base.edges:
        if e.src not in emb.mapping or e.dst not in emb.mapping:
            continue
        q = matcher.qualifying_events(emb.mapping[e.src], emb.mapping[e.dst], e) or []
        types = {et for _, _, et in q} or set(e.types)
        maxb = max((b for _, b, _ in q), default=0)
        edges.append(EdgeSpec(names[e.src], names[e.dst], types, order=e.order,
                              min_count=max(1, int(math.floor(len(q) * generalize))),
                              min_bytes=int(maxb * generalize) if e.min_bytes else 0,
                              periodic=e.periodic, max_cv=e.max_cv * (1 + generalize) if e.periodic else e.max_cv,
                              weight=e.weight, essential=e.essential))
    t = Pattern(name="", kind="attack", nodes=nodes, edges=edges, tactic=base.tactic, techniques=list(base.techniques),
                max_span=base.max_span, description=f"Shared behavioural template derived from a {base.name} detection",
                benign_counterparts=list(base.benign_counterparts))
    t.name = f"shared_{base.name}_{canonical_hash(t)[:8]}"
    return t


def canonical_hash(p: Pattern) -> str:
    evs = []
    for e in p.edges:
        for k in range(min(e.min_count, 3)):
            evs.append(make_event(float(e.order) + k * 1e-3, e.src, e.dst, sorted(e.types)[0]))
    roles = {n: "|".join(sorted(s.roles)) if s.roles else "*" for n, s in p.nodes.items()}
    _, lv = temporal_color_refinement(sorted(evs, key=lambda x: x.ts), roles, depth=3, multiplicity="set",
                                      return_levels=True)
    hist = sorted(Counter((k, c) for k, l in enumerate(lv) for c in l.values()).items())
    extra = sorted((e.order, sorted(e.types), e.min_count, e.min_bytes, e.periodic) for e in p.edges)
    return hashlib.blake2b(json.dumps([hist, extra, p.max_span]).encode(), digest_size=16).hexdigest()


def _canonical_json(p: Pattern) -> str:
    d = p.to_dict()
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def sign(p: Pattern, key: bytes) -> str:
    return hmac.new(key, _canonical_json(p).encode(), hashlib.sha256).hexdigest()


def verify(p: Pattern, signature: str, key: bytes) -> bool:
    return hmac.compare_digest(sign(p, key), signature)


# Roles that every enterprise has (or that are not the sharer's assets): revealing that "a domain
# controller" or "an external host" was involved identifies nobody, even if the sharer has only one.
GENERIC_ROLES = {"dc", "dns", "fileserver", "external", "saas"}


def privacy_report(p: Pattern, index: GraphIndex, k: int = 5) -> Dict:
    role_counts = Counter(index.roles.values())
    nodes = {}
    for n, spec in p.nodes.items():
        size = sum(role_counts[r] for r in (spec.roles or role_counts.keys()))
        generic = bool(spec.roles) and spec.roles <= GENERIC_ROLES
        nodes[n] = {"roles": sorted(spec.roles or []), "anonymity_set": size, "generic_role": generic,
                    "ok": size >= k or generic}
    return {"k": k, "nodes": nodes, "all_ok": all(v["ok"] for v in nodes.values()),
            "contains_identifiers": False}


def export_package(det: Detection, matcher: PatternMatcher, key: bytes, k: int = 5, generalize: float = 0.5) -> Dict:
    t = detection_to_template(det, matcher, generalize)
    return {"template": t.to_dict(), "canonical_hash": canonical_hash(t), "signature": sign(t, key),
            "privacy": privacy_report(t, matcher.ix, k)}


def import_package(pkg: Dict, key: bytes) -> Optional[Pattern]:
    t = Pattern.from_dict(pkg["template"])
    if not verify(t, pkg["signature"], key):
        return None
    if canonical_hash(t) != pkg["canonical_hash"]:
        return None
    return t
