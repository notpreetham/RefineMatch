# RefineMatch: Ambiguity-Guided Provenance Graph Matching

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-2.1.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB.svg?logo=react)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8.0-646CFF.svg?logo=vite)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/Tests-290%20Passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**RefineMatch** is a deterministic, identity-independent cybersecurity threat-hunting engine designed to locate complex attack signatures within massive, noisy enterprise provenance telemetry.

Modern Advanced Persistent Threats (APTs) continually evade signature and rule-based detectors by rotating IP addresses, hostnames, and process IDs. RefineMatch abstracts away ephemeral identifiers, transforming system call and network logs into attributed, directed temporal provenance graphs. Using a mathematically rigorous combination of **Weisfeiler-Lehman (1-WL) Color Refinement**, **Ambiguity-Guided Individualization and Refinement (AGIR)**, and the **Hungarian Algorithm**, RefineMatch identifies needle-in-a-haystack attack topologies with near-exact structural correspondence.

---

## 🎯 Key Highlights

- **Deterministic & Explainable:** Free of stochastic neural network hallucinations. Every node assignment comes with an optimal bipartite correspondence score and an analyst-reviewable forensic explanation.
- **Identity Invariance:** Attack detection remains provably invariant under complete node relabeling, host pseudonymization, and process identifier permutation.
- **Noise Resilience:** Correctly isolates small 2-to-9 node multi-stage attack signatures embedded in provenance graphs containing over 8,000+ noisy background enterprise events.
- **Real-World Provenance Ingestion:** Built-in streaming parser for the official **DARPA / StreamSpot** provenance dataset, plus dynamic upload for custom enterprise `.tsv` and `.csv` logs.
- **Enterprise Dark-Mode Dashboard:** Powered by a high-throughput **FastAPI** backend and a **React 19 / Vite** visual investigation interface featuring dynamic SVG dual-viewport graph visualization, real-time pattern scanning, and interactive 1:1 node assignment tracing.

---

## 🔬 Core Mathematical Architecture

```
Observed Telemetry Logs (.tsv / .csv)
               │
               ▼
   [ StreamSpot / CSV Ingestion ] ──> Attributed TemporalDiGraph (V, E, T)
               │
               ▼
   [ 1-WL Color Refinement ] ───────> Iterative Multiset Color Classes
               │
               ▼
   [ AGIR Symmetry Breaking ] ──────> Resolves Automorphic Equivalence via Tie-Breaking
               │
               ▼
   [ Hungarian Matching (1:1) ] ────> Optimal Bipartite Node-to-Node Alignment
               │
               ▼
   [ Multi-Factor Risk Scoring ] ───> Structural + Temporal (LCS) + Frequency + Contrastive
               │
               ▼
   [ Full-Stack Analyst Console ] ──> Threat Narrative, Dynamic Viewport, & Leaderboard
```

### 1. 1-WL Color Refinement (Partition Sorting)
The engine initializes node colors using attributed types (process, socket, file, host). In each refinement iteration $k$, every node's color updates by hashing its current color with the sorted multiset of neighbor colors:
$$c_{v}^{(k+1)} = \text{Hash}\left(c_{v}^{(k)}, \{\!\!\{ (c_{u}^{(k)}, \text{attr}(u, v)) \mid u \in \mathcal{N}(v) \}\!\!\}\right)$$
Refinement iterates until partition stability is achieved, rapidly pruning candidate match pairs without expensive subgraph isomorphism search.

### 2. AGIR Tie-Breaking (Symmetry Resolution)
Standard 1-WL color refinement fails on symmetric structures (e.g., identical fan-out sockets, parallel worker threads, or cycle automorphisms). **AGIR** (Ambiguity-Guided Individualization and Refinement) computes an ambiguity score across color classes:
- Identifies equitable partitions where multiple nodes share identical color multisets.
- Selectively individualizes ambiguous nodes by assigning distinct singleton colors.
- Re-refines the graph until all automorphic symmetries are resolved and the structural representation reaches deterministic stability.

### 3. Hungarian Algorithm (Optimal Bipartite Node Matching)
Given the individualized color signatures between reference pattern $G_{\text{ref}}$ and observed telemetry $G_{\text{obs}}$, RefineMatch constructs a cost matrix based on color compatibility, topological distance, and edge consistency. The **Hungarian algorithm (Kuhn-Munkres)** computes the global maximum-weight bipartite 1-to-1 node correspondence in polynomial time $O(n^3)$.

