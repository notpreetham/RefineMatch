"""RefineMatch analyst dashboard.

    streamlit run app/dashboard.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
import streamlit as st

from src.explanation.certificate import build_certificate, verify_certificate
from src.ingestion.synthetic import (ATTACK_KINDS, HARD_NEGATIVE_KINDS, SyntheticEnterprise, generate_benchmark,
                                     generate_campaign)
from src.matching.matcher import PatternMatcher
from src.pipeline import RefineMatch
from src.robustness.certify import certify

st.set_page_config(page_title="RefineMatch", layout="wide")
st.title("RefineMatch")
st.caption("Training-free, explainable-by-construction, certifiably robust detection of multi-stage attacks "
           "with temporal colour refinement")

with st.sidebar:
    seed = st.number_input("seed", 0, 10_000, 0)
    mode = st.radio("scenario", ["single window", "multi-stage campaign"])
    kind = st.selectbox("window content", ["benign"] + ATTACK_KINDS + [f"look-alike: {k}" for k in HARD_NEGATIVE_KINDS])
    stealth = st.slider("attack stealth", 0.0, 1.0, 0.0, 0.05)
    thr = st.slider("alert threshold", 0.1, 1.0, 0.65, 0.05)
    use_benign = st.checkbox("benign contrast", True)
    use_temporal = st.checkbox("temporal order", True)
    use_novelty = st.checkbox("novelty term", True)


@st.cache_resource(show_spinner="Learning benign colour profile...")
def engine(seed, use_benign, use_temporal, use_novelty, thr):
    ent = SyntheticEnterprise(seed=int(seed))
    rm = RefineMatch(ent.roles, threshold=thr, use_benign=use_benign, use_temporal=use_temporal, use_novelty=use_novelty)
    rm.fit_baseline([w.events for w in generate_benchmark(15, 0, 0, seed=int(seed) + 100, enterprise=ent)])
    return ent, rm


ent, rm = engine(seed, use_benign, use_temporal, use_novelty, thr)


def dot_for(det, index):
    lines = ["digraph G { rankdir=LR; node [shape=box, style=rounded, fontname=Helvetica];"]
    for p, v in det.embedding.mapping.items():
        lines.append(f'"{v}" [label="{v}\\n{index.roles.get(v, "?")}\\n({p})", color="#b5384b", penwidth=2];')
    for ev in sorted(det.embedding.evidence, key=lambda e: e.order):
        lines.append(f'"{ev.source}" -> "{ev.destination}" [label="{ev.order}: {ev.event_type}", color="#b5384b"];')
    if det.benign_embedding is not None:
        for ev in det.benign_embedding.evidence:
            lines.append(f'"{ev.source}" -> "{ev.destination}" [label="benign: {ev.event_type}", style=dashed, color="#3a9e5f"];')
    lines.append("}")
    return "\n".join(lines)


def show_report(rep):
    c1, c2, c3 = st.columns(3)
    c1.metric("window score", f"{rep.score:.2f}")
    c2.metric("alerts", len(rep.alerts))
    c3.metric("events / hosts", f"{len(rep.graph.events)} / {rep.graph.graph.number_of_nodes()}")
    rows = [{"template": d.pattern.name, "tactic": d.pattern.tactic, "hosts": ", ".join(d.nodes),
             "contrastive": round(d.score.contrastive_score, 3), "attack_sim": round(d.score.attack_similarity, 3),
             "benign_sim": round(d.score.benign_similarity, 3), "closest benign": d.score.best_benign or "-",
             "novelty": round(d.score.frequency_score, 3), "risk": d.score.risk_level} for d in rep.detections]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if not rep.detections:
        return
    pick = st.selectbox("inspect detection", [d.pattern.name for d in rep.detections])
    det = next(d for d in rep.detections if d.pattern.name == pick)
    m = PatternMatcher(rep.index)
    rc = certify(det, m, rm.scorer, thr)
    cert = build_certificate(det, m, rm.scorer, rc)
    ok, problems = verify_certificate(cert, rep.index, det.pattern)
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Evidence subgraph")
        st.graphviz_chart(dot_for(det, rep.index))
        st.subheader("Robustness certificate")
        st.write(rc.summary())
        st.write("**Cheapest evasion found (deletion):**", rc.deletion_plan[:4] or "-")
        st.write("**Benign-mimicry analysis:**", rc.insertion_plan[:3])
    with right:
        st.subheader("Detection certificate")
        st.code(cert.to_text())
        if ok:
            st.success("certificate independently verified against raw events")
        else:
            st.error(problems)
        with st.expander("refinement / individualization trace"):
            st.json(cert.refinement_trace)


tab1, tab2 = st.tabs(["Analysis", "Experiment results"])
with tab1:
    if mode == "single window":
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
        show_report(rm.analyze_window(ev, s0, s0 + 3600))
    else:
        events, stages, cent = generate_campaign(seed=int(seed) + 11, enterprise=ent)
        reports = rm.analyze_stream(events)
        st.subheader("Window timeline")
        st.bar_chart(pd.DataFrame({"window": list(range(len(reports))), "score": [r.score for r in reports]}).set_index("window"))
        for c in rm.campaigns(reports):
            st.markdown(f"**Campaign score {c.score:.3f}** -- {' → '.join(c.tactics)} -- hosts {', '.join(c.hosts)}")
            for line in c.narrative:
                st.write("• " + line)
        w = st.slider("inspect window", 0, len(reports) - 1, len(reports) - 1)
        show_report(reports[w])

with tab2:
    root = os.path.join(os.path.dirname(__file__), "..", "results")
    rp = os.path.join(root, "report.md")
    if os.path.exists(rp):
        for f in ["e1_detection.png", "e3_stealth.png", "e4_robustness.png"]:
            fp = os.path.join(root, "figures", f)
            if os.path.exists(fp):
                st.image(fp)
        st.markdown(open(rp).read())
    else:
        st.info("Run `python -m src.evaluation.experiments --out results` first.")
