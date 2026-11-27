r"""Robustness certificates for a detection.

Threat model
------------
The adversary controls the hosts in the detected embedding: it can **avoid** (delete) any of the
events it generated, and **insert** arbitrary extra events from those hosts. It cannot rewrite the
asset inventory (roles come from a CMDB / service observations it does not control) and it cannot
delete events of uncompromised hosts. The goal is to push the contrastive score below the alert
threshold.

What we certify
---------------
* **Deletion lower bound** ``r_del``: every exact embedding of the attack template must be broken.
  Breaking an embedding costs at least the cheapest of its edge/node constraints (events to remove
  so a pattern edge stops qualifying, or so a fan-out drops below its distinct-target threshold),
  multiplied by the number of interchangeable leaf alternatives. Since *every* embedding must be
  broken, ``max_m min_cost(m)`` is a sound lower bound (and a greedy hitting set gives an upper
  bound -- an explicit evasion plan). Deletions cannot create new embeddings (containment and
  temporal order and periodic-subsequence tests are monotone under deletion).
* **Insertion (benign-mimicry) bound** ``r_ins``: insertions never decrease attack similarity for
  monotone templates (subgraph containment is monotone), so the only insertion route is to make a
  benign template explain the evidence. Because benign templates carry role constraints the
  adversary cannot change, we compute the *maximum achievable* explanation fraction exactly; if it
  is below what is needed to cross the threshold, the detection is certified immune to any number
  of insertions (``r_ins = inf``). Otherwise we report LB = 1 and the cost of an explicit
  completion attack as UB.
* **Novelty**: edits can change TCR colours and hence the novelty term. All bounds above assume
  the worst case (novelty forced to 0), so they hold unconditionally; a tighter bound that holds
  the novelty term fixed is reported separately as ``deletion_lower_bound_fixed_novelty``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.core.config import DEFAULT_MATCH_THRESHOLD
from src.matching.matcher import Embedding, PatternMatcher
from src.matching.pattern import EdgeSpec, Pattern
from src.scoring.contrastive import ContrastiveScorer, Detection

INF = float("inf")


@dataclass
class RobustnessCertificate:
    threshold: float
    deletion_lower_bound: float
    deletion_upper_bound: float
    deletion_plan: List[str]
    insertion_lower_bound: float
    insertion_upper_bound: float
    insertion_plan: List[str]
    max_benign_explain: float
    needed_benign: float
    novelty_safe: bool
    monotone: bool
    exhaustive: bool
    notes: List[str] = field(default_factory=list)
    deletion_lower_bound_fixed_novelty: float = 0.0   # conditional: assumes the novelty term is unchanged

    @property
    def certified_radius(self) -> float:
        """Minimum number of adversarial event edits guaranteed to be needed to evade."""
        return min(self.deletion_lower_bound, self.insertion_lower_bound)

    def summary(self) -> str:
        def f(x):
            return "inf" if x == INF else str(int(x))
        s = (f"certified radius {f(self.certified_radius)} edits "
             f"(deletion >= {f(self.deletion_lower_bound)}, insertion >= {f(self.insertion_lower_bound)})")
        if self.deletion_lower_bound_fixed_novelty > self.deletion_lower_bound:
            s += f"; {f(self.deletion_lower_bound_fixed_novelty)} deletions if the novelty term cannot be manipulated"
        return s


def _edge_break_cost(matcher: PatternMatcher, e: EdgeSpec, u: str, v: str) -> float:
    """Minimum edits so that u->v stops satisfying edge spec e.

    Non-essential steps can simply be skipped. Essential steps must still happen at least once:
    the adversary may only thin them out below ``min_count`` or split large transfers into chunks
    below ``min_bytes`` (1 deletion + ceil(bytes/min_bytes) insertions per large transfer)."""
    evs = matcher.qualifying_events(u, v, e)
    if evs is None:
        return 0
    allev = matcher.ix.events_between(u, v, e.types)
    if e.periodic:
        # evs is the longest periodic chain (length L); d deletions split it into <= d+1 runs, so
        # every run drops below min_count m only if d >= (L - m + 1) / m  (sound lower bound)
        L = len(evs)
        cost_count = math.ceil((L - e.min_count + 1) / e.min_count) if (not e.essential or e.min_count >= 2) else INF
    else:
        cost_count = len(evs) - e.min_count + 1 if (not e.essential or e.min_count >= 2) else INF
    if e.min_bytes > 0:
        big = [x for x in allev if x[1] >= e.min_bytes]
        if e.essential:
            cost_bytes = sum(1 + math.ceil(b / max(1, e.min_bytes - 1)) for _, b, _ in big)
        else:
            cost_bytes = len(big)
    else:
        cost_bytes = INF
    return min(cost_bytes, cost_count)


def _node_break_cost(matcher: PatternMatcher, pattern: Pattern, p: str, u: str) -> float:
    spec = pattern.nodes[p]
    best = INF
    for et, n in spec.min_out_distinct.items():
        targets = matcher.ix.out.get(u, {}).get(et, {})
        if len(targets) < n:
            return 0
        counts = sorted(len(x) for x in targets.values())
        best = min(best, sum(counts[: len(targets) - n + 1]))
    return best


def _order_feasible(pattern: Pattern, lists: Dict[int, List[float]]) -> bool:
    groups: Dict[int, List[int]] = {}
    for i, e in enumerate(pattern.edges):
        groups.setdefault(e.order, []).append(i)
    orders = sorted(groups)
    starts = sorted({t for i in groups[orders[0]] for t in lists[i]})
    for s0 in starts:
        prev, first, ok, t_first = s0, True, True, None
        for o in orders:
            gmax = prev
            for i in groups[o]:
                cand = [t for t in lists[i] if (t >= prev if first else t > prev)]
                if not cand:
                    ok = False
                    break
                t = min(cand)
                t_first = t if t_first is None else t_first
                if t - t_first > pattern.max_span:
                    ok = False
                    break
                gmax = max(gmax, t)
            if not ok:
                break
            prev, first = gmax, False
        if ok:
            return True
    return False


def _temporal_break_cost(matcher: PatternMatcher, pattern: Pattern, m: Embedding, max_events: int = 14) -> int:
    """Exact minimum number of deleted events that destroys every order-respecting selection
    (brute force for small evidence sets, else the trivially sound bound 1)."""
    lists = {}
    for i, e in enumerate(pattern.edges):
        evs = matcher.qualifying_events(m.mapping[e.src], m.mapping[e.dst], e) or []
        lists[i] = [t for t, _, _ in evs]
    flat = [(i, t) for i, ts in lists.items() for t in ts]
    if len(flat) > max_events:
        return 1  # sound fallback
    for k in range(1, len(flat) + 1):
        for rem in itertools.combinations(range(len(flat)), k):
            rs = set(rem)
            sub = {i: [] for i in lists}
            for j, (i, t) in enumerate(flat):
                if j not in rs:
                    sub[i].append(t)
            if any(not sub[i] and pattern.edges[i].essential for i in sub):
                continue  # an essential step cannot be avoided entirely
            if any(not v for v in sub.values()) or not _order_feasible(pattern, sub):
                return k
    return INF if any(e.essential for e in pattern.edges) else len(flat)


def _break_options(matcher: PatternMatcher, pattern: Pattern, m: Embedding, tag) -> list:
    """Ways to break embedding m: (sound cost, key, description)."""
    opts = []
    for e in pattern.edges:
        u, v = m.mapping[e.src], m.mapping[e.dst]
        c = _edge_break_cost(matcher, e, u, v)
        if c == INF:
            continue
        leaf = e.dst if e.dst in m.alternatives else (e.src if e.src in m.alternatives else None)
        mult = m.alternatives.get(leaf, 1) if leaf else 1
        # every interchangeable alternative needs >= 1 deletion; the representative needs c
        cost = c + (mult - 1)
        key = ("edge", u, v if mult == 1 else "*", tuple(sorted(e.types)))
        verb = "split large" if (e.essential and e.min_bytes > 0) else f"suppress {c}"
        desc = (f"{verb} '{'/'.join(sorted(e.types))}' event(s) {u}->{v} ({c} edits)" if mult == 1 else
                f"suppress '{'/'.join(sorted(e.types))}' events from {u} to all {mult} alternatives (>= {cost})")
        opts.append((cost, key, desc))
    if len({e.order for e in pattern.edges}) > 1:
        c = _temporal_break_cost(matcher, pattern, m)
        if c < INF:
            opts.append((c, ("temporal", tuple(sorted(m.mapping.items()))),
                         f"delete {c} event(s) so the steps no longer occur in causal order"))
    for p, u in m.mapping.items():
        c = _node_break_cost(matcher, pattern, p, u)
        if c < INF:
            opts.append((c, ("node", u, tuple(sorted(pattern.nodes[p].min_out_distinct))),
                         f"reduce fan-out of {u} below threshold ({c} events)"))
    return opts


def deletion_bounds(matcher: PatternMatcher, pattern: Pattern, needed_similarity: float,
                    scorer: Optional[ContrastiveScorer] = None, mod: float = 1.0, threshold: float = 0.0):
    """Deletions needed so that no (relaxed) embedding keeps a contrastive score >= threshold.

    An embedding must be broken only if its similarity is >= ``needed_similarity`` (computed with the
    detection's own benign term) *and* its own benign explanation does not already push it below the
    threshold (deletions can only shrink benign explanations, so this filter is sound).
    Returns (sound lower bound, greedy upper bound, plan, exhaustive)."""
    options_per_emb, exhaustive = [], True
    cache: dict = {}
    for idx, f in PatternMatcher.relaxation_variants(pattern):
        cov = sum(pattern.edges[i].weight for i in idx) / pattern.total_weight
        if cov * f < needed_similarity - 1e-12:
            continue
        sub, embs, exh = matcher.match_variant(pattern, idx, f)
        exhaustive &= exh
        for m in embs:
            if m.score < needed_similarity - 1e-12:
                continue
            if scorer is not None and scorer.use_benign:
                b, _, _ = scorer.benign_similarity(matcher, pattern, m, cache)
                if m.score * max(0.0, 1 - scorer.lam * b) * mod < threshold:
                    continue
            opts = _break_options(matcher, sub, m, (tuple(idx), f))
            if not opts:
                return INF, INF, ["every step is essential: cannot evade by deletion; the adversary must "
                                  "change timing or tactic"], exhaustive
            options_per_emb.append(opts)
    if not options_per_emb:
        return 0, 0, [], exhaustive
    lb = max(min(o[0] for o in opts) for opts in options_per_emb)
    remaining = list(range(len(options_per_emb)))
    plan, cost, chosen = [], 0, set()
    while remaining:
        tally: Dict[tuple, list] = {}
        for i in remaining:
            for c, key, desc in options_per_emb[i]:
                if key in chosen:
                    continue
                cur = tally.setdefault(key, [c, 0, desc])
                cur[0] = max(cur[0], c)
                cur[1] += 1
        if not tally:
            break
        key, (c, hits, desc) = min(tally.items(), key=lambda kv: kv[1][0] / kv[1][1])
        chosen.add(key)
        cost += c
        plan.append(desc)
        remaining = [i for i in remaining if not any(k == key for _, k, _ in options_per_emb[i])]
    return lb, max(cost, lb), plan, exhaustive


def max_benign_explanation(scorer: ContrastiveScorer, matcher: PatternMatcher, attack: Pattern, emb: Embedding):
    """Exact upper bound on explain_fraction achievable by inserting events, given fixed roles.

    An attack evidence event (u->v, tau) can only ever be explained by a benign edge spec whose
    source node accepts role(u), destination accepts role(v), and whose types include tau."""
    wmap = {(e.src, e.dst): e.weight for e in attack.edges}
    best, best_b, missing = 0.0, None, []
    for bname in attack.benign_counterparts:
        b = scorer.lib.get(bname)
        if b is None:
            continue
        tot = cov = 0.0
        miss = []
        for ev in emb.evidence:
            w = wmap.get((ev.pattern_src, ev.pattern_dst), 1.0)
            tot += w
            ru = matcher.ix.roles.get(ev.source, "workstation")
            rv = matcher.ix.roles.get(ev.destination, "workstation")
            ok = False
            for be in b.edges:
                if ev.event_type not in be.types:
                    continue
                s_spec, d_spec = b.nodes[be.src], b.nodes[be.dst]
                role_ok = lambda spec, r: (spec.roles is None or r in spec.roles) and r not in spec.not_roles and \
                    (spec.internal is None or (r not in ("external", "saas")) == spec.internal)
                if role_ok(s_spec, ru) and role_ok(d_spec, rv):
                    ok = True
                    break
            if ok:
                cov += w
            else:
                miss.append(f"{ev.source}({ru})->{ev.destination}({rv}) '{ev.event_type}' cannot match any edge of {bname}")
        frac = cov / tot if tot else 0.0
        if frac > best or best_b is None:
            best, best_b, missing = frac, bname, miss
    return best, best_b, missing


def certify(detection: Detection, matcher: PatternMatcher, scorer: ContrastiveScorer,
            threshold: float = DEFAULT_MATCH_THRESHOLD) -> RobustnessCertificate:
    attack, emb, sc = detection.pattern, detection.embedding, detection.score
    monotone = True  # containment, causal order and periodic-subsequence tests are all insertion-monotone
    notes = []
    a = sc.attack_similarity
    keep = max(1e-9, 1 - scorer.lam * sc.benign_similarity)  # benign explanation only shrinks under deletion
    mod_now = scorer.alpha + (1 - scorer.alpha) * sc.frequency_score
    mod_worst = scorer.alpha  # the adversary may also drive the novelty term to 0
    # Unconditional bound: an embedding keeps the alert alive whatever happens to novelty only if
    # score * keep * alpha >= threshold, so exactly those must be broken.
    lb, ub, plan, exh = deletion_bounds(matcher, attack, threshold / (keep * mod_worst), scorer, mod_worst, threshold)
    # Conditional bound (novelty held at its current value) -- reported separately, never as the radius.
    lb_c, _, _, _ = deletion_bounds(matcher, attack, threshold / (keep * mod_now), scorer, mod_now, threshold)
    if not exh:
        notes.append("embedding enumeration hit its budget; deletion LB is still sound, UB may be optimistic")

    # benign similarity needed so that a * (1 - lam b) * alpha < threshold (worst-case novelty)
    if a * mod_worst <= 0:
        needed = 0.0
    else:
        needed = max(0.0, (1 - threshold / (a * mod_worst)) / scorer.lam) if scorer.lam > 0 else INF
    max_exp, bname, missing = max_benign_explanation(scorer, matcher, attack, emb)
    if not scorer.use_benign or needed == INF:
        ins_lb, ins_ub, ins_plan = INF, INF, ["benign contrast disabled: insertions cannot lower the score"]
    elif a * mod_worst < threshold:
        ins_lb, ins_ub, ins_plan = 1, INF, ["novelty manipulation alone could lower the score below threshold"]
    elif max_exp <= needed:
        ins_lb, ins_ub, ins_plan = INF, INF, [f"no benign template can explain >= {needed:.2f} of the evidence "
                                              f"(max {max_exp:.2f} via {bname})"] + missing
    else:
        ins_lb = 1
        b = scorer.lib[bname]
        ins_ub = sum(e.min_count for e in b.edges)
        ins_plan = [f"complete '{bname}' around the attack hosts with ~{ins_ub} fabricated events"]
    novelty_safe = a * keep * scorer.alpha >= threshold
    return RobustnessCertificate(threshold, lb, ub, plan, ins_lb, ins_ub, ins_plan, max_exp, needed,
                                 novelty_safe, monotone, exh, notes, lb_c)
