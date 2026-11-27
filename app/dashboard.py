"""RefineMatch analyst dashboard.

    streamlit run app/dashboard.py
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(__file__))

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import ui
from ui import C, badge, bar, card, esc, html, kpi, kpi_row, risk_badge, row, score_color, section

from src.explanation.certificate import build_certificate, verify_certificate
from src.ingestion.synthetic import (ATTACK_KINDS, HARD_NEGATIVE_KINDS, SyntheticEnterprise, generate_benchmark,
                                     generate_campaign)
from src.matching.matcher import PatternMatcher
from src.pipeline import RefineMatch
from src.robustness.certify import INF, certify
from src.scoring.campaign import TACTIC_ORDER

st.set_page_config(page_title="RefineMatch", page_icon="◆", layout="wide")
ui.inject_css()
st.markdown("""<style>
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
  background:#ffffff; border:1px solid #e1e5eb !important; border-radius:16px !important;
  box-shadow:0 1px 3px rgba(30,42,56,0.07), 0 1px 2px rgba(30,42,56,0.04); }
</style>""", unsafe_allow_html=True)

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
pretty = lambda name: name.replace("_", " ").replace("-", " ").capitalize()
fmt_t = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
fmt_r = lambda x: "∞" if x == INF else f"{int(x)}"

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    html("""<div style="padding:4px 0 14px 0;border-bottom:1px solid #e1e5eb;margin-bottom:14px">
    <div class="rm-eyebrow">Analyst console</div>
    <div style="font-family:var(--rm-serif);font-size:1.7rem;color:#1e2a38;line-height:1.1;margin-top:4px">RefineMatch</div>
    </div>""")
    html('<div class="rm-eyebrow" style="margin-bottom:6px">Scenario</div>')
    mode = st.radio("view", ["Single window", "Multi-stage campaign"], label_visibility="collapsed")
    kind = st.selectbox("window content", ["benign"] + ATTACK_KINDS + [f"look-alike: {k}" for k in HARD_NEGATIVE_KINDS],
                        format_func=lambda k: ("Look-alike · " + pretty(k.split(": ")[1])) if k.startswith("look-alike")
                        else pretty(k), disabled=mode != "Single window")
    stealth = st.slider("attack stealth", 0.0, 1.0, 0.0, 0.05, disabled=mode != "Single window")
    seed = st.number_input("random seed", 0, 10_000, 0)
    html('<div class="rm-eyebrow" style="margin:18px 0 6px 0;padding-top:14px;border-top:1px solid #e1e5eb">Detector</div>')
    thr = st.slider("alert threshold", 0.1, 1.0, 0.65, 0.05)
    use_benign = st.toggle("Benign contrast", True)
    use_temporal = st.toggle("Temporal order", True)
    use_novelty = st.toggle("Novelty term", True)
    html('<div class="rm-note" style="margin-top:14px;font-size:.8rem">Turn components off to see what each one '
         'contributes, e.g. disable benign contrast on a look-alike window.</div>')


@st.cache_resource(show_spinner="Learning benign colour profile…")
def engine(seed, use_benign, use_temporal, use_novelty, thr):
    ent = SyntheticEnterprise(seed=int(seed))
    rm = RefineMatch(ent.roles, threshold=thr, use_benign=use_benign, use_temporal=use_temporal, use_novelty=use_novelty)
    rm.fit_baseline([w.events for w in generate_benchmark(15, 0, 0, seed=int(seed) + 100, enterprise=ent)])
    return ent, rm


ent, rm = engine(seed, use_benign, use_temporal, use_novelty, thr)

# ----------------------------------------------------------------------------- hero
ui.hero("Temporal graph intrusion detection",
        "Attacks <em>proven</em>, not predicted.",
        "Every alert is a verifiable match of an ATT&CK behaviour in causal order, contrasted against sanctioned "
        "look-alikes, and shipped with a certificate and a guaranteed evasion cost.",
        [badge("training-free", "blue"), badge("verifiable certificates", "teal"),
         badge("certified robustness", "purple"), badge("streaming", "neutral")])


# ----------------------------------------------------------------------------- components
def detection_card(d, selected: bool) -> str:
    s = d.score
    col = score_color(s.contrastive_score, thr)
    tags = badge(pretty(d.pattern.tactic), "purple") + "".join(badge(t, "neutral") for t in d.pattern.techniques)
    body = (f'<div style="margin-bottom:10px">{tags}</div>'
            f'<div class="rm-mono" style="margin-bottom:12px">{esc(" · ".join(d.nodes))}</div>'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">'
            f'<span class="rm-kpi-label">Contrastive score</span>'
            f'<span class="rm-mono" style="color:{col};font-size:1.05rem">{s.contrastive_score:.2f}</span></div>'
            f'{bar(s.contrastive_score, col)}'
            f'<div style="margin-top:10px">{row("attack similarity", f"{s.attack_similarity:.2f}")}'
            f'{row("benign explanation", f"{s.benign_similarity:.2f}")}'
            f'{row("closest look-alike", esc(pretty(s.best_benign)) if s.best_benign else "—")}</div>')
    return card(pretty(d.pattern.name), body, risk_badge(s.risk_level), eyebrow="detection",
                extra_class="rm-lift" + (" rm-selected" if selected else ""))


def evidence_step(e) -> str:
    extra = badge(f"{e['max_bytes'] / 1e6:.0f} MB", "neutral") if e.get("max_bytes") else ""
    return (f'<div class="rm-step"><div class="rm-step-n">{e["order"]}</div><div>'
            f'<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap">'
            f'<span class="rm-mono" style="color:#1e2a38">{esc(e["source"])} → {esc(e["destination"])}</span>'
            f'<span class="rm-mono rm-muted">{fmt_t(e["timestamp"])} UTC</span></div>'
            f'<div style="margin-top:4px">{badge(e["event_type"], "blue")}{badge("× " + str(e.get("count", 1)), "neutral")}'
            f'{extra}</div></div></div>')


def show_report(rep, key):
    score = rep.score
    alerting = score >= thr
    kpi_row([
        kpi("Window score", f"{score:.2f}", "max contrastive score", score_color(score, thr)),
        kpi("Verdict", "ALERT" if alerting else "CLEAR", f"threshold {thr:.2f}", C["error"] if alerting else C["success"]),
        kpi("Alerts", str(len(rep.alerts)),
            f"{len(rep.detections)} template{'' if len(rep.detections) == 1 else 's'} matched"),
        kpi("Events", f"{len(rep.graph.events):,}", "in this window"),
        kpi("Hosts", str(rep.graph.graph.number_of_nodes()), "observed"),
    ])
    if not rep.detections:
        html('<div class="rm-note">No attack template matched this window.</div>')
        return
    section("Detections", "ranked by contrastive score")
    names = [d.pattern.name for d in rep.detections]
    pick = st.selectbox("Inspect detection", names, format_func=pretty, key=f"pick-{key}")
    cards = "".join(detection_card(d, d.pattern.name == pick) for d in rep.detections)
    html(f'<div class="rm-grid" style="grid-template-columns:repeat(auto-fit,minmax(290px,1fr))">{cards}</div>')

    det = next(d for d in rep.detections if d.pattern.name == pick)
    m = PatternMatcher(rep.index)
    rc = certify(det, m, rm.scorer, thr)
    cert = build_certificate(det, m, rm.scorer, rc)
    ok, problems = verify_certificate(cert, rep.index, det.pattern)

    section(f"Why “{pretty(det.pattern.name)}” fired", "detection certificate")
    left, right = st.columns([1.25, 1], gap="medium")
    with left:
        with st.container(border=True):
            sub = "Solid: attack steps in causal order" + (" · dashed: closest benign explanation"
                                                            if det.benign_embedding is not None else "")
            html(f'<div class="rm-eyebrow">Evidence subgraph</div>'
                 f'<div class="rm-muted" style="font-size:.85rem;margin:2px 0 6px 0">{sub}</div>')
            nodes = [(v, rep.index.roles.get(v, "?"), p) for p, v in det.embedding.mapping.items()]
            edges = [(e.source, e.destination, f"{e.order} · {e.event_type}")
                     for e in sorted(det.embedding.evidence, key=lambda e: e.order)]
            benign = [(e.source, e.destination, f"benign · {e.event_type}") for e in det.benign_embedding.evidence] \
                if det.benign_embedding is not None else []
            st.graphviz_chart(ui.graph_dot(nodes, edges, benign), use_container_width=True)
        steps = "".join(evidence_step(e) for e in sorted(cert.evidence, key=lambda x: (x["order"], x["timestamp"])))
        html(card("Causal evidence", steps, badge(f"temporal {det.score.temporal_score:.2f}", "teal"),
                  eyebrow="one raw event per step"))
    with right:
        status = ('<div class="rm-verified">✓ Independently verified against raw events</div>' if ok else
                  f'<div style="color:{C["error"]}">✗ Verification failed: {esc("; ".join(problems))}</div>')
        hosts = "".join(row(f"node {p}", f"{esc(v)} <span class='rm-muted'>({esc(cert.roles.get(v, '?'))})</span>")
                        for p, v in sorted(cert.mapping.items()))
        facts = "".join(f'<div class="rm-note" style="margin-top:8px">{esc(f)}</div>' for f in cert.node_facts)
        contrast = "".join(f'<div class="rm-note" style="margin-top:8px">{esc(b)}</div>' for b in cert.benign_contrast)
        html(card("Verification", f'{status}<div style="margin-top:10px">{hosts}</div>{facts}{contrast}',
                  badge("exhaustive" if cert.exhaustive else "budget-limited", "teal" if cert.exhaustive else "warning"),
                  eyebrow="machine-checkable"))
        plan = "".join(f"<li>{esc(p)}</li>" for p in (rc.deletion_plan[:3] + rc.insertion_plan[:2]))
        rob = (f'<div style="display:flex;align-items:flex-end;gap:12px;margin-bottom:8px">'
               f'<div class="rm-big">{fmt_r(rc.certified_radius)}</div>'
               f'<div class="rm-muted" style="padding-bottom:6px">attacker edits needed<br/>to evade (lower bound)</div></div>'
               f'{row("deletions", "≥ " + fmt_r(rc.deletion_lower_bound))}'
               f'{row("insertions", "≥ " + fmt_r(rc.insertion_lower_bound))}'
               f'{row("if novelty is fixed", "≥ " + fmt_r(rc.deletion_lower_bound_fixed_novelty))}'
               f'<div class="rm-note" style="margin-top:10px"><div class="rm-kpi-label" style="margin-bottom:4px">'
               f'Cheapest evasion analysis</div><ul style="margin:0;padding-left:18px">{plan}</ul></div>')
        html(card("Robustness", rob, badge("sound", "purple"), eyebrow="certified radius"))
    with st.expander("Raw certificate and refinement trace"):
        st.code(cert.to_text(), language=None)
        st.json(cert.refinement_trace, expanded=False)


def timeline_chart(reports):
    df = pd.DataFrame({"window": [f"W{i}" for i in range(len(reports))], "score": [r.score for r in reports],
                       "status": ["alert" if r.score >= thr else "clear" for r in reports],
                       "start": [fmt_t(r.start) for r in reports]})
    bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=38).encode(
        x=alt.X("window:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 1]), title="window score"),
        color=alt.Color("status:N", scale=alt.Scale(domain=["alert", "clear"], range=[C["blue"], C["border2"]]),
                        legend=None),
        tooltip=["window", "start", alt.Tooltip("score:Q", format=".2f")])
    rule = alt.Chart(pd.DataFrame({"t": [thr]})).mark_rule(strokeDash=[4, 4], color=C["error"]).encode(y="t:Q")
    return (bars + rule).properties(height=220).configure_view(strokeWidth=0).configure_axis(
        labelFont="DM Mono", titleFont="DM Sans", labelColor=C["text2"], titleColor=C["muted"],
        gridColor=C["border"], domainColor=C["border2"]).configure(background="transparent")


# ----------------------------------------------------------------------------- pages
tab1, tab2 = st.tabs(["Analysis", "Experiment results"])
with tab1:
    if mode == "Single window":
        rng = np.random.default_rng(int(seed) + 7)
        s0 = 1_700_000_000.0
        if kind.startswith("look-alike"):
            ev = ent.benign_events(s0, 3600, rng, hard={kind.split(": ")[1]})
        else:
            ev = ent.benign_events(s0, 3600, rng)
            if kind != "benign":
                aev, _ = ent.attack_events(kind, s0, 3600, rng, stealth=stealth)
                ev += [e for e in aev if e.ts < s0 + 3600]
        ev.sort(key=lambda e: e.ts)
        show_report(rm.analyze_window(ev, s0, s0 + 3600), "single")
    else:
        events, stages, cent = generate_campaign(seed=int(seed) + 11, enterprise=ent)
        reports = rm.analyze_stream(events)
        camps = rm.campaigns(reports)
        top = camps[0] if camps else None
        section("Kill chain", "campaign stitching across windows")
        covered = set(top.tactics) if top else set()
        strip = "".join(
            f'<div class="rm-stage {"on" if t in covered else ""}"><div class="rm-kpi-label">stage {i + 1}</div>'
            f'<div class="rm-stage-name">{pretty(t)}</div><div style="margin-top:4px">'
            f'{badge("observed", "blue") if t in covered else badge("not seen", "neutral")}</div></div>'
            for i, t in enumerate(sorted(TACTIC_ORDER, key=TACTIC_ORDER.get)))
        html(f'<div class="rm-chain">{strip}</div>')
        if top:
            narrative = "".join(
                f'<div class="rm-step"><div class="rm-step-n">{i + 1}</div><div>'
                f'<div style="font-weight:500">{esc(pretty(a.detection.pattern.name))} {badge(pretty(a.tactic), "purple")}</div>'
                f'<div class="rm-mono" style="margin-top:3px">{esc(" · ".join(a.detection.nodes))} · score {a.score:.2f}</div>'
                f'</div></div>' for i, a in enumerate(top.alerts))
            c1, c2 = st.columns([1, 1.4], gap="medium")
            with c1:
                kpi_row([kpi("Campaign score", f"{top.score:.3f}", "noisy-OR over distinct tactics", C["blue"]),
                         kpi("Stages", f"{len(top.tactics)}", "distinct ATT&CK tactics")])
                html(card("Compromised hosts", " ".join(badge(h, "blue") for h in top.hosts), eyebrow="linked actors"))
            with c2:
                html(card("Attack narrative", narrative, badge(f"{len(top.alerts)} alerts", "neutral"), eyebrow="stitched"))
        with st.container(border=True):
            html('<div class="rm-eyebrow">Window timeline</div><div class="rm-muted" style="font-size:.85rem">'
                 'Dashed line: alert threshold</div>')
            st.altair_chart(timeline_chart(reports), use_container_width=True)
        w = st.select_slider("Inspect window", options=list(range(len(reports))), value=len(reports) - 1,
                             format_func=lambda i: f"W{i}")
        show_report(reports[w], f"camp-{w}")

with tab2:
    rp = os.path.join(RESULTS, "report.md")
    jp = os.path.join(RESULTS, "results.json")
    if not os.path.exists(rp):
        html('<div class="rm-note">Run <code>python -m src.evaluation.experiments --out results</code> first.</div>')
    else:
        R = json.load(open(jp)) if os.path.exists(jp) else {}
        section("Evaluation", "synthetic enterprise benchmark")
        html('<div class="rm-note" style="margin-bottom:16px">All numbers come from the synthetic generator: they show '
             'that each mechanism works and matters (ablations), not real-world performance.</div>')
        if R:
            full = R["E1_detection"]["RefineMatch (full)"]
            e4, e5 = R["E4_robustness"], R["E5_streaming"]["refinement_update"]
            kpi_row([kpi("F1", f"{full['f1']:.2f}", "RefineMatch, fixed threshold", C["blue"]),
                     kpi("False-positive rate", f"{full['fpr']:.2f}", "including look-alikes", C["teal"]),
                     kpi("Certificate violations", f"{e4['soundness_violations']}/{e4['soundness_checks']}",
                         "attacks below the bound", C["purple"]),
                     kpi("Streaming speed-up", f"×{e5['speedup']:.0f}", "incremental TCR vs WL")])
            df = pd.DataFrame([{"Detector": n.strip(" -"), "AUC": m["auc"], "Precision": m["precision"],
                                "Recall": m["recall"], "F1": m["f1"], "FPR": m["fpr"], "ms / window": m["ms_per_window"]}
                               for n, m in R["E1_detection"].items()])
            cfg = {k: st.column_config.NumberColumn(format="%.2f") for k in ["AUC", "Precision", "Recall", "F1", "FPR"]}
            cfg["ms / window"] = st.column_config.NumberColumn(format="%.1f")
            with st.container(border=True):
                html('<div class="rm-eyebrow">E1 · detection quality</div>')
                st.dataframe(df, hide_index=True, use_container_width=True, column_config=cfg)
        fig = lambda f: os.path.join(RESULTS, "figures", f)
        cols = st.columns(2, gap="medium")
        for col, f in zip(cols, ["e1_detection.png", "e3_stealth.png"]):
            if os.path.exists(fig(f)):
                with col:
                    st.image(fig(f), use_container_width=True)
        if os.path.exists(fig("e4_robustness.png")):
            st.image(fig("e4_robustness.png"), use_container_width=True)
        with st.expander("Full experiment report (E1–E9)"):
            st.markdown(open(rp).read())
