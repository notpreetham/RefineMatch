"""Exception hierarchy for RefineMatch.

All project exceptions derive from :class:`RefineMatchError`, and the concrete
ones also derive from :class:`ValueError` so generic ``except ValueError``
handlers keep working. Nothing here swallows errors; modules raise these with a
descriptive message and let the caller decide.
"""

from __future__ import annotations


class RefineMatchError(Exception):
    """Base class for all RefineMatch errors."""


class InvalidEventError(RefineMatchError, ValueError):
    """Raised when event data is malformed.

    Examples: non-datetime timestamp, empty source/destination/event_type,
    out-of-range port, negative bytes/duration, a non-``EventRecord`` object in
    an event list, or a mix of timezone-aware and naive timestamps.
    """


class InvalidTimeWindowError(InvalidEventError):
    """Raised when a temporal window is invalid.

    Examples: ``start_time > end_time``, non-datetime bounds, or bounds whose
    timezone-awareness is incompatible with the event timestamps.
    """


class InvalidGraphError(RefineMatchError, ValueError):
    """Raised when graph data is malformed or inconsistent.

    Examples: wrong graph class, multigraph, non-string node IDs, events that
    reference nodes missing from the graph, required attributes missing, or an
    attribute mapping naming unknown nodes.
    """


class InvalidRefinementInputError(RefineMatchError, ValueError):
    """Raised when Color Refinement input is invalid.

    Examples: a color mapping that does not cover exactly the graph's nodes,
    non-string colors, a negative iteration limit, or an unsupported graph type.
    """


class InvalidScoreInputError(RefineMatchError, ValueError):
    """Raised when a scoring function receives out-of-range or non-finite input.

    Examples: a similarity outside [0, 1], NaN, or risk weights that are
    negative or do not sum to 1.
    """