### 4. Multi-Factor Contrastive Scoring
The final threat score combines:
- **Structural Similarity ($S_{\text{struct}}$):** Ratio of verified edge and node attributes across matched pairs.
- **Temporal Order Consistency ($S_{\text{temp}}$):** Longest Common Subsequence (LCS) of first-seen event types along mapped provenance paths.
- **Frequency Consistency ($S_{\text{freq}}$):** Scale-invariant event-type distribution alignment.
- **Contrastive Risk Downgrade:** Compares structural correspondence against benign baseline archetypes to eliminate false positives from common administrative behaviors (NTP, DNS sync, routine updates).

---

## 📊 Telemetry Ingestion & StreamSpot Dataset

RefineMatch supports both synthetic threat generators and real-world system provenance datasets:

- **StreamSpot TSV Streaming Adapter:** Built-in zero-copy line parser for the DARPA StreamSpot provenance format (`source_id`, `source_type`, `destination_id`, `destination_type`, `edge_type`, `graph_id`). Efficiently parses multi-million event datasets (e.g., `all.tsv` ~2.3 GB) with sub-second target graph filtering.
- **Dynamic File Upload (.tsv / .csv):** Drag-and-drop log files directly via the dashboard. RefineMatch dynamically detects column formats, reconstructs directed provenance topologies, and triggers automated multi-pattern threat scans.
- **Pre-Shipped Attack Bank:** Includes standard MITRE ATT&CK inspired patterns:
  - `SUSP_SYN_001`: External-to-Internal Multi-Hop Intrusion Chain
  - `SUSP_SYN_002`: Lateral Movement Host Chain
  - `SUSP_SYN_003`: Scanning & Reconnaissance Fan-Out
  - `SUSP_SYN_004`: Command & Control (C2) Heartbeat Beaconing
  - `SUSP_SYN_005`: Data Staging Fan-In & Cloud Exfiltration

---

## 💻 Full-Stack Dark-Mode Dashboard

RefineMatch features a production-ready Incident Response dashboard:

- **Backend Bridge (`dashboard/server.py`):** High-performance FastAPI asynchronous server providing:
  - `GET /api/patterns`: Catalog of available attack signatures with metadata.
  - `POST /api/run-match`: Dynamic file upload endpoint supporting full library scanning (`target_pattern_id="ALL"`) or targeted signature evaluation.
  - `GET /api/run-match`: Automated fallback executing against local sample datasets.
- **Dynamic SVG Dual Graph Viewport (`dashboard/web`):**
  - **Dynamic Topology Layout:** Deterministic, non-overlapping concentric layout algorithm designed in pure React/SVG.
  - **Interactive 1:1 Assignment Bridge:** Hovering any node draws a real-time bezier curve connecting the reference archetype entity directly to its mapped enterprise counterpart.
  - **Threat Detection Leaderboard:** Displays all evaluated candidate signatures ranked by similarity percentage and pattern coverage.
  - **Three Viewport Modes:** *Split View* (side-by-side comparative analysis), *Overlay Mode* (ghosted signature projection), and *Diff Heatmap* (color-coded matched vs. noise telemetry).
  - **Forensic Export:** One-click JSON export containing complete incident metadata, node assignments, and triage status.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python **3.11 or newer** (tested on 3.12)
- Node.js **18+** (for frontend development)

