"""Reproducible experiment suite.

    python -m src.evaluation.experiments --out results            # full suite
    python -m src.evaluation.experiments --out results --quick    # smoke test

Produces results/results.json, results/report.md and figures in results/figures/.

E1  Detection quality vs baselines and ablations (AUC, AP, P/R/F1 at a 5%-FPR calibrated threshold)
E2  Per-scenario recall and per-look-alike false-positive rate (the alert-fatigue question)
E3  Stealth sweep (weakened attacks)
E4  Robustness: certified radii, empirical attacks, and a soundness check of the certificate
E5  Streaming: per-event refinement cost (incremental TCR vs recomputed WL) and detection latency
E6  Campaign stitching: multi-stage evidence accumulation on a stealthy kill chain
E7  Explanations: certificate verification and tamper detection
E8  Privacy-preserving sharing: a template exported by org A detects the attack at org B
E9  Individualization budget vs exactness / runtime
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from typing import Callable, Dict, List

import numpy as np

from src.core.models import EventRecord
from src.evaluation.baselines import DegreeZScore, RuleBaseline, SupervisedWLLogReg, WLHistogramAnomaly
from src.evaluation.metrics import summarize, threshold_for_fpr
from src.explanation.certificate import build_certificate, verify_certificate
from src.graph.streaming import StreamingDetector, benchmark_refinement_update
from src.ingestion.synthetic import (ATTACK_KINDS, HARD_NEGATIVE_KINDS, SyntheticEnterprise, generate_benchmark,
                                     generate_campaign)
from src.matching.matcher import PatternMatcher
from src.matching.templates import template_library
from src.pipeline import RefineMatch
from src.robustness import attacks as adv
from src.robustness.certify import INF, certify
from src.sharing.fingerprint import export_package, import_package

THR = 0.65  # RefineMatch's fixed (uncalibrated) alert threshold: above any single-step partial match (0.6)


def _rm_variants(roles) -> Dict[str, RefineMatch]:
    return {
        "RefineMatch (full)": RefineMatch(roles, threshold=THR),
        "  - no benign contrast": RefineMatch(roles, threshold=THR, use_benign=False),
        "  - no temporal order": RefineMatch(roles, threshold=THR, use_temporal=False),
        "  - no novelty term": RefineMatch(roles, threshold=THR, use_novelty=False),
        "  - no individualization": RefineMatch(roles, threshold=THR, max_individualizations=0),
    }


def run(out: str, quick: bool = False, seed: int = 0) -> dict:
    os.makedirs(os.path.join(out, "figures"), exist_ok=True)
    R: dict = {}
    t_all = time.time()
    ent = SyntheticEnterprise(seed=seed)
    roles = ent.roles
    n_hist, n_cal = (10, 10) if quick else (40, 30)
    n_ben, n_att, n_hard = (6, 2, 2) if quick else (40, 12, 8)
    history = [w.events for w in generate_benchmark(n_hist, 0, 0, seed=seed + 100, enterprise=ent)]
    calib = [w.events for w in generate_benchmark(n_cal, 0, 0, seed=seed + 200, enterprise=ent)]
    test = generate_benchmark(n_ben, n_att, n_hard, seed=seed + 300, enterprise=ent)
    train_sup = generate_benchmark(n_hist // 2, max(2, n_att // 2), max(1, n_hard // 2), seed=seed + 400, enterprise=ent)
    y = [int(w.is_attack) for w in test]

    # ------------------------------------------------------------------ E1/E2
    detectors: Dict[str, Callable[[List[EventRecord]], float]] = {}
    rms = _rm_variants(roles)
    for name, rm in rms.items():
        rm.fit_baseline(history)
        detectors[name] = (lambda rm: (lambda ev: rm.analyze_window(ev).score))(rm)
    baselines = [WLHistogramAnomaly(temporal=False), WLHistogramAnomaly(temporal=True), DegreeZScore(), RuleBaseline()]
    for b in baselines:
        b.fit(history, roles)
        detectors[b.name] = b.score
    sup = SupervisedWLLogReg().fit_supervised(train_sup, roles)
    detectors[sup.name + " [uses labels]"] = sup.score

    e1, e2, scores_all = {}, {}, {}
    for name, fn in detectors.items():
        t = time.time()
        s = [fn(w.events) for w in test]
        dt = (time.time() - t) / len(test)
        cal = [fn(ev) for ev in calib]
        thr = threshold_for_fpr(cal, 0.05)
        if name.startswith("RefineMatch") or name.startswith("  -"):
            thr = THR
        elif name.startswith("Threshold rules"):
            thr = 1.0  # binary detector: alert whenever any rule fires (calibration would disable it)
        m = summarize(y, s, thr)
        m["ms_per_window"] = dt * 1000
        e1[name] = m
        scores_all[name] = s
        per = {}
        for k in ATTACK_KINDS:
            idx = [i for i, w in enumerate(test) if w.kind == k]
            per[f"recall:{k}"] = float(np.mean([s[i] >= thr for i in idx])) if idx else float("nan")
        for k in HARD_NEGATIVE_KINDS:
            idx = [i for i, w in enumerate(test) if w.kind == k]
            per[f"fpr:{k}"] = float(np.mean([s[i] >= thr for i in idx])) if idx else float("nan")
        idx = [i for i, w in enumerate(test) if w.kind == "benign"]
        per["fpr:plain_benign"] = float(np.mean([s[i] >= thr for i in idx])) if idx else float("nan")
        e2[name] = per
        print(f"[E1] {name:52s} AUC={m['auc']:.3f} AP={m['ap']:.3f} P={m['precision']:.2f} R={m['recall']:.2f} "
              f"F1={m['f1']:.2f} FPR={m['fpr']:.2f} ({m['ms_per_window']:.1f} ms/window)")
    R["E1_detection"] = e1
    R["E2_per_scenario"] = e2

    # ------------------------------------------------------------------ E3 stealth
    rm = rms["RefineMatch (full)"]
    e3 = {}
    levels = [0.0, 0.5, 1.0] if quick else [0.0, 0.25, 0.5, 0.75, 1.0]
    for st in levels:
        ws = generate_benchmark(0, max(2, n_att // 2), 0, seed=seed + 500 + int(st * 100), stealth=st, enterprise=ent)
        row = {}
        for name in ["RefineMatch (full)", "Threshold rules (Sigma-style)", "WL-histogram anomaly (UNICORN-style)"]:
            thr = e1[name]["threshold"]
            row[name] = float(np.mean([detectors[name](w.events) >= thr for w in ws]))
        e3[str(st)] = row
        print(f"[E3] stealth={st}: " + ", ".join(f"{k.split(' ')[0]}={v:.2f}" for k, v in row.items()))
    R["E3_stealth"] = e3

    # ------------------------------------------------------------------ E4 robustness
    att = [w for w in test if w.is_attack]
    radii = defaultdict(list)
    radii_cond = defaultdict(list)
    sound_viol, sound_checks = 0, 0
    rng = np.random.default_rng(seed + 600)
    certs_for_e7 = []
    for w in att:
        rep = rm.analyze_window(w.events, w.start, w.end)
        if not rep.detections:
            continue
        d = rep.detections[0]
        m = PatternMatcher(rep.index)
        c = certify(d, m, rm.scorer, THR)
        r = c.certified_radius
        radii[w.kind].append(r)
        radii_cond[w.kind].append(min(c.deletion_lower_bound_fixed_novelty, c.insertion_lower_bound))
        certs_for_e7.append((rep, d, m, c))
        # soundness: k < deletion LB deletions that keep >= 1 event per essential step must not evade
        if d.score.contrastive_score >= THR and np.isfinite(c.deletion_lower_bound) and c.deletion_lower_bound > 1:
            k = int(c.deletion_lower_bound) - 1
            for _ in range(3):
                pert = _delete_non_essential(w.events, d, k, rng)
                sc = rm.analyze_window(pert, w.start, w.end)
                score = max((x.score.contrastive_score for x in sc.detections if x.pattern.name == d.pattern.name), default=0)
                sound_checks += 1
                sound_viol += int(score < THR)
    e4 = {"certified_radius": {k: {"median": float(np.median([min(x, 1e6) for x in v])),
                                   "frac_infinite": float(np.mean([x == INF for x in v])),
                                   "min": float(min(v)),
                                   "median_fixed_novelty": float(np.median([min(x, 1e6) for x in radii_cond[k]]))}
                               for k, v in radii.items()},
          "soundness_checks": sound_checks, "soundness_violations": sound_viol}
    # empirical attacks
    emp = {}
    budgets = {"delete": [0, 1, 3, 10], "noise": [0, 20, 100], "mimicry": [0, 3, 12], "jitter_s": [0, 120, 900],
               "beacon_jitter": [0, 2, 6]}
    if quick:
        budgets = {k: v[:2] for k, v in budgets.items()}
    hosts = ent.workstations
    for kind, bl in budgets.items():
        emp[kind] = {}
        for bgt in bl:
            hits = []
            for w in att:
                if kind == "beacon_jitter" and w.kind != "c2_beaconing":
                    continue
                attacker = sorted(w.attack_nodes & set(ent.workstations))[:1] or hosts[:1]
                if kind == "delete":
                    ev = adv.delete_attack_events(w.events, bgt, rng)
                elif kind == "noise":
                    ev = adv.insert_noise(w.events, attacker, ent.internal, bgt, rng)
                elif kind == "mimicry":
                    ev = adv.benign_mimicry(w.events, attacker[0], roles, bgt, rng)
                elif kind == "jitter_s":
                    ev = adv.timing_jitter(w.events, bgt, rng)
                else:
                    ev = adv.beacon_jitter(w.events, bgt, rng)
                hits.append(rm.analyze_window(ev, w.start, w.end).score >= THR)
            emp[kind][str(bgt)] = float(np.mean(hits)) if hits else float("nan")
        print(f"[E4] {kind}: " + ", ".join(f"{b}->{v:.2f}" for b, v in emp[kind].items()))
    e4["empirical_detection_rate"] = emp
    print(f"[E4] certificate soundness: {sound_viol} violations / {sound_checks} checks")
    R["E4_robustness"] = e4

    # ------------------------------------------------------------------ E5 streaming
    camp_events, stages, cent = generate_campaign(seed=seed + 11, enterprise=SyntheticEnterprise(seed=seed + 11))
    bench = benchmark_refinement_update(camp_events, cent.roles, max_events=300 if quick else 800)
    srm = RefineMatch(cent.roles, threshold=THR).fit_baseline(
        [w.events for w in generate_benchmark(10 if quick else 20, 0, 0, seed=seed + 12, enterprise=cent)])
    sd = StreamingDetector(srm, check_every=50)
    t = time.perf_counter()
    alerts = sd.run(camp_events)
    wall = time.perf_counter() - t
    latency = {}
    for stage, s0, s1, nodes in stages:
        lab = f"attack:{stage}"
        last_attack = max((e.ts for e in camp_events if e.label == lab), default=None)
        hit = [a for a in alerts if a.pattern == stage and s0 <= a.detected_at < s1 + 3600]
        if last_attack is not None and hit:
            latency[stage] = max(0.0, min(a.detected_at for a in hit) - last_attack)
        else:
            latency[stage] = None
    e5 = {"refinement_update": bench, "stream_events": len(camp_events), "stream_seconds": wall,
          "events_per_second": len(camp_events) / wall, "tcr_us_per_event": sd.stats["tcr_seconds"] / max(1, sd.stats["events"]) * 1e6,
          "match_checks": sd.stats["checks"], "detection_latency_s": latency,
          "alerts": [(a.pattern, a.nodes, round(a.score, 3)) for a in alerts]}
    print(f"[E5] incremental TCR {bench['incremental_tcr_us']:.1f} us/event vs static WL recompute "
          f"{bench['recompute_static_wl_us']:.0f} us/event (x{bench['speedup']:.0f}); stream {e5['events_per_second']:.0f} ev/s; "
          f"latency {latency}")
    R["E5_streaming"] = e5

    # ------------------------------------------------------------------ E6 campaign
    e6 = {}
    for st in ([0.0, 0.9] if quick else [0.0, 0.6, 0.9]):
        cevs, cstages, cent2 = _stealthy_campaign(seed + 21, st)
        crm = RefineMatch(cent2.roles, threshold=THR).fit_baseline(
            [w.events for w in generate_benchmark(10 if quick else 20, 0, 0, seed=seed + 22, enterprise=cent2)])
        reports = crm.analyze_stream(cevs)
        camps = crm.campaigns(reports, min_score=0.3)
        best_single = max((r.score for r in reports), default=0.0)
        top = camps[0] if camps else None
        e6[str(st)] = {"max_single_window_score": best_single, "campaign_score": top.score if top else 0.0,
                       "tactics": top.tactics if top else [], "narrative": top.narrative if top else [],
                       "windows_alerting": int(sum(r.score >= THR for r in reports))}
        print(f"[E6] stealth={st}: best single window {best_single:.2f} -> campaign {e6[str(st)]['campaign_score']:.2f} "
              f"({', '.join(e6[str(st)]['tactics'])})")
    R["E6_campaign"] = e6

    # ------------------------------------------------------------------ E7 explanations
    ok = tamper_caught = n = 0
    sizes = []
    examples = []
    for rep, d, m, c in certs_for_e7:
        cert = build_certificate(d, m, rm.scorer, c)
        v, _ = verify_certificate(cert, rep.index, d.pattern)
        ok += int(v)
        n += 1
        sizes.append(len(cert.evidence))
        bad = build_certificate(d, m, rm.scorer, c)
        bad.evidence[0]["timestamp"] += 1.0
        tamper_caught += int(not verify_certificate(bad, rep.index, d.pattern)[0])
        if len(examples) < len(ATTACK_KINDS) and d.pattern.name not in [e[0] for e in examples]:
            examples.append((d.pattern.name, cert.to_text()))
    R["E7_explanations"] = {"certificates": n, "verified": ok, "tamper_detected": tamper_caught,
                            "mean_evidence_events": float(np.mean(sizes)) if sizes else 0.0,
                            "examples": dict(examples)}
    print(f"[E7] {ok}/{n} certificates verify; {tamper_caught}/{n} tampered certificates rejected")

    # ------------------------------------------------------------------ E8 sharing
    key = b"community-shared-secret"
    entB = SyntheticEnterprise(seed=seed + 77, n_workstations=60, n_servers=8)
    e8 = {}
    for kind in ATTACK_KINDS:
        src_w = next(w for w in test if w.kind == kind)
        rep = rm.analyze_window(src_w.events, src_w.start, src_w.end)
        d = next((x for x in rep.detections if x.pattern.name == kind), None)
        if d is None:
            continue
        pkg = export_package(d, PatternMatcher(rep.index), key)
        tmpl = import_package(json.loads(json.dumps(pkg)), key)
        lib = {p.name: p for p in template_library().values() if p.kind == "benign"}
        lib[tmpl.name] = tmpl
        rmB = RefineMatch(entB.roles, library=lib, threshold=THR).fit_baseline(
            [w.events for w in generate_benchmark(8, 0, 0, seed=seed + 78, enterprise=entB)])
        wsB = generate_benchmark(6 if not quick else 3, 0, 0, seed=seed + 79, enterprise=entB)
        atB = []
        rngB = np.random.default_rng(seed + 80)
        for i in range(4 if not quick else 2):
            evs = entB.benign_events(wsB[0].start + i * 3600, 3600, rngB)
            aev, _ = entB.attack_events(kind, wsB[0].start + i * 3600, 3600, rngB)
            atB.append([e for e in sorted(evs + aev, key=lambda e: e.ts)])
        rec = float(np.mean([rmB.analyze_window(ev).score >= THR for ev in atB]))
        fpr = float(np.mean([rmB.analyze_window(w.events).score >= THR for w in wsB]))
        tampered = dict(pkg, template=dict(pkg["template"], max_span=1.0))
        e8[kind] = {"recall_at_B": rec, "fpr_at_B": fpr, "privacy_all_ok": pkg["privacy"]["all_ok"],
                    "signature_rejects_tampering": import_package(tampered, key) is None,
                    "template_nodes": len(tmpl.nodes), "template_edges": len(tmpl.edges)}
        print(f"[E8] {kind}: shared template recall@B={rec:.2f} FPR@B={fpr:.2f} privacy_ok={pkg['privacy']['all_ok']}")
    R["E8_sharing"] = e8

    # ------------------------------------------------------------------ E9 IR budget
    e9 = {}
    sym = _symmetric_window(ent)
    for depth in [0, 1, 2, 3]:
        rmd = RefineMatch(roles, threshold=THR, max_individualizations=depth)
        t = time.perf_counter()
        rep = rmd.analyze_window(sym)
        dt = time.perf_counter() - t
        lm = next((x for x in rep.detections if x.pattern.name == "lateral_movement"), None)
        e9[str(depth)] = {"score": rep.score, "lateral_exhaustive": lm.exhaustive if lm else None,
                          "lateral_confidence": lm.match_confidence if lm else None, "seconds": dt}
    print(f"[E9] {e9}")
    R["E9_individualization"] = e9

    R["meta"] = {"quick": quick, "seed": seed, "seconds": time.time() - t_all, "test_windows": len(test),
                 "attack_windows": sum(y), "threshold_refinematch": THR}
    with open(os.path.join(out, "results.json"), "w") as fh:
        json.dump(R, fh, indent=2, default=lambda o: None if o != o else str(o))
    _figures(R, os.path.join(out, "figures"))
    _report(R, os.path.join(out, "report.md"))
    print(f"done in {R['meta']['seconds']:.0f}s -> {out}/report.md")
    return R


def _delete_non_essential(events, det, k, rng):
    """Delete k attacker events but keep >= 1 event of every essential pattern edge (certificate threat model)."""
    mp = det.embedding.mapping
    keep_one = {}
    for e in det.pattern.edges:
        if e.essential and e.src in mp and e.dst in mp:
            keep_one[(mp[e.src], mp[e.dst])] = e.types
    att = [i for i, e in enumerate(events) if e.label and e.label.startswith("attack")]
    rng.shuffle(att)
    drop, protected = set(), {}
    for i in att:
        e = events[i]
        key = (e.source, e.destination)
        if key in keep_one and e.event_type in keep_one[key] and not protected.get(key):
            protected[key] = True
            continue
        if len(drop) < k:
            drop.add(i)
    return [e for i, e in enumerate(events) if i not in drop]


def _stealthy_campaign(seed, stealth):
    ent = SyntheticEnterprise(seed=seed)
    rng = np.random.default_rng(seed)
    p0 = ent.workstations[5]
    s0, ev, stages, last = 1_700_000_000.0, [], [], p0
    ev += ent.benign_events(s0, 3600, rng)
    s0 += 3600
    for stage in ["network_scan", "kerberoasting", "lateral_movement", "exfiltration"]:
        ev += ent.benign_events(s0, 3600, rng)
        a, nodes = ent.attack_events(stage, s0, 3600, rng, attacker=p0 if stage != "exfiltration" else last, stealth=stealth)
        if stage == "lateral_movement":
            hops = [e.destination for e in a if e.event_type == "auth_remote"]
            last = hops[-1] if hops else p0
        ev += [e for e in a if e.ts < s0 + 3600]
        stages.append((stage, s0, s0 + 3600, nodes))
        s0 += 3600
    return sorted(ev, key=lambda e: e.ts), stages, ent


def _symmetric_window(ent):
    """Many structurally identical remote-logon chains: refinement alone cannot resolve them."""
    from src.core.models import make_event
    rng = np.random.default_rng(5)
    s0 = 1_700_100_000.0
    ev = ent.benign_events(s0, 3600, rng)
    ws = ent.workstations
    for i in range(0, 24, 3):
        a, b, c = ws[i], ws[i + 1], ws[i + 2]
        t = s0 + 100 + i * 10
        ev += [make_event(t, a, b, "auth_remote", label="attack:lateral_movement"),
               make_event(t + 50, b, c, "auth_remote", label="attack:lateral_movement")]
    return sorted(ev, key=lambda e: e.ts)


def _figures(R, outdir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    C = ["#2a6fdb", "#e07a1f", "#3a9e5f", "#b5384b", "#7d5ba6", "#8c8c8c", "#1aa3a3", "#c9a227", "#555555", "#d45fa1"]
    # E1 bar: F1 and FPR
    e1 = R["E1_detection"]
    names = list(e1)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = np.arange(len(names))
    ax.bar(x - 0.2, [e1[n]["f1"] for n in names], 0.4, label="F1", color=C[0])
    ax.bar(x + 0.2, [e1[n]["fpr"] for n in names], 0.4, label="FPR", color=C[1])
    ax.set_xticks(x)
    ax.set_xticklabels([n.strip() for n in names], rotation=35, ha="right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("E1: detection quality (synthetic enterprise, hard negatives included)")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "e1_detection.png"), dpi=160)
    plt.close(fig)
    # E3 stealth
    e3 = R["E3_stealth"]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    lv = sorted(e3, key=float)
    for i, name in enumerate(next(iter(e3.values()))):
        ax.plot([float(l) for l in lv], [e3[l][name] for l in lv], marker="o", label=name, color=C[i])
    ax.set_xlabel("attack stealth")
    ax.set_ylabel("recall")
    ax.set_ylim(-0.02, 1.05)
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("E3: recall under stealthier attacks")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "e3_stealth.png"), dpi=160)
    plt.close(fig)
    # E4 empirical robustness
    emp = R["E4_robustness"]["empirical_detection_rate"]
    fig, axes = plt.subplots(1, len(emp), figsize=(3 * len(emp), 3), sharey=True)
    for ax, (k, v) in zip(np.atleast_1d(axes), emp.items()):
        ks = list(v)
        ax.plot(range(len(ks)), [v[b] for b in ks], marker="o", color=C[0])
        ax.set_xticks(range(len(ks)))
        ax.set_xticklabels(ks)
        ax.set_title(k, fontsize=9)
        ax.set_ylim(-0.02, 1.05)
        ax.spines[["top", "right"]].set_visible(False)
    np.atleast_1d(axes)[0].set_ylabel("detection rate")
    fig.suptitle("E4: detection under adversarial perturbation budgets", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "e4_robustness.png"), dpi=160)
    plt.close(fig)


def _fmt(x, p=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        if x != x:
            return "-"
        if x == float("inf"):
            return "∞"
        return f"{x:.{p}f}"
    return str(x)


def _report(R, path):
    L = ["# RefineMatch -- experiment report", "",
         f"Synthetic enterprise benchmark, seed {R['meta']['seed']}, {R['meta']['test_windows']} test windows "
         f"({R['meta']['attack_windows']} with attacks). RefineMatch uses a fixed threshold "
         f"{R['meta']['threshold_refinematch']}; baselines are calibrated to 5% FPR on held-out benign traffic. "
         "**All numbers are from synthetic data and must be re-measured on LANL / OpTC before publication.**", "",
         "## E1 Detection quality", "", "| Detector | AUC | AP | Precision | Recall | F1 | FPR | ms/window |", "|---|---|---|---|---|---|---|---|"]
    for n, m in R["E1_detection"].items():
        L.append(f"| {n.strip()} | {_fmt(m['auc'], 3)} | {_fmt(m['ap'], 3)} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | "
                 f"{_fmt(m['f1'])} | {_fmt(m['fpr'])} | {_fmt(m['ms_per_window'], 1)} |")
    L += ["", "## E2 Per-scenario recall / look-alike false-positive rate", ""]
    cols = [f"recall:{k}" for k in ATTACK_KINDS] + [f"fpr:{k}" for k in HARD_NEGATIVE_KINDS] + ["fpr:plain_benign"]
    L.append("| Detector | " + " | ".join(c.replace("recall:", "R ").replace("fpr:", "FPR ") for c in cols) + " |")
    L.append("|---" * (len(cols) + 1) + "|")
    for n, per in R["E2_per_scenario"].items():
        L.append(f"| {n.strip()} | " + " | ".join(_fmt(per[c]) for c in cols) + " |")
    L += ["", "## E3 Stealth sweep (recall)", "", "| stealth | " + " | ".join(next(iter(R["E3_stealth"].values()))) + " |",
          "|---" * (1 + len(next(iter(R["E3_stealth"].values())))) + "|"]
    for st, row in R["E3_stealth"].items():
        L.append(f"| {st} | " + " | ".join(_fmt(v) for v in row.values()) + " |")
    e4 = R["E4_robustness"]
    L += ["", "## E4 Robustness", "", "Certified radius (minimum adversarial event edits needed to evade):", "",
          "| Scenario | median (unconditional) | min | fraction ∞ | median if novelty is not manipulable |", "|---|---|---|---|---|"]
    inf = lambda x: _fmt(x, 0) if x < 1e6 else "∞"
    for k, v in e4["certified_radius"].items():
        L.append(f"| {k} | {inf(v['median'])} | {inf(v['min'])} | {_fmt(v['frac_infinite'])} | {inf(v['median_fixed_novelty'])} |")
    L += ["", f"Certificate soundness check: **{e4['soundness_violations']} violations in {e4['soundness_checks']} "
              "attacks with fewer edits than the certified bound**.", "", "Empirical detection rate vs. perturbation budget:", ""]
    for k, v in e4["empirical_detection_rate"].items():
        L.append(f"- {k}: " + ", ".join(f"{b} → {_fmt(x)}" for b, x in v.items()))
    e5 = R["E5_streaming"]
    b = e5["refinement_update"]
    L += ["", "## E5 Streaming", "",
          f"- Keeping colours current: incremental TCR **{b['incremental_tcr_us']:.1f} µs/event** vs recomputing static WL "
          f"{b['recompute_static_wl_us']:.0f} µs/event (**×{b['speedup']:.0f}**, over {b['events']} events).",
          f"- End-to-end streaming detector: {e5['events_per_second']:.0f} events/s ({e5['match_checks']} triggered match checks).",
          "- Detection latency after the last attack event: " +
          ", ".join(f"{k}: {('%.0fs' % v) if v is not None else 'missed'}" for k, v in e5["detection_latency_s"].items())]
    L += ["", "## E6 Campaign stitching", "", "| stealth | best single-window score | campaign score | windows alerting | tactics |",
          "|---|---|---|---|---|"]
    for st, v in R["E6_campaign"].items():
        L.append(f"| {st} | {_fmt(v['max_single_window_score'])} | {_fmt(v['campaign_score'])} | {v['windows_alerting']} | "
                 f"{' → '.join(v['tactics'])} |")
    e7 = R["E7_explanations"]
    L += ["", "## E7 Explanations", "",
          f"- {e7['verified']}/{e7['certificates']} certificates independently verified against raw events; "
          f"{e7['tamper_detected']}/{e7['certificates']} tampered certificates rejected.",
          f"- Mean evidence size: {e7['mean_evidence_events']:.1f} events per alert.", "", "Example certificates:", ""]
    for name, txt in e7["examples"].items():
        L += ["```", txt, "```", ""]
    L += ["## E8 Privacy-preserving sharing (org A → org B)", "", "| Template | recall @B | FPR @B | privacy k-anon ok | tamper rejected |",
          "|---|---|---|---|---|"]
    for k, v in R["E8_sharing"].items():
        L.append(f"| {k} | {_fmt(v['recall_at_B'])} | {_fmt(v['fpr_at_B'])} | {v['privacy_all_ok']} | {v['signature_rejects_tampering']} |")
    L += ["", "## E9 Individualization budget (8 symmetric remote-logon chains)", "", "| depth | score | exhaustive | confidence | seconds |",
          "|---|---|---|---|---|"]
    for dpt, v in R["E9_individualization"].items():
        L.append(f"| {dpt} | {_fmt(v['score'])} | {v['lateral_exhaustive']} | {_fmt(v['lateral_confidence'])} | {_fmt(v['seconds'], 3)} |")
    L += ["", f"_Total runtime {R['meta']['seconds']:.0f}s._", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    run(a.out, a.quick, a.seed)
