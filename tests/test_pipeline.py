import json

import numpy as np
import pytest

from src.explanation.certificate import build_certificate, verify_certificate
from src.graph.streaming import StreamingDetector
from src.ingestion.loaders import load_csv, load_lanl_auth, load_lanl_flows, load_lanl_redteam
from src.ingestion.synthetic import ATTACK_KINDS, HARD_NEGATIVE_KINDS, SyntheticEnterprise, generate_benchmark, generate_campaign
from src.matching.matcher import PatternMatcher
from src.matching.templates import template_library
from src.pipeline import RefineMatch
from src.robustness.certify import INF, certify
from src.sharing.fingerprint import canonical_hash, export_package, import_package
from src.templates_llm.generator import generate_template, pattern_from_llm_json

THR = 0.65


@pytest.fixture(scope="module")
def setup():
    ent = SyntheticEnterprise(seed=0)
    rm = RefineMatch(ent.roles, threshold=THR).fit_baseline(
        [w.events for w in generate_benchmark(10, 0, 0, seed=100, enterprise=ent)])
    test = generate_benchmark(0, 1, 1, seed=300, enterprise=ent)
    return ent, rm, test


def test_attacks_alert_lookalikes_do_not(setup):
    ent, rm, test = setup
    for w in test:
        s = rm.analyze_window(w.events, w.start, w.end).score
        if w.is_attack:
            assert s >= THR, w.kind
        else:
            assert s < THR, w.kind


def test_benign_contrast_is_what_suppresses_lookalikes(setup):
    ent, _, test = setup
    rm0 = RefineMatch(ent.roles, threshold=THR, use_benign=False, use_novelty=False)
    fp = [w.kind for w in test if not w.is_attack and rm0.analyze_window(w.events).score >= THR]
    assert len(fp) >= 3  # without contrast most look-alikes alert


def test_certificates_verify_and_detect_tampering(setup):
    ent, rm, test = setup
    for w in [w for w in test if w.is_attack]:
        rep = rm.analyze_window(w.events, w.start, w.end)
        d = rep.detections[0]
        m = PatternMatcher(rep.index)
        cert = build_certificate(d, m, rm.scorer, certify(d, m, rm.scorer, THR))
        assert verify_certificate(cert, rep.index, d.pattern)[0]
        cert.evidence[-1]["destination"] = "NOPE"
        assert not verify_certificate(cert, rep.index, d.pattern)[0]


def test_insertion_never_lowers_attack_similarity(setup):
    ent, rm, test = setup
    rng = np.random.default_rng(0)
    from src.robustness.attacks import insert_noise
    for w in [w for w in test if w.is_attack]:
        base = rm.analyze_window(w.events)
        d = base.detections[0]
        noisy = insert_noise(w.events, sorted(w.attack_nodes)[:1], ent.internal, 100, rng)
        d2 = next(x for x in rm.analyze_window(noisy).detections if x.pattern.name == d.pattern.name)
        assert d2.score.attack_similarity >= d.score.attack_similarity - 1e-9


def test_lateral_movement_is_deletion_immune(setup):
    ent, rm, test = setup
    w = next(w for w in test if w.kind == "lateral_movement")
    rep = rm.analyze_window(w.events)
    d = rep.detections[0]
    c = certify(d, PatternMatcher(rep.index), rm.scorer, THR)
    assert c.deletion_lower_bound == INF and c.insertion_lower_bound == INF


def test_campaign_links_stages():
    events, stages, ent = generate_campaign(seed=11)
    rm = RefineMatch(ent.roles, threshold=THR).fit_baseline(
        [w.events for w in generate_benchmark(6, 0, 0, seed=12, enterprise=ent)])
    camps = rm.campaigns(rm.analyze_stream(events))
    assert camps and len(camps[0].tactics) >= 3


def test_streaming_detector_alerts():
    events, stages, ent = generate_campaign(seed=11)
    rm = RefineMatch(ent.roles, threshold=THR)
    alerts = StreamingDetector(rm, check_every=50).run(events)
    assert {a.pattern for a in alerts} >= {"network_scan", "kerberoasting", "lateral_movement"}