### 2. Installation
```powershell
# Clone repository
git clone https://github.com/your-username/RefineMatch.git
cd RefineMatch

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1    # On Windows PowerShell
# source .venv/bin/activate   # On Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch the Full-Stack Dashboard
Run the FastAPI application server:
```powershell
python dashboard/server.py
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```
> The FastAPI server serves the compiled React/Vite dashboard bundle directly, complete with dynamic dataset upload, interactive graph canvases, and live multi-pattern scanning.

### 4. Run the Full Test Suite
RefineMatch is verified by **290 unit and integration tests**:
```powershell
pytest
```

### 5. Run the StreamSpot End-to-End Pipeline
To run the algorithmic matching pipeline directly on the StreamSpot dataset via terminal:
```powershell
python src/run_streamspot.py
```

---

## 📁 Repository Structure

```
RefineMatch/
├── dashboard/
│   ├── server.py                 # FastAPI backend API bridge
│   ├── app.py                    # Streamlit legacy dashboard
│   ├── service.py                # Dashboard business logic service
│   └── web/                      # React 19 + Vite frontend application
│       ├── src/
│       │   ├── App.tsx           # Main Incident Response console & dynamic graph canvas
│       │   └── main.tsx          # React application entry point
│       ├── package.json
│       ├── vite.config.ts
│       └── dist/                 # Pre-compiled static production bundle
├── src/
│   ├── core/
│   │   ├── config.py             # System thresholds, constants, and taxonomies
│   │   ├── exceptions.py         # Custom domain exceptions
│   │   └── models.py             # TemporalGraph, EventRecord, GraphNode dataclasses
│   ├── graph/
│   │   ├── anonymizer.py         # Identity abstraction & pseudonymization engine
│   │   ├── graph_builder.py      # NetworkX temporal graph constructor
│   │   └── temporal_graph.py     # Temporal graph operations & metadata accessors
│   ├── ingestion/
│   │   ├── csv_parser.py         # Generic enterprise CSV event log parser
│   │   ├── dataset_loader.py     # Dataset loader interface
│   │   ├── pattern_bank.py       # Built-in synthetic & reference pattern library
│   │   ├── streamspot_adapter.py # Real-world StreamSpot TSV dataset streaming adapter
│   │   └── synthetic_generator.py# Parametric attack & benign graph generator
│   ├── matching/
│   │   ├── candidate_generation.py # 1-WL color class candidate pruning
│   │   ├── graph_matcher.py      # End-to-end graph matching workflow
│   │   ├── node_assignment.py    # Hungarian 1-to-1 optimal bipartite matcher
│   │   └── pattern_bank.py       # Re-export module for matching routines
│   ├── refinement/
│   │   ├── ambiguity.py          # Equitable partition ambiguity detector
│   │   ├── color_refinement.py   # 1-WL multiset color refinement algorithm
│   │   └── individualization.py  # AGIR tie-breaking & symmetry resolution
│   ├── scoring/
│   │   ├── contrastive_score.py  # Attack vs benign contrastive scoring
│   │   ├── risk_score.py         # Multi-factor risk level synthesizer
│   │   ├── structural_score.py   # Structural graph similarity calculation
│   │   └── temporal_score.py     # Temporal event ordering (LCS) & frequency score
│   ├── evaluation/
│   │   ├── baselines.py          # Classical baseline matchers (degree stats, GED, WL-cosine)
│   │   ├── experiments.py        # Benchmark experiment suite
│   │   └── metrics.py            # Precision, recall, F1, role accuracy metrics
│   ├── explanation/
│   │   └── evidence_generator.py # Plain-language forensic narrative generator
│   ├── robustness/
│   │   └── mutation_engine.py    # Perturbation engine (edge drops, noise nodes, timestamp jitter)
│   ├── main.py                   # End-to-end pipeline runner
│   └── run_streamspot.py         # Real-world StreamSpot matching execution script
├── data/
│   ├── benign_patterns/          # Baseline benign pattern JSON definitions
│   ├── reference_patterns/       # MITRE attack pattern JSON definitions
│   └── streamspot/               # StreamSpot TSV datasets (sample_0_1.tsv)
├── tests/                        # 290 test cases covering 100% of pipeline modules
├── pyproject.toml                # Project metadata & pytest configuration
├── requirements.txt              # Production Python dependencies
└── README.md                     # Project documentation
```

---

## 🧪 Experimental Benchmarks & Robustness

RefineMatch was evaluated across multiple experimental scenarios (results stored in `results/`):

1. **Identity Invariance:** Renaming 100% of hostnames, IP addresses, and process IDs results in **0.0 score difference** and **1.0 role-exact accuracy** — confirming complete identity independence.
2. **Noise Resistance:** Evaluated against 10%–30% random edge insertions and extraneous background events. The 1-WL partition pruning filters benign noise before the Hungarian algorithm executes.
3. **Temporal Sensitivity:** Where structural topologies between benign and malicious processes are similar, temporal event order consistency (LCS) reliably breaks the tie and eliminates false positives.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
