"""Tests for src.refinement.color_refinement.

Hand-checkable graphs used below (all edges directed, edge type "e" unless noted):

* PATH5:  a -> b -> c -> d -> e
    degrees (in,out): a(0,1) b(1,1) c(1,1) d(1,1) e(1,0)
    round 0: {a} {b,c,d} {e}               -> 3 classes
    round 1: b sees pred a, c sees pred b, d sees succ e  -> all differ -> 5 classes
    round 2: no further split -> stable after 2 rounds
* STAR:   hub -> x, hub -> y, hub -> z      -> leaves x,y,z stay one class
* C6 vs 2xC3: every node has (in,out) = (1,1) -> one class forever, but the
  graphs are not isomorphic (1-WL limitation).
"""

import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import networkx as nx
import pytest

from src.core.exceptions import InvalidRefinementInputError
from src.core.models import EventRecord, RefinementResult, TemporalGraph
from src.graph.anonymizer import anonymize_graph
from src.graph.graph_builder import assign_node_attributes, build_temporal_graph
from src.refinement.color_refinement import (
    color_histogram,
    color_refine,
    get_color_classes,
    initialize_colors,
    refine_once,
    refinement_history,
    wl_equivalent,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2024, 1, 1)


def make_graph(edges, node_types=None):
    g = nx.DiGraph()
    for u, v, *rest in edges:
        etype = rest[0] if rest else "e"
        g.add_edge(u, v, edge_type=etype, edge_types={etype: 1}, weight=1)
    for node in g.nodes:
        g.nodes[node]["node_type"] = (node_types or {}).get(node, "host")
    return g


def class_sizes(colors):
    return sorted(len(v) for v in get_color_classes(colors).values())


def path5():
    return make_graph([("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")])


def cycle(names):
    return make_graph([(names[i], names[(i + 1) % len(names)]) for i in range(len(names))])


# ------------------------------ initial partition ------------------------------ #

def test_initial_partition_hand_checked():
    g = make_graph(
        [("c1", "s", "http"), ("c2", "s", "http"), ("s", "db", "sql")],
        {"c1": "client", "c2": "client", "s": "server", "db": "database"},
    )
    classes = get_color_classes(initialize_colors(g))
    assert sorted(classes.values()) == [["c1", "c2"], ["db"], ["s"]]


def test_initial_partition_path5():
    classes = get_color_classes(initialize_colors(path5()))
    assert sorted(classes.values()) == [["a"], ["b", "c", "d"], ["e"]]


def test_edge_type_histogram_splits_initial_partition():
    g = make_graph([("c1", "s", "http"), ("c2", "s", "ssh")])
    colors = initialize_colors(g)
    assert colors["c1"] != colors["c2"]


def test_node_type_splits_initial_partition():
    g = make_graph([("c1", "s"), ("c2", "s")], {"c1": "client", "c2": "laptop"})
    colors = initialize_colors(g)
    assert colors["c1"] != colors["c2"]


def test_missing_node_type_attribute_uses_default():
    g = nx.DiGraph()
    g.add_edge("u", "v", edge_type="e")
    assert initialize_colors(g)["u"] != initialize_colors(g)["v"]


# ------------------------------ refinement steps ------------------------------ #

def test_one_refinement_iteration_on_path5():
    g = path5()
    initial = initialize_colors(g)
    once = refine_once(g, initial)
    assert class_sizes(initial) == [1, 1, 3]
    assert class_sizes(once) == [1, 1, 1, 1, 1]


def test_refine_once_only_splits_never_merges():
    g = path5()
    initial = initialize_colors(g)
    once = refine_once(g, initial)
    for members in get_color_classes(once).values():
        assert len({initial[n] for n in members}) == 1


def test_incoming_vs_outgoing_neighbours_are_distinguished():
    # b has a source-like predecessor; d has a sink-like successor.
    colors = refine_once(path5(), initialize_colors(path5()))
    assert colors["b"] != colors["d"] and colors["b"] != colors["c"] != colors["d"]


def test_reversing_edge_direction_changes_colors():
    forward = color_refine(make_graph([("a", "b")])).node_colors
    backward = color_refine(make_graph([("b", "a")])).node_colors
    assert forward["a"] == backward["b"]  # source role
    assert forward["a"] != backward["a"]


