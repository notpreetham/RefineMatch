"""Member 1 demo: events -> graph -> anonymise -> Color Refinement -> comparison.

Run from the project root:  python examples/member1_demo.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import networkx as nx  # noqa: E402

from src.core.models import EventRecord  # noqa: E402
from src.graph.anonymizer import anonymize_graph, create_identity_mapping  # noqa: E402
from src.graph.graph_builder import assign_node_attributes, build_temporal_graph  # noqa: E402
from src.graph.temporal_graph import get_event_frequency, get_temporal_window  # noqa: E402
from src.refinement.color_refinement import color_refine, wl_equivalent  # noqa: E402

START = datetime(2024, 5, 1, 9, 0, 0)


def scenario(client, web, db, ext):
    """A tiny client -> web -> db flow plus an external callback, with arbitrary names."""
    spec = [(client, web, "http"), (client, web, "http"), (web, db, "sql"),
            (web, ext, "https"), (ext, client, "reply")]
    return [EventRecord(START + timedelta(seconds=10 * i), s, d, t) for i, (s, d, t) in enumerate(spec)]


def short(color):
    return color[:8]


def main():
    # Two environments: same behaviour, completely different machine identities.
    net_a = build_temporal_graph(scenario("10.0.0.5", "10.0.1.9", "10.0.2.3", "203.0.113.7"))
    net_b = build_temporal_graph(scenario("laptop-77", "srv-edge", "sqlbox", "partner.example"))

    # Node types must be supplied explicitly; they cannot be inferred from a CSV.
    net_a = assign_node_attributes(net_a, {"10.0.0.5": "client", "10.0.1.9": "server",
                                           "10.0.2.3": "database", "203.0.113.7": "external_service"})
    net_b = assign_node_attributes(net_b, {"laptop-77": "client", "srv-edge": "server",
                                           "sqlbox": "database", "partner.example": "external_service"})

    anon_a, anon_b = anonymize_graph(net_a), anonymize_graph(net_b)
    print("Identity mapping A:", create_identity_mapping(net_a))
    print("Frequency N_0001 -> N_0002 in A:", get_event_frequency(anon_a, "N_0001", "N_0002"))
    window = get_temporal_window(anon_a.events, START, START + timedelta(seconds=25))
    print("Events in first 25 s (half-open window):", len(window))

    res_a, res_b = color_refine(anon_a.graph), color_refine(anon_b.graph)
    print(f"\nA: iterations={res_a.iterations} stable={res_a.stable} classes={len(res_a.color_classes)}")
    print(f"B: iterations={res_b.iterations} stable={res_b.stable} classes={len(res_b.color_classes)}")
    for node in anon_a.graph.nodes:
        orig = anon_a.graph.nodes[node]["original_id"]
        print(f"  A {node} ({orig:>12}) color {short(res_a.node_colors[node])}")
    for node in anon_b.graph.nodes:
        orig = anon_b.graph.nodes[node]["original_id"]
        print(f"  B {node} ({orig:>12}) color {short(res_b.node_colors[node])}")
    same = sorted(res_a.node_colors.values()) == sorted(res_b.node_colors.values())
    print("Same structural signatures across different identities:", same)

    # The 1-WL limitation: not isomorphic, yet indistinguishable.
    def cyc(names):
        g = nx.DiGraph()
        for i, n in enumerate(names):
            g.add_edge(n, names[(i + 1) % len(names)], edge_type="e", edge_types={"e": 1})
        return g
    c6 = cyc(list("abcdef"))
    two_c3 = nx.compose(cyc(list("abc")), cyc(list("def")))
    print("\nC6 vs 2xC3 isomorphic?", nx.is_isomorphic(c6, two_c3),
          "| 1-WL equivalent?", wl_equivalent(c6, two_c3))


if __name__ == "__main__":
    main()
