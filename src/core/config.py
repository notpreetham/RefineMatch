"""Centralized configuration and thresholds for RefineMatch."""

DEFAULT_MAX_REFINEMENT_ITERATIONS = 10
DEFAULT_MAX_INDIVIDUALIZATIONS = 3          # max depth of individualization (branching) in the matcher
DEFAULT_MAX_BRANCHES = 64                   # max candidates tried per individualization point
DEFAULT_MAX_EMBEDDINGS = 16                 # embeddings kept per pattern (used by certificates)
DEFAULT_SEARCH_BUDGET = 5000                # max search nodes per pattern match
DEFAULT_MATCH_THRESHOLD = 0.65              # alert threshold on the contrastive score (> single-step partial match)
DEFAULT_AMBIGUITY_THRESHOLD = 0.5
DEFAULT_TEMPORAL_WINDOW_SECONDS = 3600      # 1 hour window
DEFAULT_RISK_THRESHOLD = 0.8
DEFAULT_IDENTITY_PREFIX = "Node_"

# Temporal colour refinement
DEFAULT_TCR_DEPTH = 3                       # refinement rounds (receptive field in time-respecting hops)
DEFAULT_MULTIPLICITY = "log"               # "exact" | "log" | "set" multiplicity semantics

# Contrastive scoring
DEFAULT_BENIGN_LAMBDA = 1.0                 # weight of benign explanation in the contrast
DEFAULT_NOVELTY_ALPHA = 0.85                # 1.0 disables the novelty modulation; novelty can move a score by <= 15%

RISK_LEVELS = [(0.8, "critical"), (0.6, "high"), (0.35, "medium"), (0.0, "low")]

# Event-type vocabulary used across ingestion, templates and the LLM template generator
EVENT_TYPES = [
    "auth_remote", "kerberos_tgt", "kerberos_tgs", "ldap", "dns",
    "http", "http_upload", "smb_file", "conn",
]
ROLES = [
    "workstation", "admin_ws", "helpdesk", "server", "dc", "dns", "fileserver",
    "jumphost", "monitoring", "backup", "external", "saas",
]
EXTERNAL_ROLES = {"external", "saas"}
