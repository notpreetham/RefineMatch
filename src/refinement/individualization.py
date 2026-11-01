"""Individualization and AGIR (Ambiguity-Guided Individualization and Refinement).

Established techniques: Color Refinement and individualization-refinement are
classical (they underlie practical graph-isomorphism tools such as nauty/
Traces). The *proposed contribution* of this project is the ambiguity-guided
SELECTION of which node to individualize and the integration with identity-
independent cyber-pattern matching and temporal scoring.

Individualization gives one node a fresh unique color and re-runs refinement.
The fresh color depends only on the node's old color (never on its ID), so
two graphs that individualize corresponding nodes get comparable colors.

LIMITS: this is a heuristic, budgeted search. It does NOT guarantee a complete
isomorphism decision (that would need backtracking over all branches). For
automorphic ambiguity (e.g. star leaves) which node is chosen is arbitrary but
harmless; ties are broken by node ID order, the only place IDs are consulted.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field

import networkx as nx

from src.core.config import (
    COLOR_DIGEST_HEX_LENGTH,
    DEFAULT_AMBIGUITY_THRESHOLD,
    DEFAULT_MAX_CANDIDATES_PER_CLASS,
    DEFAULT_MAX_INDIVIDUALIZATIONS,
    DEFAULT_MAX_REFINEMENT_ITERATIONS,
)
from src.core.exceptions import InvalidRefinementInputError
from src.core.models import RefinementResult
from src.refinement.ambiguity import (
    calculate_ambiguity_score,
    find_ambiguous_classes,
    rank_ambiguous_classes,
)
from src.refinement.color_refinement import color_refine, get_color_classes, refine_once

SELECTION_STRATEGIES = ("agir", "random")


@dataclass
class AgirStep:
    """One accepted individualization (for dashboards and tests)."""

    step: int
    color_class: str
    class_size: int
    ambiguity_score: float
    candidates: list[str]
    selected_node: str
    classes_before: int
    classes_after: int
    ambiguous_nodes_before: int
    ambiguous_nodes_after: int

    @property
    def refinement_gain(self) -> int:
        """Number of new color classes created by this step."""
        return self.classes_after - self.classes_before


def _digest(parts: list) -> str:
    raw = json.dumps(parts, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:COLOR_DIGEST_HEX_LENGTH]


def _fresh_color(seed_parts: list, taken: set[str]) -> str:
    """Deterministic unused color derived from ``seed_parts`` (no node IDs)."""
    counter = 0
    candidate = _digest(seed_parts)
    while candidate in taken:
        counter += 1
        candidate = _digest(seed_parts + [counter])
    return candidate


def individualize_node(colors: dict[str, str], node_id: str) -> dict[str, str]:
    """Return a copy of ``colors`` where ``node_id`` has a fresh unique color."""
    if node_id not in colors:
        raise InvalidRefinementInputError(f"node {node_id!r} is not in the coloring")
    updated = dict(colors)
    updated[node_id] = _fresh_color(["indiv", colors[node_id]], set(colors.values()))
    return updated


def individualize_pair(
    colors_a: dict[str, str], node_a: str, colors_b: dict[str, str], node_b: str
) -> tuple[dict[str, str], dict[str, str]]:
    """Give ``node_a`` (graph A) and ``node_b`` (graph B) the SAME fresh color.

    Used by matching: pairing two nodes as "the same" must make them equal in
    both colorings so refinement propagates the pairing identically.
    """
    for colors, node in ((colors_a, node_a), (colors_b, node_b)):
        if node not in colors:
            raise InvalidRefinementInputError(f"node {node!r} is not in the coloring")
    taken = set(colors_a.values()) | set(colors_b.values())
    token = _fresh_color(["pair", colors_a[node_a], colors_b[node_b]], taken)
    new_a, new_b = dict(colors_a), dict(colors_b)
    new_a[node_a] = token
    new_b[node_b] = token
    return new_a, new_b


def refine_fixed_rounds(
    graph: nx.DiGraph, colors: dict[str, str], rounds: int
) -> dict[str, str]:
    """Apply exactly ``rounds`` refinement rounds (no early stop).

    A fixed round count keeps colors of two graphs comparable.
    """
    if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 0:
        raise InvalidRefinementInputError("rounds must be a non-negative int")
    for _ in range(rounds):
        res = refine_once(graph, colors)
        colors = res.node_colors if isinstance(res, RefinementResult) else res
    return colors


def refine_from_colors(
    graph: nx.DiGraph,
    colors: dict[str, str],
    max_iterations: int = DEFAULT_MAX_REFINEMENT_ITERATIONS,
) -> tuple[dict[str, str], int, bool]:
    """Refine from a given coloring until stable or capped.

    Returns ``(colors, rounds_executed, stable)`` with the same stability
    rule as :func:`color_refine`.
    """
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 0:
        raise InvalidRefinementInputError("max_iterations must be a non-negative int")
    if not colors:
        return colors, 0, True
    for executed in range(1, max_iterations + 1):
        refined_res = refine_once(graph, colors)
        refined = refined_res.node_colors if isinstance(refined_res, RefinementResult) else refined_res
        stable = len(set(refined.values())) == len(set(colors.values()))
        colors = refined
        if stable:
            return colors, executed, True
    return colors, max_iterations, False


def _ambiguous_node_count(colors: dict[str, str]) -> int:
    return sum(len(nodes) for nodes in get_color_classes(colors).values() if len(nodes) > 1)


def run_individualization(
    graph: nx.DiGraph, refinement: RefinementResult, node_id: str
) -> RefinementResult:
    """Individualize ``node_id`` in ``refinement`` and re-run refinement."""
    colors = individualize_node(refinement.node_colors, node_id)
    final, rounds, stable = refine_from_colors(graph, colors)
    return RefinementResult(
        node_colors=final,
        color_classes=get_color_classes(final),
        iterations=refinement.iterations + rounds,
        stable=stable,
    )


def agir_refine_with_trace(
    graph: nx.DiGraph,
    max_individualizations: int = DEFAULT_MAX_INDIVIDUALIZATIONS,
    selection: str = "agir",
    seed: int = 0,
) -> tuple[RefinementResult, list[AgirStep]]:
    """AGIR on a single graph, returning the result and a step trace.

    ``selection="agir"``: only classes with ambiguity score >=
    ``DEFAULT_AMBIGUITY_THRESHOLD`` are considered; the highest-ranked class is
    chosen and, within it, the node whose individualization yields the largest
    refinement gain (ties: smallest node ID). Steps that would not reduce the
    number of ambiguous nodes are rejected.
    ``selection="random"``: the ablation baseline (random class and node, no
    usefulness check, seeded).
    Stops when no worthwhile ambiguity remains or the budget is exhausted.
    """
    if selection not in SELECTION_STRATEGIES:
        raise InvalidRefinementInputError(f"selection must be one of {SELECTION_STRATEGIES}")
    if isinstance(max_individualizations, bool) or not isinstance(max_individualizations, int) \
            or max_individualizations < 0:
        raise InvalidRefinementInputError("max_individualizations must be a non-negative int")

    result = color_refine(graph)
    colors, iterations, stable = result.node_colors, result.iterations, result.stable
    trace: list[AgirStep] = []
    rng = random.Random(seed)

    for step in range(1, max_individualizations + 1):
        current = RefinementResult(colors, get_color_classes(colors), iterations, stable)
        ranked = rank_ambiguous_classes(graph, current)
        if selection == "agir":
            ranked = [(c, s) for c, s in ranked if s >= DEFAULT_AMBIGUITY_THRESHOLD]
        if not ranked:
            break
        color, score = ranked[0] if selection == "agir" else rng.choice(ranked)
        class_nodes = sorted(current.color_classes[color])
        pool = (
            [rng.choice(class_nodes)]
            if selection == "random"
            else class_nodes[:DEFAULT_MAX_CANDIDATES_PER_CLASS]
        )
        classes_before = len(current.color_classes)
        ambiguous_before = _ambiguous_node_count(colors)
        best = None
        for node in pool:
            new_colors, rounds, new_stable = refine_from_colors(
                graph, individualize_node(colors, node)
            )
            gain = (len(set(new_colors.values())) - classes_before,
                    ambiguous_before - _ambiguous_node_count(new_colors))
            if best is None or gain > best[0]:
                best = (gain, node, new_colors, rounds, new_stable)
        gain, node, new_colors, rounds, new_stable = best
        if selection == "agir" and (gain[0] < 1 or gain[1] < 1):
            break  # not useful: keep the branch only if ambiguity is reduced
        trace.append(AgirStep(
            step=step, color_class=color, class_size=len(class_nodes),
            ambiguity_score=score, candidates=pool, selected_node=node,
            classes_before=classes_before, classes_after=len(set(new_colors.values())),
            ambiguous_nodes_before=ambiguous_before,
            ambiguous_nodes_after=_ambiguous_node_count(new_colors),
        ))
        colors, iterations, stable = new_colors, iterations + rounds, new_stable

    final = RefinementResult(colors, get_color_classes(colors), iterations, stable)
    return final, trace


def agir_refine(
    graph: nx.DiGraph,
    max_individualizations: int = DEFAULT_MAX_INDIVIDUALIZATIONS,
) -> RefinementResult:
    """AGIR (ambiguity-guided) refinement of one graph; see the traced variant."""
    return agir_refine_with_trace(graph, max_individualizations)[0]


def individualize_graph(
    graph: nx.DiGraph | TemporalGraph,
    refinement: RefinementResult,
) -> RefinementResult:
    """AGIR step: pick the most ambiguous class in ``graph`` and individualize one node.

    Returns an updated RefinementResult with the individualized node assigned
    a fresh unique color, ready for the next ``refine_once`` pass.
    If no ambiguous classes remain, returns the refinement with ``stable=True``.
    """
    g = graph.graph if hasattr(graph, "graph") else graph
    ranked = rank_ambiguous_classes(g, refinement)
    if not ranked:
        return RefinementResult(
            node_colors=dict(refinement.node_colors),
            color_classes=dict(refinement.color_classes),
            iterations=refinement.iterations,
            stable=True,
        )
    color, _ = ranked[0]
    class_nodes = sorted(refinement.color_classes[color])
    node_to_indiv = class_nodes[0]
    new_colors = individualize_node(refinement.node_colors, node_to_indiv)
    return RefinementResult(
        node_colors=new_colors,
        color_classes=get_color_classes(new_colors),
        iterations=refinement.iterations,
        stable=False,
    )
