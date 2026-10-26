"""Core data models shared across modules."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import networkx as nx


@dataclass
class EventRecord:
    timestamp: datetime
    source: str
    destination: str
    event_type: str
    protocol: Optional[str] = None
    source_port: Optional[int] = None
    destination_port: Optional[int] = None
    bytes: Optional[int] = None
    duration: Optional[float] = None


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    role: Optional[str] = None
    original_id: Optional[str] = None


@dataclass
class GraphEdge:
    source: str
    destination: str
    edge_type: str
    direction: str
    weight: int
    first_seen: datetime
    last_seen: datetime
    duration: Optional[float] = None
    bytes_total: Optional[int] = None
    protocol: Optional[str] = None


@dataclass
class TemporalGraph:
    graph: nx.DiGraph
    events: List[EventRecord]
    start_time: Optional[datetime]
    end_time: Optional[datetime]


@dataclass
class RefinementResult:
    node_colors: Dict[str, str]
    color_classes: Dict[str, List[str]]
    iterations: int
    stable: bool


@dataclass
class MatchResult:
    similarity: float
    node_mapping: Dict[str, str]
    matched_nodes: List[str]
    unmatched_observed_nodes: List[str]
    unmatched_reference_nodes: List[str]
    individualization_count: int
    confidence: float


@dataclass
class ScoreResult:
    structural_score: float
    temporal_score: float
    frequency_score: float
    attack_similarity: float
    benign_similarity: float
    contrastive_score: float
    risk_level: str
    