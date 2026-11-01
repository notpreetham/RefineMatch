# RefineMatch — Member 1 (Core Models, Graph, Identity Abstraction, Color Refinement)

Foundation layer for RefineMatch. Members 2–4 import this code; public names and signatures follow the team blueprint.

## Install and test

```bash
python -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r requirements.txt
pytest                      # uses pytest.ini (pythonpath = .)
python examples/member1_demo.py
```

## Layout

```
src/core/{models,config,exceptions}.py
src/graph/{graph_builder,anonymizer,temporal_graph}.py
src/refinement/color_refinement.py
tests/  examples/member1_demo.py  pytest.ini  requirements.txt
```

## Public API

| Module | Names |
|---|---|
| `src.core.models` | `EventRecord`, `GraphNode`, `GraphEdge`, `TemporalGraph`, `RefinementResult`, `MatchResult`, `ScoreResult`, `is_timezone_aware` |
| `src.graph.graph_builder` | `build_temporal_graph`, `aggregate_edges` (+ additive: `validate_events`, `assign_node_attributes`, `get_graph_node`, `get_graph_edge`) |
| `src.graph.anonymizer` | `anonymize_graph`, `create_identity_mapping` |
| `src.graph.temporal_graph` | `get_ordered_events`, `get_event_frequency`, `get_temporal_window` (+ additive: `copy_temporal_graph`) |
| `src.refinement.color_refinement` | `initialize_colors`, `refine_once`, `color_refine`, `get_color_classes` (+ additive: `refinement_history`, `color_histogram`, `wl_equivalent`) |

Additive helpers do not alter any specified signature.

## Graph attribute contract

`TemporalGraph.graph` is an `nx.DiGraph` with `str` node IDs, one edge per ordered pair.

**Node:** `node_type` (default `"host"`; set via `assign_node_attributes`), `role` (or `None`), `original_id` (`None` until anonymised; never a structural feature).

**Edge (source → destination):** `edge_type` (dominant event type, ties alphabetical), `edge_types` (`{type: count}`), `direction` (`"source_to_destination"`), `weight` (event count), `first_seen`, `last_seen`, `protocol` (dominant non-null) and `protocols`, `bytes_total` and `duration` (**sums over events that reported a value; `None` if none did — unknown ≠ 0**), plus `bytes_known_count`, `duration_known_count`. Ports stay on events only.

`TemporalGraph.events` is an independent copy in **input order**; use `get_ordered_events` for chronological order. `start_time`/`end_time` are min/max timestamps (`None` if empty).

## Conventions

- **Equal timestamps:** stable sort, input order kept.
- **Timezones:** aware timestamps compare as instants; mixing aware and naive raises `InvalidEventError` / `InvalidTimeWindowError`.
- **Windows:** half-open `[start, end)`. Adjacent windows never double-count. To include a graph's last event use `end = graph.end_time + epsilon`.
- **Frequency:** `get_event_frequency` is directional and counts preserved events (equals edge `weight` for built graphs).

## Identity abstraction

IDs become `N_0001, N_0002, …` in order of first appearance in chronologically ordered events (source before destination), then event-less nodes in insertion order. The order never inspects original names, so renaming machines yields identical anonymised output. Replacement is simultaneous, so abstract-looking original IDs cannot collide. The input graph is never mutated.

**This is pseudonymisation, not privacy protection.** Topology, timing, frequency and protocols remain and may enable re-identification; `original_id` and the mapping are reversible by design.

## Color Refinement (1-WL)

`color_0(v) = H(node_type, in-degree, out-degree, out/in edge-type histograms)`;
`color_{k+1}(v) = H(color_k(v), sorted multiset of (out|in, edge-type label, neighbour color))`.
`H` = truncated SHA-256 (128 bits) of canonical JSON — never Python's `hash()`.

Not used as features: IDs, `original_id`, `role`, insertion order, weights, timestamps, bytes. (To make roles matter, encode them in `node_type`.)

**Cross-graph comparison (for Member 2).** Colors are content-addressed, so no joint refinement is needed, **provided you compare colors from the same round**. Final `color_refine` colors of 1-WL-equivalent graphs are comparable (they stop at the same round); different `iterations` already proves the graphs differ. For an observed graph with extra noise nodes compared to a reference pattern, compare a fixed shallow depth: `refinement_history(g)[k]`. Never compare different rounds.

**1-WL ≠ isomorphism.** Equal stable colorings are necessary, not sufficient (a directed 6-cycle and two directed 3-cycles are indistinguishable; tested). `wl_equivalent` returning `True` means "not distinguished"; `False` is conclusive.

`iterations` = rounds executed including the confirming round; `stable` = a non-splitting round was observed within the cap.

## Test status

Run `pytest`. In the authoring sandbox pytest could not be installed (no network), so the suite was executed with a minimal local pytest-compatible shim (supports `raises`, `parametrize`; not shipped). Please confirm with real pytest on your machine.

## Limitations

- Node types/roles are never inferred; supply them explicitly.
- Edge labels use the *set* of event types, not counts; frequency belongs to the scoring modules.
- Degrees are over distinct neighbours (`DiGraph`), not event counts.
- 128-bit truncated digests: collisions negligible, not impossible.
- Provisional thresholds in `config.py` (match/risk/ambiguity/individualization) are placeholders, not empirically derived.
- `MultiDiGraph`, undirected graphs and non-string node IDs are rejected.

## Integration guide

- **Member 2:** call `color_refine(tg.graph)` on anonymised graphs; compare `refinement_history` entries by index; `get_color_classes` gives ambiguous classes (size > 1). Individualize by replacing a color and calling `refine_once` — it accepts any coloring covering exactly the graph's nodes.
- **Member 3:** build events as `EventRecord` (validated on construction); `build_temporal_graph` → `assign_node_attributes` → `anonymize_graph`. Use `get_temporal_window` for windows and `get_event_frequency` for counts. Normalise timestamps to all-aware or all-naive first.
- **Member 4:** to rename identities reuse `create_identity_mapping`/`copy_temporal_graph`; edge attribute names above are the contract if you mutate graphs (keep `edge_types` consistent with `edge_type`/`weight`).

## Assumptions needing team approval

1. `MatchResult`/`ScoreResult` live in `models.py` as plain containers.
2. Half-open time windows.
3. `EventRecord` etc. validate at construction (CSV parsing must normalise NaN/negative values first).
4. `duration` on edges is a **total**, not a mean.
5. Roles and weights excluded from refinement.
6. Extra files: `pytest.ini` and additive helper functions.
