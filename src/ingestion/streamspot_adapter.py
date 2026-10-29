"""StreamSpot dataset adapter.

Parses official StreamSpot TSV/CSV provenance graphs into the RefineMatch
TemporalGraph data contract.

Format (tab-separated, headerless):
    source_id, source_type, destination_id, destination_type, edge_type, graph_id
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import networkx as nx

from src.core.config import EDGE_DIRECTION_SOURCE_TO_DESTINATION
from src.core.exceptions import InvalidGraphError
from src.core.models import EventRecord, GraphEdge, GraphNode, TemporalGraph

# Base instant for synthetic timestamps (StreamSpot records lack native timestamps)
STREAMSPOT_BASE_TIME = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def parse_streamspot_file(
    filepath: str,
    target_graph_id: str,
    base_time: Optional[datetime] = None,
    time_step_seconds: float = 1.0,
) -> TemporalGraph:
    """Parse a StreamSpot TSV file for a specific target_graph_id.

    Args:
        filepath: Path to the StreamSpot dataset file.
        target_graph_id: Identifier of the specific graph to extract.
        base_time: Starting timestamp for synthesized events (defaults to STREAMSPOT_BASE_TIME).
        time_step_seconds: Increment between consecutive event timestamps.

    Returns:
        A validated TemporalGraph dataclass instance representing the target graph.
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"StreamSpot dataset file not found: {filepath}")

    di_graph = nx.DiGraph()
    events: List[EventRecord] = []
    current_time = base_time or STREAMSPOT_BASE_TIME
    time_delta = timedelta(seconds=time_step_seconds)
    target_str = str(target_graph_id).strip()

    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Support both tab-separated and comma-separated rows
            parts = line.split("\t") if "\t" in line else [p.strip() for p in line.split(",")]
            if len(parts) < 6:
                continue

            src_id = parts[0].strip()
            src_type = parts[1].strip() or "node"
            dst_id = parts[2].strip()
            dst_type = parts[3].strip() or "node"
            edge_type = parts[4].strip() or "flow"
            graph_id = parts[5].strip()

            if graph_id != target_str:
                continue

            # Add source node if missing
            if not di_graph.has_node(src_id):
                node_obj = GraphNode(node_id=src_id, node_type=src_type, original_id=src_id)
                di_graph.add_node(
                    node_obj.node_id,
                    node_type=node_obj.node_type,
                    original_id=node_obj.original_id,
                    role=None,
                )
            else:
                # Update node type if previous was generic
                if di_graph.nodes[src_id].get("node_type") == "node" and src_type != "node":
                    di_graph.nodes[src_id]["node_type"] = src_type

            # Add destination node if missing
            if not di_graph.has_node(dst_id):
                node_obj = GraphNode(node_id=dst_id, node_type=dst_type, original_id=dst_id)
                di_graph.add_node(
                    node_obj.node_id,
                    node_type=node_obj.node_type,
                    original_id=node_obj.original_id,
                    role=None,
                )
            else:
                if di_graph.nodes[dst_id].get("node_type") == "node" and dst_type != "node":
                    di_graph.nodes[dst_id]["node_type"] = dst_type

            event_time = current_time
            current_time += time_delta

            # Record event
            event = EventRecord(
                timestamp=event_time,
                source=src_id,
                destination=dst_id,
                event_type=edge_type,
            )
            events.append(event)

            # Update or create edge in nx.DiGraph
            if di_graph.has_edge(src_id, dst_id):
                edge_data = di_graph[src_id][dst_id]
                edge_data["weight"] += 1
                edge_data["last_seen"] = event_time
                edge_data["edge_types"][edge_type] = edge_data["edge_types"].get(edge_type, 0) + 1
            else:
                edge_obj = GraphEdge(
                    source=src_id,
                    destination=dst_id,
                    edge_type=edge_type,
                    direction=EDGE_DIRECTION_SOURCE_TO_DESTINATION,
                    weight=1,
                    first_seen=event_time,
                    last_seen=event_time,
                )
                di_graph.add_edge(
                    src_id,
                    dst_id,
                    edge_type=edge_obj.edge_type,
                    edge_types={edge_type: 1},
                    direction=edge_obj.direction,
                    weight=edge_obj.weight,
                    first_seen=edge_obj.first_seen,
                    last_seen=edge_obj.last_seen,
                    bytes_total=None,
                    duration=None,
                    protocol=None,
                )

    # Attach graph metadata
    di_graph.graph["graph_id"] = target_str
    di_graph.graph["source"] = "streamspot"

    start_time = events[0].timestamp if events else None
    end_time = events[-1].timestamp if events else None

    return TemporalGraph(
        graph=di_graph,
        events=events,
        start_time=start_time,
        end_time=end_time,
    )


def list_streamspot_graph_ids(filepath: str) -> list[str]:
    """Return a sorted list of unique graph IDs present in a StreamSpot file."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"StreamSpot dataset file not found: {filepath}")

    graph_ids = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t") if "\t" in line else [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                graph_ids.add(parts[5].strip())

    return sorted(graph_ids)
