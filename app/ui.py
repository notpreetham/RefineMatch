"""RefineMatch design system: tokens, global CSS and small HTML components for Streamlit.

Visual language: muted grey-blue canvas, white cards with delicate borders and soft shadows,
DM Serif Display headings, DM Sans interface text, DM Mono for technical metadata, and restrained
blue / teal / purple accents. Every view imports from here so the look stays consistent.
"""

from __future__ import annotations

import html as _html
from typing import Iterable, List, Optional

import streamlit as st

# ----------------------------------------------------------------------------- tokens
C = {
    "bg": "#f0f2f5", "surface": "#ffffff", "surface2": "#f7f8fa",
    "text": "#1e2a38", "text2": "#4a5568", "muted": "#8795a8",
    "border": "#e1e5eb", "border2": "#cdd3db",
    "blue": "#3b72b8", "blue_bg": "#eaf1fb", "blue_mid": "#5a8fd4", "blue_dark": "#2a5490",
    "teal": "#2e7d6f", "teal_bg": "#e6f4f2", "purple": "#7b4fa6", "purple_bg": "#f2ecfa",
    "success": "#2e7d6f", "warning": "#b87c2a", "error": "#c0392b",
    "warning_bg": "#fbf3e6", "error_bg": "#fbeceb",
}
SHADOW_S = "0 1px 3px rgba(30,42,56,0.07), 0 1px 2px rgba(30,42,56,0.04)"
SHADOW_M = "0 4px 12px rgba(30,42,56,0.09), 0 2px 4px rgba(30,42,56,0.05)"
SHADOW_L = "0 12px 32px rgba(30,42,56,0.12), 0 4px 8px rgba(30,42,56,0.06)"

TONES = {  # tone -> (text colour, background)
    "blue": (C["blue"], C["blue_bg"]), "teal": (C["teal"], C["teal_bg"]),
    "purple": (C["purple"], C["purple_bg"]), "success": (C["success"], C["teal_bg"]),
    "warning": (C["warning"], C["warning_bg"]), "error": (C["error"], C["error_bg"]),
    "neutral": (C["text2"], C["surface2"]),
}
RISK_TONE = {"critical": "error", "high": "warning", "medium": "blue", "low": "success"}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Serif+Display:ital@0;1&display=swap');
:root {{
  --rm-bg:{C['bg']}; --rm-surface:{C['surface']}; --rm-surface2:{C['surface2']};
  --rm-text:{C['text']}; --rm-text2:{C['text2']}; --rm-muted:{C['muted']};
  --rm-border:{C['border']}; --rm-border2:{C['border2']};
  --rm-blue:{C['blue']}; --rm-blue-bg:{C['blue_bg']}; --rm-blue-dark:{C['blue_dark']};
  --rm-shadow-s:{SHADOW_S}; --rm-shadow-m:{SHADOW_M}; --rm-shadow-l:{SHADOW_L};
  --rm-serif:'DM Serif Display', Georgia, serif; --rm-sans:'DM Sans', system-ui, sans-serif;
  --rm-mono:'DM Mono', ui-monospace, Menlo, monospace;
}}
html, body, .stApp, button, input, textarea, select, p, label, li {{ font-family: var(--rm-sans); }}
[data-testid="stIconMaterial"], span[class*="material-symbols"], .material-icons {{ font-family: 'Material Symbols Rounded' !important; }}
.stApp {{ background: var(--rm-bg); color: var(--rm-text); }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1280px; }}
h1, h2, h3 {{ font-family: var(--rm-serif) !important; font-weight: 400 !important; color: var(--rm-text); letter-spacing: -0.01em; }}
code, pre, .stCode {{ font-family: var(--rm-mono) !important; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* sidebar */
section[data-testid="stSidebar"] {{ background: var(--rm-surface); border-right: 1px solid var(--rm-border); }}
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p {{ color: var(--rm-text2); }}
section[data-testid="stSidebar"] [data-testid="stCheckbox"] p {{ font-family: var(--rm-sans) !important; font-size: .9rem !important;
  letter-spacing: 0 !important; text-transform: none !important; color: var(--rm-text) !important; }}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
  font-family: var(--rm-mono); font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--rm-muted); }}

/* inputs */
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, .stNumberInput input {{
  background: var(--rm-surface2) !important; border-radius: 10px !important; border-color: var(--rm-border) !important; }}
div[data-baseweb="select"] > div:focus-within, div[data-baseweb="input"] > div:focus-within {{
  border-color: var(--rm-blue) !important; box-shadow: 0 0 0 3px rgba(59,114,184,0.15) !important; }}

/* buttons */
.stButton > button, .stDownloadButton > button {{ border-radius: 10px; font-weight: 500; border: 1px solid var(--rm-border);
  background: var(--rm-surface); color: var(--rm-text); transition: all .15s ease; box-shadow: var(--rm-shadow-s); }}
