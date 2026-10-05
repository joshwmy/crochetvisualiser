"""Errors raised while building or validating a stitch graph."""

from __future__ import annotations


class StitchGraphError(Exception):
    """Base class for stitch-graph construction/validation failures."""


class GraphBuildError(StitchGraphError):
    """Raised when a compiled ``Pattern`` cannot be expanded into a graph.

    This should never happen for a pattern that already passed
    :func:`crochet_reconstruction.validation.validator.validate` — it exists
    as a defensive invariant check, not a normal user-facing error path.
    """


class GraphValidationError(StitchGraphError):
    """Raised when a built :class:`~crochet_reconstruction.graph.models.StitchGraph`
    fails an invariant check. A graph that fails validation must never reach
    the geometry or rendering stages.
    """
