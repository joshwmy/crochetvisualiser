"""Structured exceptions raised before a pattern reaches the validator.

These are distinct from :mod:`crochet_reconstruction.validation`, which
produces a severity-ranked report *about* an already-compiled
:class:`~crochet_reconstruction.domain.pattern.Pattern`. Exceptions in this
module are raised earlier, while fitting parameters to a template, when no
compiled pattern can be produced at all (e.g. no repeat-compatible stitch
count exists within the declared dimensional tolerance). Pydantic's own
``ValidationError`` continues to cover malformed/out-of-range raw inputs.
"""

from __future__ import annotations


class CrochetReconstructionError(Exception):
    """Base class for all domain-level errors raised by the engine."""


class UnsupportedConstructionError(CrochetReconstructionError):
    """Raised when a construction style has no Phase 1 engine support."""


class UnsupportedDimensionsError(CrochetReconstructionError):
    """Raised when requested measurements/gauge cannot satisfy the template.

    Examples: no repeat-compatible stitch count within tolerance, or the
    computed body round count is less than one after crown and brim are
    accounted for.
    """


class TemplateRangeError(CrochetReconstructionError):
    """Raised when an input falls outside the template's supported range."""