def test_neighbour_multiplicity_matters():
    one = make_graph([("h", "x")])
    two = make_graph([("h", "x"), ("h", "y")])
    assert color_refine(one).node_colors["h"] != color_refine(two).node_colors["h"]


def test_self_loop_supported():
    g = make_graph([("a", "a"), ("a", "b")])
    result = color_refine(g)
    assert result.stable and set(result.node_colors) == {"a", "b"}


# ------------------------------ convergence ------------------------------ #

def test_convergence_on_path5():
    result = color_refine(path5())
    assert result.stable and result.iterations == 2
    assert class_sizes(result.node_colors) == [1, 1, 1, 1, 1]


def test_max_iterations_respected():
    capped = color_refine(path5(), max_iterations=1)
    assert capped.iterations == 1 and not capped.stable
    assert class_sizes(capped.node_colors) == [1, 1, 1, 1, 1]
    zero = color_refine(path5(), max_iterations=0)
    assert zero.iterations == 0 and not zero.stable
    assert zero.node_colors == initialize_colors(path5())


def test_stable_when_final_round_is_the_cap():
    assert color_refine(path5(), max_iterations=2).stable


def test_already_stable_initial_partition_takes_one_confirming_round():
    result = color_refine(cycle(["p", "q", "r"]))
    assert result.stable and result.iterations == 1


def test_empty_graph():
    result = color_refine(nx.DiGraph())
    assert (result.node_colors, result.color_classes, result.iterations, result.stable) == (
        {}, {}, 0, True)
    assert initialize_colors(nx.DiGraph()) == {}
    assert refine_once(nx.DiGraph(), {}) == {}


def test_single_isolated_node():
    g = nx.DiGraph()
    g.add_node("solo", node_type="host")
    result = color_refine(g)
    assert result.stable and list(result.node_colors) == ["solo"]


