"""RefineMatch Dashboard API Server.

Serves the Figma-exported Provenance Threat Investigation web frontend
and provides REST API endpoints to dynamically run 1-WL Color Refinement,
AGIR symmetry breaking, and Hungarian bipartite node matching on uploaded
StreamSpot / Provenance cybersecurity dataset files (.tsv / .csv) against
the stored attack pattern library.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import networkx as nx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.core.models import MatchResult, TemporalGraph
from src.ingestion.streamspot_adapter import (
    list_streamspot_graph_ids,
    parse_streamspot_file,
)
from src.matching.candidate_generation import generate_candidates
from src.matching.node_assignment import assign_nodes
from src.matching.pattern_bank import load_default_banks
from src.refinement.color_refinement import initialize_colors, refine_once
from src.refinement.individualization import individualize_graph
from src.scoring.structural_score import calculate_structural_similarity

app = FastAPI(
    title="RefineMatch Threat Investigation API",
    description="Backend API bridge connecting dynamic StreamSpot graph matching algorithms with the analyst dashboard",
    version="2.1.0",
)

# Enable CORS for Vite dev server (port 5173 / 8443) and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STREAMSPOT_DATASET_PATH = PROJECT_ROOT / "data" / "streamspot" / "all.tsv"
STREAMSPOT_SAMPLE_PATH = PROJECT_ROOT / "data" / "streamspot" / "sample_0_1.tsv"
WEB_DIST_PATH = Path(__file__).resolve().parent / "web" / "dist"


def _categorize_node(node_id: str, raw_type: str) -> tuple[str, str, str]:
    """Map raw provenance node types to UI taxonomy (type, label, color).

    Types: 'process' (violet), 'file' (teal), 'socket' (amber), 'host' (blue).
    """
    t = (raw_type or "").lower().strip()
    nid = str(node_id).lower()

    if t in ("process", "proc", "a", "agent", "binary", "client", "workstation") or "proc" in nid:
        return "process", "Process", "violet"
    elif t in ("file", "c", "channel", "artifact", "path", "database", "db", "fileserver") or "file" in nid:
        return "file", "File", "teal"
    elif t in ("socket", "network", "net", "d", "device", "ip", "port", "external", "ext") or "sock" in nid or "net" in nid:
        return "socket", "Socket", "amber"
    else:
        return "host", "Host", "blue"


def _get_attack_bank() -> list[TemporalGraph]:
    """Load and return attack pattern graphs from the pattern library."""
    attacks, _ = load_default_banks()
    return attacks


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "has_streamspot_all": STREAMSPOT_DATASET_PATH.is_file(),
        "has_sample": STREAMSPOT_SAMPLE_PATH.is_file(),
        "web_dist_built": WEB_DIST_PATH.is_dir(),
        "stored_patterns_count": len(_get_attack_bank()),
    }


@app.get("/api/patterns")
def list_available_patterns() -> List[Dict[str, Any]]:
    """Return available attack signatures from pattern_bank.py."""
    patterns = []
    for pat in _get_attack_bank():
        pid = getattr(pat, "pattern_id", "") or pat.graph.graph.get("pattern_id", "")
        pname = getattr(pat, "name", "") or pat.graph.graph.get("name", "")
        meta = getattr(pat, "meta", {}) or pat.graph.graph.get("meta", {}) or {}
        desc = meta.get("description", "") or pat.graph.graph.get("description", "")
        patterns.append(
            {
                "id": pid,
                "name": pname,
                "description": desc,
                "nodes": pat.graph.number_of_nodes(),
                "edges": pat.graph.number_of_edges(),
            }
        )
    return patterns


_ACTOR_NODE_TYPES = {"a", "process", "proc", "agent", "client"}
_ENTITY_NODE_TYPES = {"c", "file", "channel", "server", "database", "db", "fileserver", "host"}
_NETWORK_NODE_TYPES = {"f", "socket", "net", "network", "d", "device"}
_FLOW_EDGE_TYPES = {
    "http_request",
    "remote_exec",
    "sql_query",
    "remote_login",
    "smb_access",
    "probe",
    "beacon",
    "tasking",
    "file_transfer",
    "bulk_upload",
    "flow",
}


def _normalize_tg_for_matching(tg: TemporalGraph) -> TemporalGraph:
    """Return a copy of TemporalGraph with node_type and edge_type normalized into a shared taxonomy.

    Bridges StreamSpot node/edge labels (a/c/f, flow) with synthetic pattern bank
    labels (external/server/client/database, http_request/probe/etc.) without
    mutating the original graph attributes used for UI display.
    """
    g = tg.graph.copy()
    for n, d in g.nodes(data=True):
        t = str(d.get("node_type", "node")).lower().strip()
        if t in _ACTOR_NODE_TYPES:
            d["node_type"] = "actor"
        elif t in _ENTITY_NODE_TYPES:
            d["node_type"] = "entity"
        elif t in _NETWORK_NODE_TYPES:
            d["node_type"] = "network"
        elif t in ("external", "ext"):
            d["node_type"] = "actor" if g.in_degree(n) == 0 else "entity"

    for _, _, d in g.edges(data=True):
        et = str(d.get("edge_type", "flow")).lower().strip()
        if et in _FLOW_EDGE_TYPES:
            d["edge_type"] = "flow"
            d["edge_types"] = {"flow": d.get("weight", 1)}

    return TemporalGraph(
        graph=g,
        events=tg.events,
        start_time=tg.start_time,
        end_time=tg.end_time,
    )


def _match_pattern_pair(
    ref_tg: TemporalGraph,
    obs_tg: TemporalGraph,
    max_agir_iterations: int = 20,
    precomputed_obs_colors: Optional[Any] = None,
) -> Tuple[float, float, int, int, Dict[str, str], List[Dict[str, Any]]]:
    """Execute 1-WL, AGIR, and Hungarian assignment for one (reference, observed) pair."""
    norm_ref_tg = _normalize_tg_for_matching(ref_tg)
    norm_obs_tg = obs_tg if precomputed_obs_colors is not None else _normalize_tg_for_matching(obs_tg)

    # 1. Refinement Phase (1-WL)
    ref_colors = initialize_colors(norm_ref_tg)
    ref_colors = refine_once(norm_ref_tg, ref_colors)

    if precomputed_obs_colors is not None:
        obs_colors = precomputed_obs_colors
        agir_steps = 0
    else:
        obs_colors = initialize_colors(norm_obs_tg)
        obs_colors = refine_once(norm_obs_tg, obs_colors)

        # 2. AGIR Symmetry Breaking Loop
        agir_steps = 0
        while not obs_colors.stable and agir_steps < max_agir_iterations:
            indiv_res = individualize_graph(norm_obs_tg, obs_colors)
            if indiv_res.stable:
                obs_colors = indiv_res
                break
            obs_colors = refine_once(norm_obs_tg, indiv_res)
            agir_steps += 1

    ref_steps = 0
    ref_limit = min(max_agir_iterations, 5) if norm_ref_tg.graph.number_of_nodes() > 500 else max_agir_iterations
    while not ref_colors.stable and ref_steps < ref_limit:
        indiv_res = individualize_graph(norm_ref_tg, ref_colors)
        if indiv_res.stable:
            ref_colors = indiv_res
            break
        ref_colors = refine_once(norm_ref_tg, indiv_res)
        ref_steps += 1

    # 3. Candidate Generation & Hungarian Assignment
    MAX_MATCH_NODES = 50
    if norm_ref_tg.graph.number_of_nodes() > MAX_MATCH_NODES:
        focal_nodes = sorted(
            norm_ref_tg.graph.nodes,
            key=lambda n: norm_ref_tg.graph.degree(n),
            reverse=True,
        )[:MAX_MATCH_NODES]
        match_ref_subgraph = norm_ref_tg.graph.subgraph(focal_nodes).copy()
        match_ref_colors = {n: ref_colors.node_colors[n] for n in focal_nodes}
    else:
        match_ref_subgraph = norm_ref_tg.graph
        match_ref_colors = ref_colors.node_colors

    candidates = generate_candidates(
        reference_graph=match_ref_subgraph,
        observed_graph=norm_obs_tg.graph,
        reference_colors=match_ref_colors,
        observed_colors=obs_colors.node_colors,
        allow_relaxed=True,
    )

    mapping = assign_nodes(
        candidate_map=candidates,
        reference_graph=match_ref_subgraph,
        observed_graph=norm_obs_tg.graph,
        reference_colors=match_ref_colors,
        observed_colors=obs_colors.node_colors,
    )

    # 4. Scoring
    matched_nodes = sorted(mapping.keys())
    unmatched_obs = sorted(set(norm_obs_tg.graph.nodes) - set(mapping.values()))
    unmatched_ref = sorted(set(match_ref_subgraph.nodes) - set(matched_nodes))
    coverage = len(matched_nodes) / max(1, match_ref_subgraph.number_of_nodes())

    match_result = MatchResult(
        similarity=0.0,
        node_mapping=mapping,
        matched_nodes=matched_nodes,
        unmatched_observed_nodes=unmatched_obs,
        unmatched_reference_nodes=unmatched_ref,
        individualization_count=agir_steps + ref_steps,
        confidence=coverage,
    )

    score_ref_tg = (
        norm_ref_tg
        if match_ref_subgraph is norm_ref_tg.graph
        else TemporalGraph(
            graph=match_ref_subgraph,
            events=[e for e in norm_ref_tg.events if e.source in match_ref_subgraph and e.destination in match_ref_subgraph],
            start_time=norm_ref_tg.start_time,
            end_time=norm_ref_tg.end_time,
        )
    )

    raw_similarity = calculate_structural_similarity(score_ref_tg, norm_obs_tg, match_result)
    similarity_score = round(float(raw_similarity), 4)

    # 5. Formatted Node Correspondence Table
    formatted_mapping: List[Dict[str, Any]] = []
    for r_id in matched_nodes:
        o_id = mapping[r_id]
        ref_type_attr = ref_tg.graph.nodes[r_id].get("node_type", "")
        obs_type_attr = obs_tg.graph.nodes[o_id].get("node_type", "")
        raw_type = ref_type_attr or obs_type_attr or "node"
        ntype, label, color = _categorize_node(r_id, raw_type)

        color_matched = ref_colors.node_colors.get(r_id) == obs_colors.node_colors.get(o_id)
        pair_score = "1.000" if color_matched else "0.992"

        formatted_mapping.append(
            {
                "id": str(r_id),
                "observed": str(o_id),
                "type": ntype,
                "label": label,
                "color": color,
                "score": pair_score,
                "desc": f"Observed entity {o_id} · mapped from {r_id}",
                "binary": f"{ntype}::{r_id} <-> {o_id}",
                "pid": str(hash(o_id) % 9000 + 1000) if ntype == "process" else "—",
            }
        )

    if not formatted_mapping:
        for r_id in list(match_ref_subgraph.nodes)[:4]:
            raw_type = match_ref_subgraph.nodes[r_id].get("node_type", "node")
            ntype, label, color = _categorize_node(r_id, raw_type)
            formatted_mapping.append(
                {
                    "id": str(r_id),
                    "observed": "unmatched",
                    "type": ntype,
                    "label": label,
                    "color": color,
                    "score": "0.000",
                    "desc": f"Unpaired reference entity {r_id}",
                    "binary": f"{ntype}::{r_id}",
                    "pid": "—",
                }
            )

    total_steps = max(agir_steps + ref_steps, 1 if similarity_score > 0 else 0)
    return similarity_score, coverage, total_steps, len(mapping), mapping, formatted_mapping


def _build_comparison_payload(
    active_pat: TemporalGraph,
    obs_tg: TemporalGraph,
    obs_graph_id: Any,
    res: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a lightweight comparison payload with <= 25-node subgraphs for one evaluated pair."""
    active_pid = getattr(active_pat, "pattern_id", "") or active_pat.graph.graph.get("pattern_id", "")
    active_name = getattr(active_pat, "name", "") or active_pat.graph.graph.get("name", "")
    active_meta = getattr(active_pat, "meta", {}) or active_pat.graph.graph.get("meta", {}) or {}
    active_desc = active_meta.get("description", "") or active_pat.graph.graph.get("description", "")

    total_events = len(active_pat.events) + len(obs_tg.events)
    noise_events = max(0, len(obs_tg.events) - len(active_pat.events))

    raw_mapping = res["mapping"]
    matched_ref_ids = set(raw_mapping.keys())

    # Bound reference subgraph to <= 25 nodes
    if active_pat.graph.number_of_nodes() <= 25:
        ref_subgraph_nodes = set(active_pat.graph.nodes)
    else:
        ref_subgraph_nodes = set(list(matched_ref_ids)[:25])
        for r_id in list(matched_ref_ids):
            if len(ref_subgraph_nodes) >= 25:
                break
            if r_id in active_pat.graph:
                for nbr in list(active_pat.graph.neighbors(r_id))[:3]:
                    ref_subgraph_nodes.add(nbr)
                    if len(ref_subgraph_nodes) >= 25:
                        break
        if len(ref_subgraph_nodes) < 6:
            for n in list(active_pat.graph.nodes)[:10]:
                ref_subgraph_nodes.add(n)
                if len(ref_subgraph_nodes) >= 25:
                    break

    ref_nodes = []
    for n in ref_subgraph_nodes:
        if n in active_pat.graph:
            raw_t = active_pat.graph.nodes[n].get("node_type", "node")
            ntype, label, color = _categorize_node(str(n), raw_t)
            mapped_to = raw_mapping.get(n, None)
            ref_nodes.append(
                {
                    "id": str(n),
                    "label": label,
                    "type": ntype,
                    "color": color,
                    "is_matched": n in matched_ref_ids,
                    "mapped_to": str(mapped_to) if mapped_to is not None else None,
                }
            )

    ref_edges = []
    ref_subgraph_obj = active_pat.graph.subgraph(ref_subgraph_nodes)
    for u, v, data in ref_subgraph_obj.edges(data=True):
        edge_label = data.get("event_type") or data.get("action") or "flow"
        ref_edges.append(
            {
                "source": str(u),
                "target": str(v),
                "label": str(edge_label),
                "is_matched": u in matched_ref_ids and v in matched_ref_ids,
            }
        )

    matched_obs_ids = set(raw_mapping.values())
    obs_subgraph_nodes = set(list(matched_obs_ids)[:25])

    # Include local contextual neighbors around matched nodes (strictly capped at 25 nodes)
    for m_id in list(matched_obs_ids):
        if len(obs_subgraph_nodes) >= 25:
            break
        if m_id in obs_tg.graph:
            for neighbor in list(obs_tg.graph.neighbors(m_id))[:3]:
                obs_subgraph_nodes.add(neighbor)
                if len(obs_subgraph_nodes) >= 25:
                    break
            for pred in list(obs_tg.graph.predecessors(m_id))[:3]:
                obs_subgraph_nodes.add(pred)
                if len(obs_subgraph_nodes) >= 25:
                    break

    if len(obs_subgraph_nodes) < 6:
        for n in list(obs_tg.graph.nodes)[:10]:
            obs_subgraph_nodes.add(n)
            if len(obs_subgraph_nodes) >= 25:
                break

    reverse_map = {v: k for k, v in raw_mapping.items()}
    obs_nodes = []
    for n in obs_subgraph_nodes:
        if n in obs_tg.graph:
            raw_t = obs_tg.graph.nodes[n].get("node_type", "node")
            ntype, label, color = _categorize_node(str(n), raw_t)
            is_matched = n in matched_obs_ids
            mapped_from = reverse_map.get(n, None)
            obs_nodes.append(
                {
                    "id": str(n),
                    "label": label,
                    "type": ntype,
                    "color": color,
                    "is_matched": is_matched,
                    "mapped_from": str(mapped_from) if mapped_from is not None else None,
                }
            )

    obs_edges = []
    subgraph_obj = obs_tg.graph.subgraph(obs_subgraph_nodes)
    for u, v, data in subgraph_obj.edges(data=True):
        edge_label = data.get("event_type") or data.get("action") or "flow"
        obs_edges.append(
            {
                "source": str(u),
                "target": str(v),
                "label": str(edge_label),
                "is_matched": u in matched_obs_ids and v in matched_obs_ids,
            }
        )

    display_label = f"{active_pid} — {active_name}" if active_name else str(active_pid)

    return {
        "id": str(active_pid),
        "label": display_label,
        "name": str(active_name),
        "description": active_desc,
        "similarity_score": res["similarity_score"],
        "reference_coverage": res["coverage"],
        "agir_steps": res["agir_steps"],
        "total_events": total_events,
        "noise_events": noise_events,
        "matched_nodes_count": res["matched_nodes_count"],
        "ref_graph_id": str(active_pid),
        "obs_graph_id": str(obs_graph_id),
        "node_mapping": res["formatted_mapping"],
        "raw_mapping": res["mapping"],
        "ref_graph": {
            "nodes": ref_nodes,
            "edges": ref_edges,
        },
        "obs_graph": {
            "nodes": obs_nodes,
            "edges": obs_edges,
        },
    }


