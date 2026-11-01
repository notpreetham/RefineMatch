# RefineMatch

**Identity-Independent Cyber Attack Pattern Matching Using Temporal Color Refinement and Selective Individualization**

A research prototype. It turns network-communication events into attributed, directed temporal graphs, derives structural signatures with Color Refinement (1-WL), resolves ambiguity with **AGIR** (Ambiguity-Guided Individualization and Refinement), matches the result against a bank of suspicious-like and benign patterns, adds temporal/frequency evidence and contrastive scoring, and produces an analyst-reviewable explanation.

> **Read this first.** A "high" result is a **suspicious-pattern flag for analyst review, not a confirmed attack.** All bundled data is **synthetic**; the "suspicious" patterns are illustrative shapes, not recordings of real attacks. No real public dataset was evaluated. Results show the pipeline works as designed under controlled perturbation; they are **not** evidence of real-world detection performance.

## What is established vs. what is proposed

| Component | Status |
|---|---|
| Color Refinement / 1-WL, individualization-refinement, Hungarian assignment, graph edit distance, WL-subtree features | Established, classical techniques (not claimed as novel) |
| Ambiguity-guided *selection* of what to individualize, its integration into identity-independent cyber-pattern matching, and combining it with temporal/frequency/contrastive evidence | The project's proposed integration. **Its benefit is not demonstrated by our experiments** (see "Honest results") |

## Pipeline

```
events (CSV / synthetic) -> validation -> temporal graph -> identity abstraction
  -> Color Refinement -> ambiguity detection -> paired AGIR + candidate pruning
  -> node assignment + structural similarity -> temporal / frequency consistency
  -> contrastive (attack-like vs benign) scoring -> risk level + explanation
```

## Install and run (Windows 11, CMD)

Python **3.11 or newer** (developed on 3.12; syntax checked against the 3.11 grammar; not executed on 3.11 by the author).

```bat
cd RefineMatch
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

pytest                                             :: run all tests
python examples\full_demo.py                       :: end-to-end synthetic demo
python examples\member1_demo.py                    :: original Member 1 demo
python -m src.evaluation.experiments --quick       :: fast experiments (about 1 minute)
python -m src.evaluation.experiments               :: full experiments, writes results\
python -m src.evaluation.experiments --no-ged      :: skip the slow edit-distance baseline
streamlit run dashboard\app.py                     :: dashboard (opens in your browser)
```

If `.venv\Scripts\activate` fails in PowerShell, use CMD or run `Set-ExecutionPolicy -Scope Process RemoteSigned` first.

## Dashboard

`streamlit run dashboard\app.py` starts in **demo mode** (synthetic data loaded automatically; no API keys, network, or downloads). Screens: 1 Input (synthetic or CSV upload, temporal window, identity masking) · 2 Raw events · 3 Graph · 4 Color Refinement · 5 AGIR · 6 Matching (correspondence, pattern comparison) · 7 Risk (score factors, explanation) · 8 Mutation demo · 9 Evaluation (reads `results/experiments.json`). Every number is computed by the real backend (`dashboard/service.py` calls `src/`).

CSV format: required `timestamp,source,destination,event_type`; optional `protocol,source_port,destination_port,bytes,duration`. CSV data has no node types, so tick **"Ignore node types"** (the pattern bank is then matched without type information).

## Repository layout and how modules connect

```
src/core/         models, config (all constants), exceptions            [Member 1]
src/graph/        graph_builder, anonymizer, temporal_graph, graph_utils [Member 1]
src/refinement/   color_refinement [M1]; ambiguity, individualization (AGIR) [M2]
src/matching/     candidate_generation, node_assignment, graph_matcher   [M2]
src/scoring/      structural_score [M2]; temporal_score, contrastive_score, risk_score [M3]
src/ingestion/    csv_parser, dataset_loader, synthetic_generator, pattern_bank [M3]
src/explanation/  evidence_generator
src/robustness/   mutation_engine                                        [M4]
src/evaluation/   metrics, baselines, experiments                        [M4]
src/pipeline.py   integration: observed graph -> banks -> match -> scores -> explanation
dashboard/        service.py (backend for the UI), app.py (Streamlit)
data/             reference_patterns/, benign_patterns/ (synthetic JSON banks)
results/          experiments.json + CSV tables (generated)
tests/ examples/
```

Dependency direction: `core <- graph <- refinement <- matching <- scoring <- pipeline <- evaluation/dashboard`. `src.core` imports nothing above it (tested).

## Algorithms (short) and limitations