.stButton > button:hover {{ border-color: var(--rm-blue); color: var(--rm-blue); box-shadow: var(--rm-shadow-m); transform: translateY(-1px); }}
.stButton > button[kind="primary"] {{ background: var(--rm-blue); color: #fff; border-color: var(--rm-blue); }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--rm-border); }}
.stTabs [data-baseweb="tab"] {{ font-weight: 500; color: var(--rm-text2); padding: 10px 14px; }}
.stTabs [aria-selected="true"] {{ color: var(--rm-blue) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--rm-blue); height: 2px; }}

/* expander / dataframe / alerts */
details[data-testid="stExpander"] {{ background: var(--rm-surface); border: 1px solid var(--rm-border) !important;
  border-radius: 16px !important; box-shadow: var(--rm-shadow-s); }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--rm-border); border-radius: 12px; overflow: hidden; }}
[data-testid="stImage"] img {{ border-radius: 12px; border: 1px solid var(--rm-border); background: #fff; }}
.stGraphVizChart {{ background: var(--rm-surface); }}

/* ---------- RefineMatch components ---------- */
.rm-eyebrow {{ font-family: var(--rm-mono); font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--rm-muted); }}
.rm-hero {{ margin: 0 0 1.6rem 0; }}
.rm-hero h1 {{ font-size: clamp(2.1rem, 4vw, 3.1rem); line-height: 1.08; margin: .35rem 0 .6rem 0; }}
.rm-hero h1 em {{ color: var(--rm-blue); font-style: italic; }}
.rm-hero p {{ color: var(--rm-text2); font-size: 1.02rem; max-width: 760px; line-height: 1.6; margin: 0 0 .9rem 0; }}
.rm-card {{ background: var(--rm-surface); border: 1px solid var(--rm-border); border-radius: 16px; box-shadow: var(--rm-shadow-s);
  padding: 18px 20px; transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease; margin-bottom: 14px; }}
.rm-card:hover {{ box-shadow: var(--rm-shadow-m); }}
.rm-card.rm-lift:hover {{ transform: translateY(-2px); }}
.rm-card.rm-selected {{ border-color: var(--rm-blue); box-shadow: 0 0 0 3px rgba(59,114,184,0.10), var(--rm-shadow-m); }}
.rm-card-head {{ display:flex; align-items:center; justify-content:space-between; gap: 10px;
  padding-bottom: 10px; margin-bottom: 12px; border-bottom: 1px solid var(--rm-border); }}
.rm-card-title {{ font-family: var(--rm-serif); font-size: 1.25rem; color: var(--rm-text); }}
.rm-kpi-label {{ font-family: var(--rm-mono); font-size: 0.68rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--rm-muted); }}
.rm-kpi-value {{ font-family: var(--rm-mono); font-size: 1.9rem; font-weight: 500; color: var(--rm-text); margin-top: 6px; line-height: 1.1; }}
.rm-kpi-sub {{ font-size: 0.82rem; color: var(--rm-text2); margin-top: 4px; }}
.rm-badge {{ display:inline-block; font-family: var(--rm-mono); font-size: 0.7rem; letter-spacing: 0.04em; padding: 3px 9px;
  border-radius: 999px; margin: 2px 4px 2px 0; white-space: nowrap; border: 1px solid transparent; }}
.rm-mono {{ font-family: var(--rm-mono); font-size: 0.85rem; color: var(--rm-text2); }}
.rm-muted {{ color: var(--rm-muted); }}
.rm-bar {{ height: 6px; background: var(--rm-surface2); border-radius: 999px; overflow: hidden; border: 1px solid var(--rm-border); }}
.rm-bar > span {{ display:block; height: 100%; border-radius: 999px; }}
.rm-grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 18px; }}
.rm-grid .rm-card {{ margin-bottom: 0; }}
.rm-row {{ display:flex; justify-content:space-between; align-items:baseline; gap: 12px; padding: 7px 0; border-bottom: 1px dashed var(--rm-border); }}
.rm-row:last-child {{ border-bottom: none; }}
.rm-step {{ display:grid; grid-template-columns: 34px 1fr; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--rm-border); }}
.rm-step:last-child {{ border-bottom: none; }}
.rm-step-n {{ width: 28px; height: 28px; border-radius: 50%; background: var(--rm-blue-bg); color: var(--rm-blue);
  font-family: var(--rm-mono); font-size: .8rem; display:flex; align-items:center; justify-content:center; }}
