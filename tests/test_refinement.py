import numpy as np
import pytest

from src.core.models import make_event as ev
from src.ingestion.synthetic import SyntheticEnterprise, generate_benchmark
from src.refinement.temporal import TemporalColorRefiner, static_color_refinement, temporal_color_refinement


def chain(order):
    t1, t2 = order
    return [ev(t1, "x", "y", "auth_remote"), ev(t2, "y", "z", "auth_remote")]


def test_tcr_separates_causal_from_noncausal_chain_static_wl_does_not():
    causal, noncausal = sorted(chain((1, 2)), key=lambda e: e.ts), sorted(chain((2, 1)), key=lambda e: e.ts)
    assert temporal_color_refinement(causal, {}).node_colors["z"] != temporal_color_refinement(noncausal, {}).node_colors["z"]
    assert static_color_refinement(causal, {}).node_colors["z"] == static_color_refinement(noncausal, {}).node_colors["z"]


def test_colours_are_name_independent():
    a = [ev(1, "a", "b", "dns"), ev(2, "b", "c", "conn")]
    b = [ev(1, "p", "q", "dns"), ev(2, "q", "r", "conn")]
    ca, cb = temporal_color_refinement(a, {}).node_colors, temporal_color_refinement(b, {}).node_colors
    assert [ca[k] for k in "abc"] == [cb[k] for k in "pqr"]


@pytest.mark.parametrize("mode", ["exact", "log", "set"])
def test_incremental_equals_batch(mode):
    ent = SyntheticEnterprise(seed=1)
    w = generate_benchmark(0, 1, 0, seed=2, enterprise=ent)[0]
    _, batch = temporal_color_refinement(w.events, ent.roles, depth=3, multiplicity=mode, return_levels=True)
    inc = TemporalColorRefiner(ent.roles, depth=3, multiplicity=mode)
    for e in w.events:
        inc.add_event(e)
    assert inc.final_levels() == batch


def test_ties_are_handled_identically():
    evs = [ev(5, "a", "b", "conn"), ev(5, "b", "c", "conn"), ev(5, "c", "a", "conn"), ev(6, "a", "a", "dns")]
    _, batch = temporal_color_refinement(evs, {}, return_levels=True)
    inc = TemporalColorRefiner({})
    for e in evs:
        inc.add_event(e)
    assert inc.final_levels() == batch


def test_append_locality():
    """P2: a new (latest) event changes the final colours of its two endpoints only."""
    ent = SyntheticEnterprise(seed=3)
    w = generate_benchmark(1, 0, 0, seed=4, enterprise=ent)[0]
    inc = TemporalColorRefiner(ent.roles)
    for e in w.events:
        inc.add_event(e)
    before = inc.final_levels()
    new = ev(w.events[-1].ts + 1, "WS001", "WS002", "auth_remote")
    inc.add_event(new)
    after = inc.final_levels()
    for k in range(len(before)):
        changed = {v for v in before[k] if before[k][v] != after[k].get(v)}
        assert changed <= {"WS001", "WS002"}


def test_out_of_order_rejected():
    inc = TemporalColorRefiner({})
    inc.add_event(ev(10, "a", "b", "conn"))
    with pytest.raises(ValueError):
        inc.add_event(ev(5, "a", "b", "conn"))