def test_sharing_roundtrip_signature_and_anonymity(setup):
    ent, rm, test = setup
    w = next(w for w in test if w.kind == "lateral_movement")
    rep = rm.analyze_window(w.events)
    pkg = export_package(rep.detections[0], PatternMatcher(rep.index), b"k")
    text = json.dumps(pkg)
    assert not any(h in text for h in w.attack_nodes)  # no identifiers leak
    t = import_package(json.loads(text), b"k")
    assert t is not None and canonical_hash(t) == pkg["canonical_hash"]
    assert import_package(json.loads(text), b"wrong-key") is None


class _FakeBlock:
    def __init__(self, text):
        self.type, self.text = "text", text


class _FakeResp:
    def __init__(self, text):
        self.content, self.stop_reason = [_FakeBlock(text)], "end_turn"


class _FakeClient:
    """Stands in for anthropic.Anthropic(): first draft is broken, second is valid."""

    def __init__(self, drafts):
        self.drafts, self.calls = list(drafts), []
        self.beta = self
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        return _FakeResp(json.dumps(self.drafts.pop(0)))


def _draft(role="workstation", src_dst=("a", "b")):
    return {"name": "rdp_hop", "tactic": "lateral-movement", "techniques": ["T1021.001"], "description": "x",
            "max_span_seconds": 3600,
            "nodes": [{"id": "a", "roles": [], "not_roles": [], "location": "internal", "min_out_distinct": []},
                      {"id": "b", "roles": [role], "not_roles": [], "location": "internal", "min_out_distinct": []},
                      {"id": "c", "roles": [], "not_roles": [], "location": "internal", "min_out_distinct": []}],
            "edges": [{"src": src_dst[0], "dst": src_dst[1], "event_types": ["auth_remote"], "order": 1, "min_count": 1,
                       "min_bytes": 0, "periodic": False, "weight": 1, "essential": True},
                      {"src": "b", "dst": "c", "event_types": ["auth_remote"], "order": 2, "min_count": 1,
                       "min_bytes": 0, "periodic": False, "weight": 1, "essential": True}],
            "benign_lookalikes": ["admin_jump"]}


def test_llm_generator_validation_loop(setup):
    ent, _, _ = setup
    benign = [w.events for w in generate_benchmark(4, 0, 0, seed=55, enterprise=ent)]
    bad = _draft(src_dst=("a", "a"))          # self-loop -> rejected
    client = _FakeClient([bad, _draft()])
    res = generate_template("RDP lateral movement", ent.roles, benign, client=client)
    assert res.accepted and res.rounds == 2 and res.feedback[0]
    assert client.calls[0]["output_config"]["format"]["type"] == "json_schema"


def test_loaders(tmp_path):
    auth = tmp_path / "auth.txt"
    auth.write_text("1,U1@D,U1@D,C1,C2,NTLM,Network,LogOn,Success\n"
                    "2,U1@D,U1@D,C2,C3,Kerberos,Network,LogOn,Success\n"
                    "3,U1@D,U1@D,C2,C9,Kerberos,Network,TGS,Success\n"
                    "4,U1@D,U1@D,C2,C2,Kerberos,Network,LogOn,Success\n")
    rt = tmp_path / "redteam.txt"
    rt.write_text("1,U1@D,C1,C2\n")
    evs = load_lanl_auth(str(auth), redteam=load_lanl_redteam(str(rt)))
    assert [e.event_type for e in evs] == ["auth_remote", "auth_remote", "kerberos_tgs"]
    assert evs[0].label == "attack:lateral_movement"
    flows = tmp_path / "flows.txt"
    flows.write_text("5,1,C1,N1,C7,443,6,10,90000000\n6,1,C1,N2,C8,53,17,1,80\n")
    assert [e.event_type for e in load_lanl_flows(str(flows))] == ["http_upload", "dns"]
    csvp = tmp_path / "conn.csv"
    csvp.write_text("ts,src,dst,dport,bytes\n10,a,b,445,100\n")
    e = load_csv(str(csvp), {"timestamp": "ts", "source": "src", "destination": "dst", "destination_port": "dport",
                             "bytes": "bytes"})[0]
    assert e.event_type == "smb_file"
