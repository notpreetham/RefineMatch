"""Core data models shared across modules."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
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
    label: Optional[str] = None  # ground truth (e.g. "benign", "attack:lateral_movement"); never read by detectors

    @property
    def ts(self) -> float:
        return self.timestamp.timestamp()


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
    history: List[Dict[str, str]] = field(default_factory=list)  # colors per iteration (0 = initial)


@dataclass
class EvidenceEdge:
    """One observed event that satisfies one pattern edge."""
    pattern_src: str
    pattern_dst: str
    source: str
    destination: str
    event_type: str
    timestamp: float
    order: int


@dataclass
class MatchResult:
    similarity: float
    node_mapping: Dict[str, str]
    matched_nodes: List[str]
    unmatched_observed_nodes: List[str]
    unmatched_reference_nodes: List[str]
    individualization_count: int
    confidence: float
    pattern_name: str = ""
    evidence: List[EvidenceEdge] = field(default_factory=list)
    edge_coverage: float = 0.0
    temporal_score: float = 0.0
    exhaustive: bool = True
    embeddings: List[Any] = field(default_factory=list)  # matching.matcher.Embedding objects, best first
    trace: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScoreResult:
    structural_score: float
    temporal_score: float
    frequency_score: float
    attack_similarity: float
    benign_similarity: float
    contrastive_score: float
    risk_level: str
    best_benign: Optional[str] = None


def make_event(t: float, s: str, d: str, etype: str, nbytes: Optional[int] = None, label: Optional[str] = "benign",
               port: Optional[int] = None, duration: Optional[float] = None) -> EventRecord:
    """Convenience constructor from a POSIX timestamp."""
    from datetime import timezone
    return EventRecord(timestamp=datetime.fromtimestamp(float(t), tz=timezone.utc), source=s, destination=d,
                       event_type=etype, bytes=nbytes, label=label, destination_port=port, duration=duration)
