"""Built-in, MITRE ATT&CK-mapped attack templates and their benign look-alikes.

Design principle: **attack templates are deliberately broad** (high recall -- they describe the
behaviour, not a specific tool), and **benign templates are specific** sanctioned behaviours that
happen to share the same shape. The contrastive scorer only alerts on structure that an attack
template explains and no benign template explains.
"""

from typing import Dict, List

from src.matching.pattern import EdgeSpec, NodeSpec, Pattern

MB = 1_000_000


def attack_templates() -> List[Pattern]:
    return [
        Pattern(
            name="lateral_movement", kind="attack", tactic="lateral-movement",
            techniques=["T1021", "T1550.002"],
            description="Remote authentication chain: a host authenticates to a second host, which then "
                        "authenticates onward to a third (time-respecting).",
            nodes={"a": NodeSpec(internal=True), "b": NodeSpec(internal=True), "c": NodeSpec(internal=True)},
            edges=[EdgeSpec("a", "b", {"auth_remote"}, order=1, weight=1.0, essential=True),
                   EdgeSpec("b", "c", {"auth_remote"}, order=2, weight=1.5, essential=True)],
            max_span=3600, benign_counterparts=["admin_jump", "helpdesk_support"]),
        Pattern(
            name="kerberoasting", kind="attack", tactic="credential-access", techniques=["T1558.003", "T1087.002"],
            description="Directory enumeration followed by a burst of Kerberos service-ticket requests.",
            nodes={"a": NodeSpec(internal=True, not_roles={"dc"}), "d": NodeSpec(roles={"dc"})},
            edges=[EdgeSpec("a", "d", {"ldap"}, order=1, weight=0.5),
                   EdgeSpec("a", "d", {"kerberos_tgs"}, order=2, min_count=10, weight=2.0, essential=True)],
            max_span=900, benign_counterparts=["service_ticket_renewal"]),
        Pattern(
            name="network_scan", kind="attack", tactic="discovery", techniques=["T1046", "T1018"],
            description="One internal host opens short connections to many distinct internal hosts.",
            nodes={"s": NodeSpec(internal=True, min_out_distinct={"conn": 15}), "t": NodeSpec(internal=True)},
            edges=[EdgeSpec("s", "t", {"conn"}, order=1, weight=1.0, essential=True)],
            max_span=3600, benign_counterparts=["monitoring_sweep"]),
        Pattern(
            name="exfiltration", kind="attack", tactic="exfiltration", techniques=["T1041", "T1567", "T1039"],
            description="Bulk collection from a file server followed by a large upload to an external host.",
            nodes={"a": NodeSpec(internal=True), "f": NodeSpec(roles={"fileserver"}), "x": NodeSpec(internal=False)},
            edges=[EdgeSpec("a", "f", {"smb_file"}, order=1, min_bytes=50 * MB, weight=1.0),
                   EdgeSpec("a", "x", {"http_upload"}, order=2, min_bytes=100 * MB, weight=3.0, essential=True)],
            max_span=3600, benign_counterparts=["cloud_sync"]),
        Pattern(
            name="c2_beaconing", kind="attack", tactic="command-and-control", techniques=["T1071.001", "T1573"],
            description="Highly periodic outbound HTTP(S) to a single external endpoint.",
            nodes={"a": NodeSpec(internal=True), "x": NodeSpec(internal=False)},
            edges=[EdgeSpec("a", "x", {"http"}, order=1, min_count=8, periodic=True, max_cv=0.1, weight=1.0, essential=True)],
            max_span=3600, benign_counterparts=["update_polling"]),
    ]


def benign_templates() -> List[Pattern]:
    return [
        Pattern(
            name="admin_jump", kind="benign", tactic="administration",
            description="Administrator workstation -> jump host -> managed servers.",
            nodes={"a": NodeSpec(roles={"admin_ws"}), "j": NodeSpec(roles={"jumphost"}), "s": NodeSpec(internal=True)},
            edges=[EdgeSpec("a", "j", {"auth_remote"}, order=1), EdgeSpec("j", "s", {"auth_remote"}, order=2)]),
        Pattern(
            name="helpdesk_support", kind="benign", tactic="administration",
            description="Helpdesk remote session into a workstation.",
            nodes={"h": NodeSpec(roles={"helpdesk"}), "w": NodeSpec(internal=True)},
            edges=[EdgeSpec("h", "w", {"auth_remote"}, order=1)]),
        Pattern(
            name="monitoring_sweep", kind="benign", tactic="operations",
            description="Monitoring server health-checks many hosts.",
            nodes={"m": NodeSpec(roles={"monitoring"}, min_out_distinct={"conn": 5}), "t": NodeSpec(internal=True)},
            edges=[EdgeSpec("m", "t", {"conn"}, order=1)]),
        Pattern(
            name="cloud_sync", kind="benign", tactic="operations",
            description="User syncs file-server documents to a sanctioned SaaS storage provider.",
            nodes={"a": NodeSpec(internal=True), "f": NodeSpec(roles={"fileserver"}), "x": NodeSpec(roles={"saas"})},
            edges=[EdgeSpec("a", "f", {"smb_file"}, order=1), EdgeSpec("a", "x", {"http_upload"}, order=2)]),
        Pattern(
            name="service_ticket_renewal", kind="benign", tactic="operations",
            description="Application server refreshing service tickets for its service accounts.",
            nodes={"s": NodeSpec(roles={"server"}), "d": NodeSpec(roles={"dc"})},
            edges=[EdgeSpec("s", "d", {"ldap"}, order=1), EdgeSpec("s", "d", {"kerberos_tgs"}, order=2, min_count=5)]),
        Pattern(
            name="update_polling", kind="benign", tactic="operations",
            description="Software agent polling a sanctioned update/SaaS endpoint on a fixed schedule.",
            nodes={"a": NodeSpec(internal=True), "x": NodeSpec(roles={"saas"})},
            edges=[EdgeSpec("a", "x", {"http"}, order=1, min_count=4, periodic=True, max_cv=0.2)]),
        Pattern(
            name="backup_job", kind="benign", tactic="operations",
            description="Backup server pulling data from servers.",
            nodes={"b": NodeSpec(roles={"backup"}), "s": NodeSpec(internal=True)},
            edges=[EdgeSpec("b", "s", {"smb_file"}, order=1)]),
    ]


def template_library() -> Dict[str, Pattern]:
    return {p.name: p for p in attack_templates() + benign_templates()}