.rm-chain {{ display:flex; flex-wrap: wrap; gap: 8px; align-items:center; margin: 6px 0 4px 0; }}
.rm-stage {{ flex: 1 1 140px; border: 1px solid var(--rm-border); border-radius: 12px; padding: 10px 12px; background: var(--rm-surface2); }}
.rm-stage.on {{ background: var(--rm-blue-bg); border-color: #c9daf2; }}
.rm-stage .rm-kpi-label {{ font-size: .62rem; }}
.rm-stage-name {{ font-weight: 500; margin-top: 3px; color: var(--rm-text); font-size: .92rem; }}
.rm-big {{ font-family: var(--rm-serif); font-size: 3rem; line-height: 1; color: var(--rm-text); }}
.rm-note {{ background: var(--rm-surface2); border: 1px solid var(--rm-border); border-radius: 12px; padding: 12px 14px;
  color: var(--rm-text2); font-size: .9rem; line-height: 1.55; }}
.rm-section {{ margin: 1.6rem 0 .8rem 0; }}
.rm-section h3 {{ font-size: 1.55rem; margin: .2rem 0 0 0; }}
.rm-verified {{ display:flex; align-items:center; gap: 8px; color: var(--rm-success, {C['success']}); font-weight: 500; }}
@media (max-width: 760px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  .rm-kpi-value {{ font-size: 1.5rem; }}
  .rm-big {{ font-size: 2.3rem; }}
  .rm-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
  .rm-kpis .rm-card {{ padding: 14px; }}
}}
</style>
"""


def _clean(s: str) -> str:
    # Streamlit markdown treats indented lines as code blocks: strip indentation from HTML.
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())


def html(s: str):
    st.markdown(_clean(s), unsafe_allow_html=True)


def esc(x) -> str:
    return _html.escape(str(x))


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def badge(text: str, tone: str = "neutral") -> str:
    fg, bg = TONES.get(tone, TONES["neutral"])
    return f'<span class="rm-badge" style="color:{fg};background:{bg};border-color:{fg}22">{esc(text)}</span>'


def risk_badge(level: str) -> str:
    return badge(level.upper(), RISK_TONE.get(level, "neutral"))


def score_color(score: float, threshold: float) -> str:
    if score >= max(threshold, 0.8):
        return C["error"]
    if score >= threshold:
        return C["warning"]
    if score >= 0.35:
        return C["blue"]
    return C["success"]


def bar(value: float, color: str) -> str:
    v = max(0.0, min(1.0, value))
    return f'<div class="rm-bar"><span style="width:{v * 100:.0f}%;background:{color}"></span></div>'


def hero(eyebrow: str, title_html: str, subtitle: str, chips: Iterable[str] = ()):
    html(f"""
    <div class="rm-hero">
    <div class="rm-eyebrow">{esc(eyebrow)}</div>
    <h1>{title_html}</h1>
    <p>{esc(subtitle)}</p>
    <div>{''.join(chips)}</div>
    </div>""")


def section(title: str, eyebrow: str = ""):
    html(f'<div class="rm-section"><div class="rm-eyebrow">{esc(eyebrow)}</div><h3>{esc(title)}</h3></div>')


def kpi(label: str, value: str, sub: str = "", accent: Optional[str] = None) -> str:
    style = f' style="color:{accent}"' if accent else ""
    return (f'<div class="rm-card rm-lift"><div class="rm-kpi-label">{esc(label)}</div>'
            f'<div class="rm-kpi-value"{style}>{esc(value)}</div>'
            f'<div class="rm-kpi-sub">{esc(sub)}</div></div>')


def kpi_row(cards: List[str]):
    html('<div class="rm-grid rm-kpis">' + "".join(cards) + "</div>")


def card(title: str, body_html: str, right_html: str = "", eyebrow: str = "", extra_class: str = "") -> str:
    eb = f'<div class="rm-eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    return (f'<div class="rm-card {extra_class}"><div class="rm-card-head"><div>{eb}'
            f'<div class="rm-card-title">{esc(title)}</div></div><div>{right_html}</div></div>{body_html}</div>')


def row(label: str, value_html: str) -> str:
    return f'<div class="rm-row"><span class="rm-muted">{esc(label)}</span><span class="rm-mono">{value_html}</span></div>'


def graph_dot(nodes, edges, benign_edges=()) -> str:
    """Graphviz DOT in the design-system palette. nodes: (id, role, pattern_node); edges: (src, dst, label)."""
    L = ['digraph G {', 'bgcolor="transparent"; rankdir=LR; pad=0.3; nodesep=0.5; ranksep=0.9;',
         f'node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="{C["border2"]}", penwidth=1.2, '
         f'fontname="DM Sans", fontsize=11, fontcolor="{C["text"]}", margin="0.18,0.1"];',
         f'edge [fontname="DM Mono", fontsize=9, fontcolor="{C["text2"]}", color="{C["blue"]}", penwidth=1.4, arrowsize=0.7];']
    for nid, role, pn in nodes:
        fill = C["purple_bg"] if role in ("external", "saas") else C["blue_bg"]
        edge_col = C["purple"] if role in ("external", "saas") else C["blue"]
        L.append(f'"{nid}" [label=<<b>{esc(nid)}</b><br/><font point-size="9" color="{C["muted"]}">{esc(role)} · {esc(pn)}</font>>, '
                 f'fillcolor="{fill}", color="{edge_col}"];')
    for s, d, lab in edges:
        L.append(f'"{s}" -> "{d}" [label="  {esc(lab)}  "];')
    for s, d, lab in benign_edges:
        L.append(f'"{s}" -> "{d}" [label="  {esc(lab)}  ", style=dashed, color="{C["teal"]}", fontcolor="{C["teal"]}"];')
    L.append("}")
    return "\n".join(L)
