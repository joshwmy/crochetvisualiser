"""Per-stitch-family row-height scaling for the rotational layout.

``Gauge.rounds_per_cm`` is measured over a swatch worked in one stitch —
``Gauge.stitch_family`` records which one. A round worked in that same
family is therefore exactly ``1 / rounds_per_cm`` tall by definition, and
needs no correction. A round worked in a *different* family is not: a round
of ``dc`` occupies more vertical space than a round of ``sc`` at the same
round gauge, and the previous uniform ``1 / rounds_per_cm`` spacing rendered
both identically.

This module supplies the missing relative term, anchored on the gauge's own
family so the measured number stays authoritative:

    row_height(round) = (1 / rounds_per_cm) * ratio[round_family] / ratio[gauge_family]

**The ratios are provisional and awaiting crochet-expert approval** — see
``STITCH_HEIGHT_RATIOS`` below. They are the standard US turning-chain
convention, not a measured proportion, and this module never presents them
as one: any pattern where they actually change a position also emits a
warning through ``GeometryDocument.warnings`` (see
``geometry/layout.py``'s ``stitch_height_warnings``), the same way every
other analytical assumption in this package is surfaced rather than
silently applied.
"""

from __future__ import annotations

from crochet_reconstruction.domain.enums import StitchFamily
from crochet_reconstruction.domain.operations import (
    DecreaseOp,
    IncreaseOp,
    MagicRingOp,
    Operation,
    RepeatOp,
    StitchOp,
    produced_count,
)
from crochet_reconstruction.domain.rounds import Component, Round

STITCH_HEIGHT_RATIOS: dict[StitchFamily, float] = {
    StitchFamily.SC: 1.0,
    StitchFamily.HDC: 2.0,
    StitchFamily.DC: 3.0,
}
"""Relative worked height per stitch family, expressed against ``sc`` = 1.0.

**Provisional — requires crochet-expert approval, in the sense of
``docs/decision-gates.md``.** These are the standard US turning-chain
counts (``sc`` 1 chain, ``hdc`` 2, ``dc`` 3), which is the conventional
published statement of relative stitch height — it is *not* a measured
fabric proportion, and real worked ``dc`` is commonly shorter than three
times a ``sc``. The convention was chosen over inventing a
plausible-looking decimal precisely because it is attributable: a reviewer
can disagree with a named convention, whereas an invented 2.4 would look
authoritative while being unfounded.

Only the *ratio between two families* is ever used, so re-basing the whole
table on a different anchor changes nothing.
"""


def _tally_produced_by_family(
    operations: list[Operation], tally: dict[StitchFamily, int], order: list[StitchFamily]
) -> None:
    """Accumulate produced-stitch counts per family, recording first appearance."""
    for op in operations:
        match op:
            case RepeatOp(times=times, body=body):
                inner: dict[StitchFamily, int] = {}
                _tally_produced_by_family(body, inner, order)
                for family, count in inner.items():
                    tally[family] = tally.get(family, 0) + times * count
            case MagicRingOp() | StitchOp() | IncreaseOp() | DecreaseOp():
                if op.stitch not in tally:
                    order.append(op.stitch)
                tally[op.stitch] = tally.get(op.stitch, 0) + produced_count(op)
            case _:
                raise TypeError(f"unhandled operation type: {type(op).__name__}")


def dominant_stitch_family(round_: Round) -> StitchFamily:
    """The family producing the most stitches in ``round_``.

    A round may legitimately mix families (``2 sc, 1 dc``), but the layout
    places a whole round at one ``z`` — so one family has to characterise
    it. Most-produced wins; ties break toward whichever tied family appears
    first in operation order, so the result is deterministic and depends
    only on structured fields, never on rendered text.
    """
    tally: dict[StitchFamily, int] = {}
    order: list[StitchFamily] = []
    _tally_produced_by_family(round_.operations, tally, order)
    if not tally:  # pragma: no cover - Round requires >= 1 operation
        raise ValueError(f"round {round_.number} has no stitch-producing operations")
    best = max(tally.values())
    for family in order:
        if tally[family] == best:
            return family
    raise AssertionError("unreachable: best count came from the tally itself")


def row_height_scale(round_family: StitchFamily, gauge_family: StitchFamily) -> float:
    """Height multiplier for a round of ``round_family`` at ``gauge_family`` gauge.

    Exactly ``1.0`` when the two match — the overwhelmingly common case, and
    the reason this change leaves every single-stitch-family pattern's
    geometry (and fingerprint) untouched.
    """
    return STITCH_HEIGHT_RATIOS[round_family] / STITCH_HEIGHT_RATIOS[gauge_family]


def scaled_row_heights(
    components: list[Component], gauge_family: StitchFamily, base_row_height_cm: float
) -> dict[tuple[str, int], float]:
    """Row height in cm for every ``(component_kind, round_number)`` key."""
    return {
        (component.kind.value, round_.number): base_row_height_cm
        * row_height_scale(dominant_stitch_family(round_), gauge_family)
        for component in components
        for round_ in component.rounds
    }


def stitch_height_warnings(components: list[Component], gauge_family: StitchFamily) -> list[str]:
    """Warnings for rounds whose height was scaled away from the measured gauge.

    Empty when every round is worked in the gauge's own family, so a
    single-family pattern gains no new warning noise.
    """
    off_gauge = sorted(
        {
            dominant_stitch_family(round_)
            for component in components
            for round_ in component.rounds
            if dominant_stitch_family(round_) is not gauge_family
        }
    )
    if not off_gauge:
        return []
    named = ", ".join(family.value for family in off_gauge)
    return [
        f"Round height for {named} rounds was scaled relative to the "
        f"{gauge_family.value} gauge using the standard turning-chain height "
        "convention (sc 1 / hdc 2 / dc 3). That convention is provisional and "
        "awaiting crochet-expert approval — it is not a measured fabric "
        "proportion, and these rounds' vertical spacing is correspondingly "
        "less reliable than a round worked in the gauge's own stitch."
    ]
