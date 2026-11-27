import numpy as np
import pytest

from src.core.models import make_event as ev
from src.graph.builder import GraphIndex, build_temporal_graph, infer_roles, windows
from src.ingestion.synthetic import ATTACK_KINDS, SyntheticEnterprise, generate_benchmark
from src.matching.matcher import PatternMatcher, periodic_chain
from src.matching.pattern import EdgeSpec, NodeSpec, Pattern
from src.matching.templates import attack_templates, template_library

ROLES = {"a": "workstation", "b": "workstation", "c": "server", "j": "jumphost", "adm": "admin_ws"}


def idx(events, roles=ROLES):
    return GraphIndex(build_temporal_graph(sorted(events, key=lambda e: e.ts), roles))


def test_lateral_chain_requires_causal_order():
    p = template_library()["lateral_movement"]
    good = idx([ev(1, "a", "b", "auth_remote"), ev(2, "b", "c", "auth_remote")])
    bad = idx([ev(2, "a", "b", "auth_remote"), ev(1, "b", "c", "auth_remote")])
    assert PatternMatcher(good).match(p).similarity == 1.0
    assert PatternMatcher(bad).match(p).similarity < 1.0
    assert PatternMatcher(bad, use_temporal=False).match(p).similarity == 1.0


def test_relaxation_gives_partial_similarity():
    p = template_library()["lateral_movement"]
    r = PatternMatcher(idx([ev(1, "a", "b", "auth_remote")])).match(p)
    assert 0 < r.similarity < 1


def test_injectivity():
    p = Pattern("t", "attack", {"x": NodeSpec(), "y": NodeSpec()}, [EdgeSpec("x", "y", {"conn"})])
    r = PatternMatcher(idx([ev(1, "a", "a", "conn")])).match(p, relax=False)
    assert r.similarity == 0


def test_individualization_resolves_symmetric_chains():
    evs = []
    hosts = [f"w{i}" for i in range(9)]
    for i in range(0, 9, 3):
        evs += [ev(10 + i, hosts[i], hosts[i + 1], "auth_remote"), ev(20 + i, hosts[i + 1], hosts[i + 2], "auth_remote")]
    ix = idx(evs, {h: "workstation" for h in hosts})
    p = template_library()["lateral_movement"]
    r = PatternMatcher(ix, max_individualizations=2).match(p)
    assert r.similarity == 1.0 and r.exhaustive and sum(e.score == 1.0 for e in r.embeddings) == 3
    greedy = PatternMatcher(ix, max_individualizations=0).match(p)
    assert not greedy.exhaustive


def test_leaf_compression_counts_alternatives():
    evs = [ev(i, "s", f"t{i}", "conn") for i in range(20)]
    roles = {"s": "workstation", **{f"t{i}": "workstation" for i in range(20)}}
    r = PatternMatcher(idx(evs, roles)).match(template_library()["network_scan"])
    assert r.similarity == 1.0 and r.embeddings[0].alternatives == {"t": 20}


def test_periodic_chain_survives_insertions():
    beacons = [60.0 * i for i in range(12)]
    noisy = sorted(beacons + [7.0, 95.0, 333.3, 401.0])
    assert len(periodic_chain(beacons, 0.1)) == 12
    assert len(periodic_chain(noisy, 0.1)) >= 12


@pytest.mark.parametrize("kind", ATTACK_KINDS)
def test_each_attack_is_matched(kind):
    ent = SyntheticEnterprise(seed=5)
    w = generate_benchmark(0, 1, 0, seed=6, enterprise=ent)[ATTACK_KINDS.index(kind)]
    m = PatternMatcher(GraphIndex(build_temporal_graph(w.events, ent.roles)))
    r = m.match(template_library()[kind])
    assert r.similarity == 1.0
    assert any(set(e.mapping.values()) & w.attack_nodes for e in r.embeddings)


def test_pattern_json_roundtrip_and_validation():
    for p in template_library().values():
        assert p.validate() == []
        q = Pattern.from_json(p.to_json())
        assert q.to_dict() == p.to_dict()
    bad = Pattern("b", "attack", {"x": NodeSpec(roles={"wizard"})}, [EdgeSpec("x", "y", {"teleport"})])
    assert len(bad.validate()) >= 3


def test_role_inference_and_windows():
    evs = [ev(i, f"w{i % 7}", "DC", "kerberos_tgs") for i in range(20)] + [ev(30, "w1", "w2", "auth_remote")]
    roles = infer_roles(evs)
    assert roles["DC"] == "dc" and roles["w1"] == "workstation"
    assert sum(len(x[2]) for x in windows(evs, size=10)) == len(evs)