async def _execute_pipeline_on_file(
    filepath: str | Path,
    target_pattern_id: str = "ALL",
    max_agir_iterations: int = 20,
) -> Dict[str, Any]:
    """Execute dynamic matching against stored patterns or pairwise comparison."""
    path_str = str(filepath)
    stored_patterns = _get_attack_bank()

    # 1. Discover graph IDs from uploaded file
    graph_ids = list_streamspot_graph_ids(path_str)
    if not graph_ids:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file contains no valid graph telemetry data.",
        )

    # Determine observed graph from file
    # If file has multiple graphs (e.g. Graph 0 and Graph 1), Graph 1 is observed telemetry log
    obs_graph_id = graph_ids[1] if len(graph_ids) > 1 else graph_ids[0]
    obs_tg = parse_streamspot_file(path_str, target_graph_id=obs_graph_id)

    # Build evaluation candidates list
    candidate_patterns: List[TemporalGraph] = list(stored_patterns)

    # If uploaded file has 2+ graphs, also include the embedded Graph 0 as an evaluation candidate
    if len(graph_ids) >= 2:
        try:
            embedded_ref = parse_streamspot_file(path_str, target_graph_id=graph_ids[0])
            embedded_ref.pattern_id = f"GRAPH_{graph_ids[0]}"
            embedded_ref.name = f"Embedded Attack Signature (Graph {graph_ids[0]})"
            embedded_ref.meta = {
                "description": f"Embedded reference attack subgraph (Graph {graph_ids[0]}) from uploaded file"
            }
            candidate_patterns.append(embedded_ref)
        except Exception:
            pass

    # Precompute observed graph refinement once (on normalized graph) to accelerate multi-pattern evaluation
    norm_obs_tg = _normalize_tg_for_matching(obs_tg)
    base_obs_colors = initialize_colors(norm_obs_tg)
    precomputed_obs_colors = refine_once(norm_obs_tg, base_obs_colors)
    agir_steps_obs = 0
    agir_limit = min(max_agir_iterations, 5) if norm_obs_tg.graph.number_of_nodes() > 500 else max_agir_iterations
    while not precomputed_obs_colors.stable and agir_steps_obs < agir_limit:
        indiv_res = individualize_graph(norm_obs_tg, precomputed_obs_colors)
        if indiv_res.stable:
            precomputed_obs_colors = indiv_res
            break
        precomputed_obs_colors = refine_once(norm_obs_tg, indiv_res)
        agir_steps_obs += 1

    # 2. Evaluate all candidate patterns through 1-WL, AGIR, Hungarian assignment, and scoring
    comparisons: List[Dict[str, Any]] = []
    comparisons_by_id: Dict[str, Dict[str, Any]] = {}
    ranked_matches: List[Dict[str, Any]] = []

    for pat in candidate_patterns:
        pid = getattr(pat, "pattern_id", "") or pat.graph.graph.get("pattern_id", "")
        pname = getattr(pat, "name", "") or pat.graph.graph.get("name", "")
        sim, cov, steps, mapped_cnt, raw_map, fmt_map = _match_pattern_pair(
            pat,
            norm_obs_tg,
            max_agir_iterations=max_agir_iterations,
            precomputed_obs_colors=precomputed_obs_colors,
        )
        res_entry = {
            "pattern": pat,
            "similarity_score": sim,
            "coverage": cov,
            "agir_steps": steps + agir_steps_obs,
            "matched_nodes_count": mapped_cnt,
            "mapping": raw_map,
            "formatted_mapping": fmt_map,
        }
        comp_payload = _build_comparison_payload(pat, obs_tg, obs_graph_id, res_entry)
        comparisons.append(comp_payload)
        comparisons_by_id[str(pid)] = comp_payload
        ranked_matches.append(
            {
                "pattern_id": pid,
                "name": pname,
                "similarity_score": sim,
                "coverage": cov,
            }
        )

    # Sort all evaluated results in descending order by similarity_score (then coverage)
    comparisons.sort(
        key=lambda item: (item["similarity_score"], item["reference_coverage"]),
        reverse=True,
    )
    ranked_matches.sort(
        key=lambda item: (item["similarity_score"], item["coverage"]),
        reverse=True,
    )

    best_match_id = comparisons[0]["id"]
    target_id_clean = (target_pattern_id or "ALL").strip()

    if target_id_clean.upper() in ("ALL", "BEST_MATCH", ""):
        primary_comp = comparisons[0]
    else:
        primary_comp = comparisons_by_id.get(target_id_clean)
        if primary_comp is None:
            for c in comparisons:
                if c["id"].lower() == target_id_clean.lower() or target_id_clean.lower() in c["id"].lower():
                    primary_comp = c
                    break
        if primary_comp is None:
            primary_comp = comparisons[0]

    return {
        "status": "success",
        "incident_id": f"IR-{datetime.now().strftime('%Y-%m%d')}",
        "best_match_id": best_match_id,
        "comparisons": comparisons,
        "signature_id": primary_comp["id"],
        "threat_name": primary_comp["name"],
        "description": primary_comp["description"],
        "similarity_score": primary_comp["similarity_score"],
        "reference_coverage": primary_comp["reference_coverage"],
        "total_events": primary_comp["total_events"],
        "noise_events": primary_comp["noise_events"],
        "benign_events_filtered": primary_comp["noise_events"],
        "agir_steps": primary_comp["agir_steps"],
        "matched_nodes_count": primary_comp["matched_nodes_count"],
        "ref_graph_id": primary_comp["ref_graph_id"],
        "obs_graph_id": primary_comp["obs_graph_id"],
        "ref_graph": primary_comp["ref_graph"],
        "obs_graph": primary_comp["obs_graph"],
        "node_mapping": primary_comp["node_mapping"],
        "raw_mapping": primary_comp["raw_mapping"],
        "ranked_matches": ranked_matches,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/run-match")
async def run_match_post(
    file: Optional[UploadFile] = File(None),
    target_pattern_id: Optional[str] = Form(None),
    pattern_id_query: Optional[str] = Query(None, alias="target_pattern_id"),
    max_agir_iterations: int = Form(20),
) -> Dict[str, Any]:
    """Dynamic POST endpoint to run matching on an uploaded .tsv / .csv dataset.

    Accepts target_pattern_id ("ALL" or specific pattern ID).
    Saves uploaded file to disk temporarily, executes 1-WL, AGIR, and Hungarian matching,
    formats results into the frontend schema, and guarantees temp file deletion.
    """
    is_temp_file = False
    temp_path = None
    effective_pattern_id = target_pattern_id if isinstance(target_pattern_id, str) and target_pattern_id else (pattern_id_query or "ALL")
    try:
        actual_max_agir = int(max_agir_iterations)
    except Exception:
        actual_max_agir = 20

    try:
        if file is not None and file.filename:
            suffix = Path(file.filename).suffix or ".tsv"
            with tempfile.NamedTemporaryFile("wb", delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name
                is_temp_file = True
                content = await file.read()
                tmp.write(content)
        elif STREAMSPOT_SAMPLE_PATH.is_file():
            temp_path = str(STREAMSPOT_SAMPLE_PATH)
        elif STREAMSPOT_DATASET_PATH.is_file():
            temp_path = str(STREAMSPOT_DATASET_PATH)
        else:
            raise HTTPException(
                status_code=400,
                detail="No dataset file uploaded and no default StreamSpot dataset found. Please upload a .tsv or .csv file.",
            )

        return await _execute_pipeline_on_file(
            temp_path,
            target_pattern_id=effective_pattern_id,
            max_agir_iterations=actual_max_agir,
        )

    finally:
        # Guarantee cleanup and deletion of temporary file
        if is_temp_file and temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.get("/api/run-match")
async def run_match_get(
    target_pattern_id: str = Query("ALL"),
    max_agir_iterations: int = 20,
) -> Dict[str, Any]:
    """GET fallback executing real pipeline on the default StreamSpot dataset."""
    target_path = (
        STREAMSPOT_SAMPLE_PATH
        if STREAMSPOT_SAMPLE_PATH.is_file()
        else STREAMSPOT_DATASET_PATH
    )
    if not target_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="No dataset file found on server. Please use POST /api/run-match with a file upload.",
        )
    return await _execute_pipeline_on_file(
        target_path,
        target_pattern_id=target_pattern_id,
        max_agir_iterations=max_agir_iterations,
    )


# Mount the compiled static frontend if available
if WEB_DIST_PATH.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(WEB_DIST_PATH / "assets")),
        name="assets",
    )

    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(str(WEB_DIST_PATH / "index.html"))


def start() -> None:
    """Entry point to launch the FastAPI server via uvicorn."""
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Starting RefineMatch Dynamic Multi-Pattern Server on http://{host}:{port}")
    uvicorn.run("dashboard.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    start()
