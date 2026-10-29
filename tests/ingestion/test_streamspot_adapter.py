"""Tests and verification for StreamSpot dataset adapter."""

import sys
import tempfile
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import networkx as nx
import pytest

from src.core.models import EventRecord, TemporalGraph
from src.ingestion.streamspot_adapter import (
    list_streamspot_graph_ids,
    parse_streamspot_file,
)
from src.refinement.color_refinement import color_refine


DUMMY_STREAMSPOT_TSV = """\
proc_101\tprocess\tfile_201\tfile\tread\tgraph_01
proc_101\tprocess\tsock_301\tsocket\tconnect\tgraph_01
sock_301\tsocket\thost_401\thost\tsendto\tgraph_01
proc_101\tprocess\tfile_201\tfile\tread\tgraph_01
proc_999\tprocess\tfile_888\tfile\twrite\tgraph_02
"""


def test_parse_streamspot_file_basic():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".tsv", encoding="utf-8") as f:
        f.write(DUMMY_STREAMSPOT_TSV)
        tsv_path = f.name

    try:
        # Verify graph IDs listing
        ids = list_streamspot_graph_ids(tsv_path)
        assert ids == ["graph_01", "graph_02"]

        # Parse target graph_01
        tg = parse_streamspot_file(tsv_path, target_graph_id="graph_01")

        # 1. Verification of TemporalGraph data contract
        assert isinstance(tg, TemporalGraph)
        assert isinstance(tg.graph, nx.DiGraph)
        assert isinstance(tg.events, list)
        assert len(tg.events) == 4
        assert tg.start_time is not None
        assert tg.end_time is not None
        assert tg.start_time <= tg.end_time

        # 2. Node attribute verification
        assert "proc_101" in tg.graph.nodes
        assert tg.graph.nodes["proc_101"]["node_type"] == "process"
        assert tg.graph.nodes["file_201"]["node_type"] == "file"
        assert tg.graph.nodes["sock_301"]["node_type"] == "socket"
        assert tg.graph.nodes["host_401"]["node_type"] == "host"
        assert tg.graph.number_of_nodes() == 4

        # 3. Edge attribute & aggregation verification
        assert tg.graph.number_of_edges() == 3
        edge_data = tg.graph["proc_101"]["file_201"]
        assert edge_data["weight"] == 2  # Two read events aggregated
        assert edge_data["edge_type"] == "read"
        assert edge_data["edge_types"] == {"read": 2}
        assert edge_data["direction"] == "source_to_destination"

        # 4. Color Refinement Compatibility
        ref_result = color_refine(tg)
        assert ref_result.stable is True
        assert len(ref_result.node_colors) == 4

        # 5. Non-existent graph returns empty TemporalGraph
        empty_tg = parse_streamspot_file(tsv_path, target_graph_id="graph_999")
        assert len(empty_tg.graph.nodes) == 0
        assert len(empty_tg.events) == 0
        assert empty_tg.start_time is None
        assert empty_tg.end_time is None

        print("\nAll StreamSpot adapter assertions passed successfully!")
    finally:
        Path(tsv_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_parse_streamspot_file_basic()
