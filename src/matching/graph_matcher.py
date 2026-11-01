"""Identity-independent graph matching: Color Refinement + paired AGIR + assignment.

Pipeline (blueprint 6.5):
 1. Color Refinement of both graphs (content-addressed, comparable per round).
 2. WORKING DEPTH: pick the deepest refinement round at which the most
    reference nodes have an exact-color observed counterpart. Noise breaks deep
    colors first, so noisy inputs fall back to shallower rounds automatically.
 3. Candidate generation (exact colors, relaxed fallback).
 4. PAIRED AGIR (if candidates are ambiguous): choose the most ambiguous
    reference class (``selection="agir"``), pair a reference node with each
    candidate, give the pair one shared fresh color, refine both graphs a fixed
    number of rounds, and keep the branch that most reduces candidate
    ambiguity. Only branches that help are kept; the budget is capped.
 5. One-to-one assignment (Hungarian) and structural similarity.

``MatchResult.node_mapping`` maps REFERENCE node -> OBSERVED node.
``confidence`` = coverage * mean(1/|candidates|): a heuristic uniqueness measure,
NOT a probability. This is a greedy, budgeted search: it can miss the best
mapping, and 1-WL limits apply (see color_refinement docs). Original IDs,
roles and ``original_id`` are never read; node IDs only break ties for
determinism.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.core.config import (
    DEFAULT_AMBIGUITY_THRESHOLD,
    DEFAULT_MATCHER_REFINE_ROUNDS,
    DEFAULT_MAX_BRANCH_EVALUATIONS,
    DEFAULT_MAX_CANDIDATES_PER_CLASS,
    DEFAULT_MAX_INDIVIDUALIZATIONS,
)
from src.core.exceptions import InvalidGraphError
from src.graph.graph_utils import relative_first_seen
from src.core.models import MatchResult, TemporalGraph
from src.matching.candidate_generation import generate_candidates
from src.matching.node_assignment import assign_nodes
from src.refinement.ambiguity import calculate_ambiguity_score
from src.refinement.color_refinement import refinement_history
from src.refinement.individualization import individualize_pair, refine_fixed_rounds
from src.scoring.structural_score import calculate_structural_similarity

SELECTIONS = ("agir", "random", "none")


@dataclass(frozen=True)
class MatcherConfig:
    """Matcher settings. ``selection``: ``agir`` | ``random`` (ablation) | ``none`` (CR only)."""

    selection: str = "agir"
    max_individualizations: int = DEFAULT_MAX_INDIVIDUALIZATIONS
    max_branch_evaluations: int = DEFAULT_MAX_BRANCH_EVALUATIONS
    refine_rounds: int = DEFAULT_MATCHER_REFINE_ROUNDS
    seed: int = 0

    def validate(self) -> None:
        if self.selection not in SELECTIONS:
            raise InvalidGraphError(f"selection must be one of {SELECTIONS}, got {self.selection!r}")
        for name in ("max_individualizations", "max_branch_evaluations", "refine_rounds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InvalidGraphError(f"{name} must be a non-negative int")


@dataclass
class PairStep:
    """One accepted paired individualization."""

    step: int
    reference_node: str
    observed_node: str
    ambiguity_score: float
    candidate_pairs_before: int
    candidate_pairs_after: int
    covered_before: int
    covered_after: int


@dataclass
class MatchDetails:
    """Full matcher output: the blueprint ``MatchResult`` plus diagnostics."""

    match: MatchResult
    trace: list[PairStep] = field(default_factory=list)
    working_depth: int = -1
    candidate_map: dict[str, list[str]] = field(default_factory=dict)
    branch_evaluations: int = 0


def _coverage(candidates: dict[str, list[str]]) -> int:
    return sum(1 for c in candidates.values() if c)


def _pairs(candidates: dict[str, list[str]]) -> int:
    return sum(len(c) for c in candidates.values())


def _check(graph: TemporalGraph, label: str) -> None:
    if not isinstance(graph, TemporalGraph):
        raise InvalidGraphError(f"{label} must be a TemporalGraph, got {type(graph).__name__}")


def _finish(reference, observed, mapping, candidates, trace, depth, evaluations) -> MatchDetails:
    ref_nodes, obs_nodes = set(reference.graph.nodes), set(observed.graph.nodes)
    matched = sorted(mapping)
    if ref_nodes and matched:
        uniqueness = sum(1.0 / max(1, len(candidates.get(u, [None]))) for u in matched) / len(matched)
        confidence = (len(matched) / len(ref_nodes)) * uniqueness
    else:
        confidence = 0.0
    result = MatchResult(
        similarity=0.0,
        node_mapping=dict(mapping),
        matched_nodes=matched,
        unmatched_observed_nodes=sorted(obs_nodes - set(mapping.values())),
        unmatched_reference_nodes=sorted(ref_nodes - set(mapping)),
        individualization_count=len(trace),
        confidence=max(0.0, min(1.0, confidence)),
    )
    result.similarity = calculate_structural_similarity(reference, observed, result)
    return MatchDetails(result, trace, depth, candidates, evaluations)


def match_graphs_detailed(
    reference: TemporalGraph, observed: TemporalGraph, config: MatcherConfig | None = None
) -> MatchDetails:
    """Run the matching pipeline and return diagnostics as well as the result."""
    config = config or MatcherConfig()
    config.validate()
    _check(reference, "reference")
    _check(observed, "observed")
    rg, og = reference.graph, observed.graph
    if rg.number_of_nodes() == 0 or og.number_of_nodes() == 0:
        return _finish(reference, observed, {}, {}, [], -1, 0)

    hist_r, hist_o = refinement_history(rg), refinement_history(og)
    ref_pos, obs_pos = relative_first_seen(rg), relative_first_seen(og)
    best_cov, depth = -1, 0
    for d in range(min(len(hist_r), len(hist_o))):
        cov = _coverage(generate_candidates(rg, og, hist_r[d], hist_o[d], allow_relaxed=False))
        if cov >= best_cov:  # ">=": prefer the deepest round at equal coverage
            best_cov, depth = cov, d
    colors_r, colors_o = hist_r[depth], hist_o[depth]
    candidates = generate_candidates(rg, og, colors_r, colors_o)

    trace: list[PairStep] = []
    evaluations = 0
    rng = random.Random(config.seed)
    exhausted: set[str] = set()
    while config.selection != "none" and len(trace) < config.max_individualizations \
            and evaluations < config.max_branch_evaluations:
        classes: dict[str, list[str]] = {}
        for u, cands in sorted(candidates.items()):
            if len(cands) > 1 and colors_r[u] not in exhausted:
                classes.setdefault(colors_r[u], []).append(u)
        if not classes:
            break
        scored = sorted(((calculate_ambiguity_score(rg, nodes), color) for color, nodes in classes.items()),
                        key=lambda item: (-item[0], item[1]))
        if config.selection == "agir":
            scored = [s for s in scored if s[0] >= DEFAULT_AMBIGUITY_THRESHOLD]
            if not scored:
                break
            score, color = scored[0]
            u = sorted(classes[color])[0]
            options = candidates[u][:DEFAULT_MAX_CANDIDATES_PER_CLASS]
        else:  # random ablation: random class, node and partner, no usefulness check
            color = rng.choice(sorted(classes))
            score = calculate_ambiguity_score(rg, classes[color])
            u = rng.choice(sorted(classes[color]))
            options = [rng.choice(candidates[u])]

        before = (_coverage(candidates), _pairs(candidates))
        best = None
        for v in options:
            if evaluations >= config.max_branch_evaluations:
                break
            evaluations += 1
            new_r, new_o = individualize_pair(colors_r, u, colors_o, v)
            new_r = refine_fixed_rounds(rg, new_r, config.refine_rounds)
            new_o = refine_fixed_rounds(og, new_o, config.refine_rounds)
            new_cands = generate_candidates(rg, og, new_r, new_o)
            key = (_coverage(new_cands), -_pairs(new_cands))
            # identity-free tie-break among equally good partners: temporal alignment
            rank = key + (-abs(ref_pos[u] - obs_pos[v]),)
            if best is None or rank > best[0]:
                best = (rank, v, new_r, new_o, new_cands)
        if best is None:
            break
        rank, v, new_r, new_o, new_cands = best
        key = rank[:2]
        helpful = key[0] >= before[0] and -key[1] < before[1]
        if config.selection == "agir" and not helpful:
            exhausted.add(color)
            continue
        trace.append(PairStep(len(trace) + 1, u, v, score, before[1], -key[1], before[0], key[0]))
        colors_r, colors_o, candidates = new_r, new_o, new_cands
        exhausted.clear()

    mapping = assign_nodes(candidates, rg, og, colors_r, colors_o)
    return _finish(reference, observed, mapping, candidates, trace, depth, evaluations)


def match_graphs(reference: TemporalGraph, observed: TemporalGraph) -> MatchResult:
    """Match ``observed`` against ``reference`` with the default (AGIR) config."""
    return match_graphs_detailed(reference, observed).match
