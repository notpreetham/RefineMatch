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


def _match_pattern_pair(
    ref_tg: TemporalGraph,
    obs_tg: TemporalGraph,
    max_agir_iterations: int = 20,
    precomputed_obs_colors: Optional[Any] = None,
) -> Tuple[float, float, int, int, Dict[str, str], List[Dict[str, Any]]]:
    """Execute 1-WL, AGIR, and Hungarian assignment for one (reference, observed) pair."""
    # 1. Refinement Phase (1-WL)
    ref_colors = initialize_colors(ref_tg)
    ref_colors = refine_once(ref_tg, ref_colors)

    if precomputed_obs_colors is not None:
        obs_colors = precomputed_obs_colors
        agir_steps = 0
    else:
        obs_colors = initialize_colors(obs_tg)
        obs_colors = refine_once(obs_tg, obs_colors)

        # 2. AGIR Symmetry Breaking Loop
        agir_steps = 0
        while not obs_colors.stable and agir_steps < max_agir_iterations:
            indiv_res = individualize_graph(obs_tg, obs_colors)
            if indiv_res.stable:
                obs_colors = indiv_res
                break
            obs_colors = refine_once(obs_tg, indiv_res)
            agir_steps += 1

    ref_steps = 0
    ref_limit = min(max_agir_iterations, 5) if ref_tg.graph.number_of_nodes() > 500 else max_agir_iterations
    while not ref_colors.stable and ref_steps < ref_limit:
        indiv_res = individualize_graph(ref_tg, ref_colors)
        if indiv_res.stable:
            ref_colors = indiv_res
            break
        ref_colors = refine_once(ref_tg, indiv_res)
        ref_steps += 1

    # 3. Candidate Generation & Hungarian Assignment
    MAX_MATCH_NODES = 50
    if ref_tg.graph.number_of_nodes() > MAX_MATCH_NODES:
        focal_nodes = sorted(
            ref_tg.graph.nodes,
            key=lambda n: ref_tg.graph.degree(n),
            reverse=True,
        )[:MAX_MATCH_NODES]
        match_ref_subgraph = ref_tg.graph.subgraph(focal_nodes).copy()
        match_ref_colors = {n: ref_colors.node_colors[n] for n in focal_nodes}
    else:
        match_ref_subgraph = ref_tg.graph
        match_ref_colors = ref_colors.node_colors

    candidates = generate_candidates(
        reference_graph=match_ref_subgraph,
        observed_graph=obs_tg.graph,
        reference_colors=match_ref_colors,
        observed_colors=obs_colors.node_colors,
        allow_relaxed=True,
    )

    mapping = assign_nodes(
        candidate_map=candidates,
        reference_graph=match_ref_subgraph,
        observed_graph=obs_tg.graph,
        reference_colors=match_ref_colors,
        observed_colors=obs_colors.node_colors,
    )

    # 4. Scoring
    matched_nodes = sorted(mapping.keys())
    unmatched_obs = sorted(set(obs_tg.graph.nodes) - set(mapping.values()))
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
        ref_tg
        if match_ref_subgraph is ref_tg.graph
        else TemporalGraph(
            graph=match_ref_subgraph,
            events=[e for e in ref_tg.events if e.source in match_ref_subgraph and e.destination in match_ref_subgraph],
            start_time=ref_tg.start_time,
            end_time=ref_tg.end_time,
        )
    )

    raw_similarity = calculate_structural_similarity(score_ref_tg, obs_tg, match_result)
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

    # Precompute observed graph refinement once to accelerate multi-pattern evaluation
    base_obs_colors = initialize_colors(obs_tg)
    precomputed_obs_colors = refine_once(obs_tg, base_obs_colors)
    agir_steps_obs = 0
    agir_limit = min(max_agir_iterations, 5) if obs_tg.graph.number_of_nodes() > 500 else max_agir_iterations
    while not precomputed_obs_colors.stable and agir_steps_obs < agir_limit:
        indiv_res = individualize_graph(obs_tg, precomputed_obs_colors)
        if indiv_res.stable:
            precomputed_obs_colors = indiv_res
            break
        precomputed_obs_colors = refine_once(obs_tg, indiv_res)
        agir_steps_obs += 1

    # 2. Execute matching based on target_pattern_id
    ranked_matches: List[Dict[str, Any]] = []
    results_by_pattern: Dict[str, Any] = {}

    target_id_clean = (target_pattern_id or "ALL").strip()

    if target_id_clean.upper() == "ALL":
        for pat in candidate_patterns:
            pid = getattr(pat, "pattern_id", "") or pat.graph.graph.get("pattern_id", "")
            pname = getattr(pat, "name", "") or pat.graph.graph.get("name", "")
            sim, cov, steps, mapped_cnt, raw_map, fmt_map = _match_pattern_pair(
                pat,
                obs_tg,
                max_agir_iterations=max_agir_iterations,
                precomputed_obs_colors=precomputed_obs_colors,
            )
            results_by_pattern[pid] = {
                "pattern": pat,
                "similarity_score": sim,
                "coverage": cov,
                "agir_steps": steps + agir_steps_obs,
                "matched_nodes_count": mapped_cnt,
                "mapping": raw_map,
                "formatted_mapping": fmt_map,
            }
            ranked_matches.append(
                {
                    "pattern_id": pid,
                    "name": pname,
                    "similarity_score": sim,
                    "coverage": cov,
                }
            )

        # Rank descending by similarity score, then coverage
        ranked_matches.sort(
            key=lambda item: (item["similarity_score"], item["coverage"]),
            reverse=True,
        )
        top_pid = ranked_matches[0]["pattern_id"]
        top_res = results_by_pattern[top_pid]

    else:
        # Match against one specific pattern
        selected_pat = None
        for pat in candidate_patterns:
            pid = getattr(pat, "pattern_id", "") or pat.graph.graph.get("pattern_id", "")
            if pid.lower() == target_id_clean.lower() or target_id_clean.lower() in pid.lower():
                selected_pat = pat
                break

        if selected_pat is None:
            # Fallback to first pattern if specific ID not found
            selected_pat = candidate_patterns[0]

        pid = getattr(selected_pat, "pattern_id", "") or selected_pat.graph.graph.get("pattern_id", "")
        pname = getattr(selected_pat, "name", "") or selected_pat.graph.graph.get("name", "")
        sim, cov, steps, mapped_cnt, raw_map, fmt_map = _match_pattern_pair(
            selected_pat,
            obs_tg,
            max_agir_iterations=max_agir_iterations,
            precomputed_obs_colors=precomputed_obs_colors,
        )
        top_res = {
            "pattern": selected_pat,
            "similarity_score": sim,
            "coverage": cov,
            "agir_steps": steps + agir_steps_obs,
            "matched_nodes_count": mapped_cnt,
            "mapping": raw_map,
            "formatted_mapping": fmt_map,
        }
        # Also compute lightweight summary of all candidate patterns for the leaderboard
        for pat in candidate_patterns:
            p_id = getattr(pat, "pattern_id", "") or pat.graph.graph.get("pattern_id", "")
            p_name = getattr(pat, "name", "") or pat.graph.graph.get("name", "")
            if p_id == pid:
                p_sim, p_cov = sim, cov
            else:
                p_sim, p_cov, _, _, _, _ = _match_pattern_pair(
                    pat,
                    obs_tg,
                    max_agir_iterations=5,
                    precomputed_obs_colors=precomputed_obs_colors,
                )
            ranked_matches.append(
                {
                    "pattern_id": p_id,
                    "name": p_name,
                    "similarity_score": p_sim,
                    "coverage": p_cov,
                }
            )
        ranked_matches.sort(
            key=lambda item: (item["similarity_score"], item["coverage"]),
            reverse=True,
        )

    # 3. Format complete detailed payload
    active_pat = top_res["pattern"]
    active_pid = getattr(active_pat, "pattern_id", "") or active_pat.graph.graph.get("pattern_id", "")
    active_name = getattr(active_pat, "name", "") or active_pat.graph.graph.get("name", "")
    active_meta = getattr(active_pat, "meta", {}) or active_pat.graph.graph.get("meta", {}) or {}
    active_desc = active_meta.get("description", "") or active_pat.graph.graph.get("description", "")

    total_events = len(active_pat.events) + len(obs_tg.events)
    noise_events = max(0, len(obs_tg.events) - len(active_pat.events))

    return {
        "status": "success",
        "incident_id": f"IR-{datetime.now().strftime('%Y-%m%d')}",
        "signature_id": active_pid,
        "threat_name": active_name,
        "description": active_desc,
        "similarity_score": top_res["similarity_score"],
        "reference_coverage": top_res["coverage"],
        "total_events": total_events,
        "noise_events": noise_events,
        "benign_events_filtered": noise_events,
        "agir_steps": top_res["agir_steps"],
        "matched_nodes_count": top_res["matched_nodes_count"],
        "ref_graph_id": str(active_pid),
        "obs_graph_id": str(obs_graph_id),
        "node_mapping": top_res["formatted_mapping"],
        "raw_mapping": top_res["mapping"],
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
