"""Centralised configuration constants for RefineMatch.

Every tunable default lives here so that no module needs unexplained magic
numbers. Values owned by other team members (matching, scoring, ambiguity)
are *provisional placeholders*: they exist so shared code can import a name,
and they MUST be tuned on validation data before any experimental claim is
made. They are not empirically derived.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

# --------------------------------------------------------------------------- #
# Color Refinement (Member 1)
# --------------------------------------------------------------------------- #

#: Upper bound on refinement rounds. 1-WL always stabilises within ``n`` rounds
#: for an ``n``-node graph; real communication graphs typically stabilise in a
#: handful. 100 is a safety cap that is far above realistic need.
DEFAULT_MAX_REFINEMENT_ITERATIONS: Final[int] = 100

#: Number of hex characters kept from the SHA-256 digest used as a color label.
#: 32 hex chars = 128 bits, which makes accidental collisions negligible for
#: project-scale graphs (it is not a cryptographic guarantee after truncation).
COLOR_DIGEST_HEX_LENGTH: Final[int] = 32

#: Initial refinement iterations count for round-0 partitions.
DEFAULT_INITIAL_REFINEMENT_ITERATIONS: Final[int] = 0

# --------------------------------------------------------------------------- #
# Identity abstraction (Member 1)
# --------------------------------------------------------------------------- #

#: Prefix for abstract identifiers, producing labels such as ``N_0001``.
DEFAULT_IDENTITY_PREFIX: Final[str] = "N"

#: Zero-padding width for the numeric part of abstract identifiers. Larger
#: graphs simply produce longer numbers; nothing is truncated.
IDENTITY_INDEX_WIDTH: Final[int] = 4

# --------------------------------------------------------------------------- #
# Graph construction (Member 1)
# --------------------------------------------------------------------------- #

#: ``node_type`` assigned when the caller gives no explicit typing. A generic
#: event log does not reveal real-world roles, so we deliberately do not guess.
DEFAULT_NODE_TYPE: Final[str] = "host"

#: Value of the ``direction`` edge attribute: edges always point from the
#: event source to the event destination.
EDGE_DIRECTION_SOURCE_TO_DESTINATION: Final[str] = "source_to_destination"

#: Largest valid TCP/UDP port number (used for EventRecord validation).
MAX_PORT: Final[int] = 65535

# --------------------------------------------------------------------------- #
# Temporal analysis (shared; used by Member 3)
# --------------------------------------------------------------------------- #

#: Default temporal window length in seconds (5 minutes). Provisional.
DEFAULT_TEMPORAL_WINDOW_SECONDS: Final[int] = 300

# --------------------------------------------------------------------------- #
# Matching / scoring / AGIR thresholds (owned by Members 2 and 3; PROVISIONAL)
# --------------------------------------------------------------------------- #

#: Minimum structural similarity to call two graphs a match. Provisional.
DEFAULT_MATCH_THRESHOLD: Final[float] = 0.70

#: Risk score at or above which an analyst-review alert is raised. Provisional.
DEFAULT_RISK_THRESHOLD: Final[float] = 0.60

#: Ambiguity score above which a color class is considered worth
#: individualizing. Provisional.
DEFAULT_AMBIGUITY_THRESHOLD: Final[float] = 0.30

#: Maximum number of individualization steps AGIR may spend. Provisional.
DEFAULT_MAX_INDIVIDUALIZATIONS: Final[int] = 5

# --------------------------------------------------------------------------- #
# Added for Members 2-4 integration (all PROVISIONAL heuristics, not tuned on
# real data; see README "Limitations").
# --------------------------------------------------------------------------- #

#: Refinement rounds run on BOTH graphs after a paired individualization. A
#: fixed count (never "until stable") keeps colors from the two graphs
#: comparable, because content-addressed colors are only comparable per round.
DEFAULT_MATCHER_REFINE_ROUNDS: Final[int] = 2

#: Max nodes of an ambiguous class evaluated as individualization candidates.
DEFAULT_MAX_CANDIDATES_PER_CLASS: Final[int] = 8

#: Hard cap on branch evaluations per match (computation budget).
DEFAULT_MAX_BRANCH_EVALUATIONS: Final[int] = 200

#: Assignment pairs scoring below this local compatibility are discarded.
DEFAULT_MIN_ASSIGNMENT_SCORE: Final[float] = 0.5

#: Final-score cut between "low" and "medium" risk levels. Provisional.
DEFAULT_MEDIUM_RISK_THRESHOLD: Final[float] = 0.40

#: Default risk weights (structural, temporal, frequency, contrastive). They
#: sum to 1. Provisional: use ``tune_weights_and_threshold`` on validation data.
DEFAULT_RISK_WEIGHTS: Final[tuple[float, float, float, float]] = (0.35, 0.25, 0.15, 0.25)

#: Minimum Jaccard overlap of edge-label profiles for a RELAXED match candidate
#: (tolerates missing and extra edges around a node). Provisional.
DEFAULT_RELAXED_MIN_PROFILE_OVERLAP: Final[float] = 0.5

#: Weight of the identity-free temporal tie-break (relative first-seen position)
#: used only to choose between otherwise equally good candidates.
TEMPORAL_TIEBREAK_WEIGHT: Final[float] = 1e-3

# --------------------------------------------------------------------------- #
# Synthetic telemetry generator constants (Member 3)
# --------------------------------------------------------------------------- #

#: Minimum ephemeral port for synthetic client events.
DEFAULT_MIN_PORT: Final[int] = 1024

#: Bounds for jitter applied to event counts: (min_factor, max_factor).
SYNTHETIC_COUNT_JITTER_BOUNDS: Final[tuple[float, float]] = (0.8, 1.25)

#: Bounds for start time jitter in seconds: (min_offset, max_offset).
SYNTHETIC_START_JITTER_SECONDS: Final[tuple[float, float]] = (0.0, 2.0)

#: Bounds for interval jitter: (min_factor, max_factor).
SYNTHETIC_INTERVAL_JITTER_BOUNDS: Final[tuple[float, float]] = (0.85, 1.15)

#: Relative standard deviation for synthetic byte volumes.
SYNTHETIC_BYTE_VARIANCE_RATIO: Final[float] = 0.2

#: Bounds for synthetic event duration in seconds: (min_duration, max_duration).
SYNTHETIC_DURATION_BOUNDS: Final[tuple[float, float]] = (0.01, 2.0)

#: Decimal precision for synthetic duration rounding.
SYNTHETIC_DURATION_ROUNDING_DIGITS: Final[int] = 3

#: Default synthetic base timestamp.
DEFAULT_SYNTHETIC_BASE_TIME: Final[datetime] = datetime(2024, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
