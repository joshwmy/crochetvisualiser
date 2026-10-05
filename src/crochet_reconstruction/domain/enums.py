"""Closed vocabularies for the crochet domain model.

Every enum here is deliberately small and scoped to what Phase 1 (adult
top-down beanie) needs. New members should only be added alongside the
engine/validator/renderer support that makes them meaningful — an enum
member with no compiler support is a silent trap, not a feature flag.
"""

from __future__ import annotations

from enum import StrEnum


class Terminology(StrEnum):
    """Abbreviation/terminology system used to label stitches for humans.

    UK terminology is a known future requirement (stitch names shift, e.g.
    US single crochet == UK double crochet) but is not implemented in
    Phase 1: only the US mapping exists in the renderer.
    """

    US = "US"


class StitchFamily(StrEnum):
    """Supported body stitches.

    ``SC``/``HDC`` are the Phase 1 beanie engine's vocabulary (see
    ``engine/crown.py``/``engine/body.py``). ``DC`` was added for the
    written-pattern parser (``parsing/written/``), which needs it for its
    documented abbreviation list; the beanie engine still never emits it.
    """

    SC = "sc"
    HDC = "hdc"
    DC = "dc"


class Construction(StrEnum):
    """Round-joining style.

    Only ``CONTINUOUS`` (spiral) rounds are implemented by the engine in
    Phase 1. ``JOINED`` is modelled here so the schema does not need a
    breaking change when joined rounds are added, but selecting it is
    rejected explicitly (see
    :class:`crochet_reconstruction.domain.errors.UnsupportedConstructionError`)
    rather than silently downgraded to continuous.
    """

    CONTINUOUS = "continuous_rounds"
    JOINED = "joined_rounds"


class BrimType(StrEnum):
    """Supported brim treatments for Phase 1."""

    NONE = "none"
    BLO_IN_ROUND = "blo_in_round"


class LoopPlacement(StrEnum):
    """Which loop(s) a stitch is worked into."""

    BOTH = "both"
    FRONT_LOOP_ONLY = "front_loop_only"
    BACK_LOOP_ONLY = "back_loop_only"


class ComponentKind(StrEnum):
    """Beanie components (``CROWN``/``BODY``/``BRIM``) plus ``PIECE``.

    ``PIECE`` is one undifferentiated worked piece with no crown/body/brim
    distinction, used by the written-pattern parser (``parsing/written/``)
    for generic round-based patterns (amigurumi, swatches) that aren't
    beanies. The rotational geometry layout treats ``PIECE`` the same as
    ``BODY`` (a flat vertical stack of rounds, no dome curvature) — a known,
    documented approximation for shapes like a sphere, where a real
    crown-and-decrease-symmetric dome treatment would render more
    accurately. See docs/known-limitations.md.
    """

    CROWN = "crown"
    BODY = "body"
    BRIM = "brim"
    PIECE = "piece"


class ClosureKind(StrEnum):
    """End-of-round closure metadata for a single round.

    ``NONE`` means the round is part of a continuous spiral with no
    stitch-level closure. ``SLIP_STITCH_JOIN`` is reserved for joined
    rounds and is never produced by the Phase 1 engine.
    """

    NONE = "none"
    SLIP_STITCH_JOIN = "slip_stitch_join"


class AssumptionSource(StrEnum):
    """Provenance of a value recorded in :class:`Assumption`.

    ``MODEL_SUGGESTED`` exists for forward-compatibility with the later
    AI-assisted phases described in the decision package; the Phase 1
    engine never produces it.
    """

    USER_CONFIRMED = "user_confirmed"
    DERIVED = "derived"
    TEMPLATE_DEFAULT = "template_default"
    MODEL_SUGGESTED = "model_suggested"


class Severity(StrEnum):
    """Validation severity levels, ordered from most to least blocking."""

    FATAL = "fatal"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    WARNING = "warning"
    INFORMATIONAL = "informational"


class PatternStatus(StrEnum):
    VALID = "valid"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    INVALID = "invalid"