def test_stable_partition_is_a_fixed_point():
    g = make_graph([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")])
    result = color_refine(g)
    again = refine_once(g, result.node_colors)
    # Labels change (they are nested hashes) but the partition must not.
    as_partition = lambda classes: sorted(map(tuple, classes.values()))
    assert as_partition(get_color_classes(again)) == as_partition(result.color_classes)


def test_result_is_valid_refinement_result():
    result = color_refine(path5())
    result.validate()
    assert result.color_classes == get_color_classes(result.node_colors)


# ------------------------------ ambiguity ------------------------------ #

def test_ambiguous_classes_remain_for_symmetric_nodes():
    g = make_graph([("hub", "x"), ("hub", "y"), ("hub", "z")])
    result = color_refine(g)
    sizes = sorted(len(v) for v in result.color_classes.values())
    assert sizes == [1, 3]
    assert ["x", "y", "z"] in result.color_classes.values()


# ------------------------------ identity independence ------------------------------ #

def _events(names):
    a, b, c, d = names
    spec = [(a, b, "http"), (a, b, "http"), (b, c, "sql"), (b, d, "http"), (d, a, "reply")]
    return [EventRecord(T0 + timedelta(seconds=i), s, t, et) for i, (s, t, et) in enumerate(spec)]


def test_renamed_graphs_have_corresponding_colors():
    names1, names2 = ("10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"), ("w", "x", "y", "z")
    g1 = build_temporal_graph(_events(names1)).graph
    g2 = build_temporal_graph(_events(names2)).graph
    r1, r2 = color_refine(g1), color_refine(g2)
    assert r1.iterations == r2.iterations and r1.stable and r2.stable
    for old, new in zip(names1, names2):
        assert r1.node_colors[old] == r2.node_colors[new]
    assert color_histogram(r1.node_colors) == color_histogram(r2.node_colors)


def test_anonymized_graph_has_same_signatures_as_original():
    names = ("10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4")
    tg = build_temporal_graph(_events(names))
    anon = anonymize_graph(tg)
    original = color_refine(tg.graph).node_colors
    anonymised = color_refine(anon.graph).node_colors
    for node, attrs in anon.graph.nodes(data=True):
        assert anonymised[node] == original[attrs["original_id"]]


def test_original_id_and_role_do_not_influence_colors():
    tg = build_temporal_graph(_events(("a", "b", "c", "d")))
    baseline = color_refine(tg.graph).node_colors
    tagged = assign_node_attributes(tg, roles={"a": "gateway", "b": "db"})
    for i, node in enumerate(tagged.graph.nodes):
        tagged.graph.nodes[node]["original_id"] = f"secret-{random.Random(i).random()}"
    assert color_refine(tagged.graph).node_colors == baseline


def test_edge_weights_timestamps_and_bytes_do_not_influence_colors():
    tg = build_temporal_graph(_events(("a", "b", "c", "d")))
    baseline = color_refine(tg.graph).node_colors
    g = tg.graph.copy()
    for _, _, attrs in g.edges(data=True):
        attrs["weight"] *= 50
        attrs["bytes_total"] = 123456
    assert color_refine(g).node_colors == baseline


def test_node_and_edge_insertion_order_do_not_matter():
    edges = [("a", "b", "x"), ("b", "c", "y"), ("c", "a", "x"), ("a", "d", "y")]
    forward = make_graph(edges)
    shuffled = make_graph(list(reversed(edges)))
    assert color_refine(forward).node_colors == color_refine(shuffled).node_colors


def test_random_graphs_under_random_renaming_keep_signatures():
    rng = random.Random(2024)
    for _ in range(25):
        n = rng.randint(2, 9)
        g = nx.DiGraph()
        g.add_nodes_from(f"v{i}" for i in range(n))
        for _ in range(rng.randint(1, 2 * n)):
            u, v = rng.randrange(n), rng.randrange(n)
            etype = rng.choice(["p", "q"])
            g.add_edge(f"v{u}", f"v{v}", edge_type=etype, edge_types={etype: 1})
        for node in g.nodes:
            g.nodes[node]["node_type"] = rng.choice(["host", "server"])
        perm = list(range(n))
        rng.shuffle(perm)
        h = nx.relabel_nodes(g, {f"v{i}": f"zz{perm[i]}-{rng.random():.6f}" for i in range(n)})
        r_g, r_h = color_refine(g), color_refine(h)
        assert r_g.iterations == r_h.iterations
        assert color_histogram(r_g.node_colors) == color_histogram(r_h.node_colors)
        assert wl_equivalent(g, h)


# ------------------------------ determinism ------------------------------ #

def test_deterministic_within_process():
    g = path5()
    assert color_refine(g) == color_refine(g)
    assert list(color_refine(g).node_colors.items()) == list(color_refine(g).node_colors.items())


def test_deterministic_across_processes_with_different_hash_seeds():
    script = (
        "import json, networkx as nx\n"
        "from src.refinement.color_refinement import color_refine\n"
        "g = nx.DiGraph()\n"
        "for u, v in [('a','b'),('b','c'),('c','d'),('d','e')]:\n"
        "    g.add_edge(u, v, edge_type='e', edge_types={'e': 1})\n"
        "print(json.dumps(color_refine(g).node_colors, sort_keys=True))\n"
    )
    outputs = set()
    for seed in ("0", "1", "424242"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(PROJECT_ROOT))
        proc = subprocess.run(
            [sys.executable, "-c", script], cwd=PROJECT_ROOT, env=env,
            capture_output=True, text=True, check=True,
        )
        outputs.add(proc.stdout.strip())
    assert len(outputs) == 1


# ------------------------------ 1-WL limits ------------------------------ #

def test_one_wl_cannot_distinguish_c6_from_two_c3():
    c6 = cycle(["a", "b", "c", "d", "e", "f"])
    two_c3 = make_graph([("a", "b"), ("b", "c"), ("c", "a"), ("d", "e"), ("e", "f"), ("f", "d")])
    assert not nx.is_isomorphic(c6, two_c3)
    assert wl_equivalent(c6, two_c3)
    r6, r33 = color_refine(c6), color_refine(two_c3)
    assert sorted(r6.node_colors.values()) == sorted(r33.node_colors.values())
    assert len(r6.color_classes) == len(r33.color_classes) == 1


def test_one_wl_distinguishes_when_structures_really_differ():
    assert not wl_equivalent(path5(), cycle(["a", "b", "c", "d", "e"]))
    assert not wl_equivalent(cycle(["a", "b", "c"]), make_graph([("a", "b"), ("b", "c"), ("c", "b")]))
    assert not wl_equivalent(make_graph([("a", "b")]), make_graph([("a", "b", "other")]))


def test_wl_equivalent_requires_same_size_and_direction():
    assert not wl_equivalent(make_graph([("a", "b")]), make_graph([("a", "b"), ("c", "d")]))
    assert wl_equivalent(make_graph([("a", "b")]), make_graph([("x", "y")]))
    assert wl_equivalent(nx.DiGraph(), nx.DiGraph())


# ------------------------------ history / comparability ------------------------------ #

def test_history_matches_color_refine_and_initialize():
    g = path5()
    history = refinement_history(g)
    assert history[0] == initialize_colors(g)
    assert history[-1] == color_refine(g).node_colors
    assert len(history) - 1 == color_refine(g).iterations


def test_colors_from_different_rounds_differ_even_for_unchanged_partition():
    history = refinement_history(cycle(["p", "q", "r"]))
    assert history[0]["p"] != history[1]["p"]


def test_fixed_depth_colors_comparable_between_graph_and_larger_graph():
    small = make_graph([("a", "b"), ("b", "c")])
    large = make_graph([("a", "b"), ("b", "c"), ("c", "x"), ("x", "y")])
    # Depth-0 color of a pure source ("a": out 1, in 0) is the same in both graphs.
    assert refinement_history(small, 0)[0]["a"] == refinement_history(large, 0)[0]["a"]
    # Depth-1 color of "a" is also equal: its 1-hop view (one successor "b") is identical.
    # (Successor b has the same depth-0 color in both graphs: in 1, out 1.)
    assert refinement_history(small, 1)[1]["a"] == refinement_history(large, 1)[1]["a"]
    # Depth-0 color of "c" differs: in the small graph c is a sink, in the large one it is not.
    assert refinement_history(small, 0)[0]["c"] != refinement_history(large, 0)[0]["c"]


# ------------------------------ validation ------------------------------ #

def test_get_color_classes_groups_and_sorts():
    classes = get_color_classes({"b": "c2", "a": "c1", "c": "c1"})
    assert classes == {"c1": ["a", "c"], "c2": ["b"]}
    assert get_color_classes({}) == {}
    with pytest.raises(InvalidRefinementInputError):
        get_color_classes({"a": 3})


def test_refine_once_validates_color_coverage():
    g = make_graph([("a", "b")])
    with pytest.raises(InvalidRefinementInputError):
        refine_once(g, {"a": "c"})
    with pytest.raises(InvalidRefinementInputError):
        refine_once(g, {"a": "c", "b": "c", "z": "c"})
    with pytest.raises(InvalidRefinementInputError):
        refine_once(g, {"a": "c", "b": 1})
    with pytest.raises(InvalidRefinementInputError):
        refine_once(g, None)


def test_invalid_inputs_rejected():
    with pytest.raises(InvalidRefinementInputError):
        color_refine(nx.Graph())
    with pytest.raises(InvalidRefinementInputError):
        color_refine(nx.MultiDiGraph())
    with pytest.raises(InvalidRefinementInputError):
        color_refine(path5(), max_iterations=-1)
    with pytest.raises(InvalidRefinementInputError):
        color_refine(path5(), max_iterations="3")
    g = nx.DiGraph()
    g.add_edge(1, 2)
    with pytest.raises(InvalidRefinementInputError):
        color_refine(g)


def test_refinement_returns_official_refinement_result_dataclass():
    g = path5()
    init_res = initialize_colors(g)
    assert isinstance(init_res, RefinementResult)
    assert init_res.iterations == 0
    assert not init_res.stable
    assert isinstance(init_res.node_colors, dict)
    assert isinstance(init_res.color_classes, dict)

    once_res = refine_once(g, init_res)
    assert isinstance(once_res, RefinementResult)
    assert once_res.iterations == 1
    assert isinstance(once_res.node_colors, dict)
    assert isinstance(once_res.color_classes, dict)


def test_temporal_graph_auto_unpacked_in_color_refinement():
    now = datetime(2024, 1, 1)
    events = [
        EventRecord(now, "a", "b", "e"),
        EventRecord(now + timedelta(seconds=1), "b", "c", "e"),
    ]
    tg = build_temporal_graph(events)
    init_res = initialize_colors(tg)
    assert isinstance(init_res, RefinementResult)
    assert "a" in init_res.node_colors

    once_res = refine_once(tg, init_res)
    assert isinstance(once_res, RefinementResult)

    full_res = color_refine(tg)
    assert isinstance(full_res, RefinementResult)
    assert full_res.stable