* **Color Refinement**: colors are truncated SHA-256 over a canonical encoding of `(type, degrees, edge-type histograms)` then of `(color, multiset of (direction, edge type, neighbour color))`. Content-addressed, so colors from two graphs are comparable **at the same round**. 1-WL cannot distinguish every non-isomorphic pair (tested: a directed 6-cycle vs two 3-cycles).
* **Ambiguity score** (heuristic): `(1 - 1/size) * (0.5 + 0.5 * mean(d/(d+1)))` per color class.
* **AGIR**: within matching, the most ambiguous reference class is chosen, a reference node is paired with each candidate (shared fresh color), both graphs are refined a fixed number of rounds, and the branch that most reduces candidate ambiguity is kept. Budgeted greedy search; **no completeness or isomorphism guarantee**.
* **Matching**: working depth chosen where most reference nodes have exact-color counterparts (so noise falls back to shallower rounds); relaxed candidates (profile overlap >= 0.5, only when exact supply is too small) tolerate missing/extra edges; Hungarian assignment with an identity-free temporal tie-break for symmetric nodes. Similarity = 0.5 x node score + 0.5 x edge score.
* **Temporal/frequency**: order = LCS of first-occurrence event-type order; frequency = distribution-shape similarity (scale-invariant); consistency = share of mapped edge pairs with preserved first-seen order.
* **Risk**: weighted sum of structural, temporal, frequency, normalised contrastive. Default weights (0.35/0.25/0.15/0.25) and thresholds (0.60 flag, 0.40 medium) are **provisional**; `tune_weights_and_threshold` fits them on labelled development data. A guard downgrades "high" to "medium" if the observation is not more similar to the suspicious-like bank than to the benign bank.
* **Other known limits**: node types are supplied, never inferred; heuristics (ambiguity score, thresholds, overlap 0.5) were not tuned on real data; percentage mutations are coarse on 2-9 node graphs (at least one item changes when p > 0); the role-exact matching accuracy metric penalises swaps of structurally identical nodes.

## Experiments (`python -m src.evaluation.experiments`)

Protocol: development seeds tune weights/threshold; disjoint test seeds are scored with frozen settings; baselines get a tuned decision margin on the same seeds. Sample sizes are tiny (24 test graphs per condition, 16 for tuning): **indicative only, no significance testing.** All outputs are deterministic except runtime/memory.

### Honest results (full run, shipped in `results/`)

* **Identity robustness (works as designed):** renaming all identifiers changed no final score (max difference 0.0), no risk level, and no best-pattern choice; role-exact matching accuracy 1.0 for raw renamed IDs and anonymized graphs.
* **AGIR did not show a benefit here.** With noise, CR-only and AGIR gave identical F1 (0.889 typed; 0.421 untyped/unlabelled) because AGIR rarely acted (0-0.13 individualizations per graph). Random individualization was slightly worse in one condition (F1 0.846) but gave higher true-pattern similarity than AGIR in the ablation condition (0.968 vs 0.927). The conservative selection threshold and usefulness test are likely too strict; this is unresolved.
* **Baselines:** on clean cross-environment data every method (including degree statistics) reaches F1 1.0, i.e. that condition is too easy to discriminate. On the hard condition (labels removed, 10% noise) RefineMatch F1 0.889 vs CR-only histogram 0.897, WL-cosine 0.857, degree statistics 0.759; GED was skipped (graphs too large). RefineMatch is comparable to, not clearly better than, the simple baselines.
* **Temporal/frequency evidence helps where structure is ambiguous:** with labels removed, structure-only F1 0.909 (FPR 0.33) rises to 0.968 with temporal + frequency.
* **Contrastive scoring trades FPR for FNR:** the full model has FPR 0 but FNR 0.2 (F1 0.889), while the same model without contrastive scoring has F1 0.933 (FPR 0.11, FNR 0.07) in the ablation condition.
* **Mutation robustness:** clean/frequency/timestamp mutations leave similarity ~1.0 (expected: the frequency measure is scale-invariant and ordering is robust on this generator); 10-20% deleted edges lower mean true-pattern similarity to ~0.67 while F1 stays 1.0; noise nodes lower it to ~0.97 (0.90 at 30%).
* The baseline set omits a GNN baseline and uses a **WL-subtree cosine** in place of true Graph2Vec; GED is size/time limited.

## Testing

`pytest` runs 287 tests (identity, graph, refinement, AGIR, matching, scoring, ingestion, mutation, metrics, experiments, dashboard, end-to-end). **How they were verified by the author:** pytest could not be installed in the authoring sandbox (no network), so the suite was executed with a minimal pytest-compatible runner (`raises`, `parametrize`); 287/287 passed there. Please run real `pytest` on your machine to confirm. The dashboard tests run the real `dashboard/app.py` against a *stub* Streamlit (verifies code paths and backend calls); **starting the real Streamlit server was not verified by the author.**

## Troubleshooting

* `ModuleNotFoundError: No module named 'src'` - run commands from the project root (the folder with `README.md`).
* `streamlit` not recognised - activate the venv (`.venv\Scripts\activate`) and re-run `pip install -r requirements.txt`.
* Port in use - `streamlit run dashboard\app.py --server.port 8502`.
* Experiments slow - use `--quick` and/or `--no-ged`.
* "No results found" on the Evaluation screen - run `python -m src.evaluation.experiments --quick`.
* CSV rejected - the error names the file, line and column; timestamps must be ISO-8601 or Unix seconds, and all must be timezone-aware or all naive.
* Regenerate the pattern bank JSON: `python -m src.ingestion.pattern_bank` (a test checks shipped files match the generator).

## Not implemented

StreamSpot / DARPA TC / OpTC / NetFlow dataset adapters (no data was available to validate a schema; export to CSV and use `load_dataset("csv", path)`), a GNN baseline, and any evaluation on real data.
