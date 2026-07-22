"""Deterministic gauge/dimension math: target circumference and repeat rounding.

See docs/mathematical-assumptions.md for the derivation, units, and
supported range of every formula in this module. Nothing here depends on
Pydantic models beyond the plain value types passed in — these are pure
functions over ``Decimal``, kept independent of the domain/compiler layers
so they can be unit-tested and reference-checked in isolation (decision
package Experiment 1: "Implement formulas independently... Compare
intermediate and final values.").
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PI: Decimal = Decimal("3.14159265358979323846")
"""Fixed-precision Decimal pi. A literal constant (not derived from
``math.pi``) so the value is explicit, reviewable, and independent of any
floating-point conversion step."""

_ONE = Decimal(1)
_TEN = Decimal(10)


def round_half_up(value: Decimal, places: int = 0) -> Decimal:
    """Round ``value`` to ``places`` decimal digits, ties away from zero.

    This is the single rounding policy used throughout the engine. Crochet
    round/stitch counts are always integers in the end, so ``places=0`` is
    the common case; ``places`` > 0 is used only for reporting intermediate
    centimetre values.
    """
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def target_circumference_cm(head_circumference_cm: Decimal, negative_ease_pct: Decimal) -> Decimal:
    """``C_t = H * (1 - e)`` — decision package §14, "Target circumference".

    ``negative_ease_pct`` is a percentage (e.g. ``Decimal("8")`` for 8%), not
    a fraction, matching the typed user input. Negative ease is always a
    user-supplied design parameter in Phase 1 — never inferred or defaulted.
    """
    ease_fraction = negative_ease_pct / Decimal(100)
    return head_circumference_cm * (_ONE - ease_fraction)


def stitches_from_circumference(circumference_cm: Decimal, stitches_per_cm: Decimal) -> Decimal:
    """``N_raw = C_t * g_s`` — raw (non-repeat-compatible) stitch count."""
    return circumference_cm * stitches_per_cm


def rounds_from_height(height_cm: Decimal, rounds_per_cm: Decimal) -> int:
    """``R_h = round(h_t * g_r)`` — total rounds spanning a height."""
    raw = height_cm * rounds_per_cm
    return int(round_half_up(raw))


@dataclass(frozen=True, slots=True)
class RepeatCompatibleCount:
    """The raw/final/deviation triple the decision package requires be recorded
    for every repeat-compatible rounding decision (§14, "Body stitch count")."""

    raw: Decimal
    chosen: int
    repeat_multiple: int
    resulting_circumference_cm: Decimal
    deviation_cm: Decimal


def repeat_compatible_count(
    raw_count: Decimal,
    repeat_multiple: int,
    stitches_per_cm: Decimal,
    target_circumference_cm_value: Decimal,
) -> RepeatCompatibleCount:
    """Round ``raw_count`` to the nearest multiple of ``repeat_multiple``.

    Candidates below and above ``raw_count`` are compared by resulting
    dimensional deviation from the target circumference; ties are broken in
    favour of the larger candidate (a looser fit reads as "less restrictive
    ease" per decision package §14 tie-break guidance). The zero candidate is
    never chosen — a beanie crown needs at least one repeat's worth of
    stitches.
    """
    if repeat_multiple < 1:
        raise ValueError("repeat_multiple must be >= 1")

    multiple = Decimal(repeat_multiple)
    down_units = (raw_count / multiple).to_integral_value(rounding="ROUND_FLOOR")
    down = int(down_units * multiple)
    up = down + repeat_multiple
    if down <= 0:
        down = up
        up = down + repeat_multiple

    def deviation_for(n: int) -> Decimal:
        circumference = Decimal(n) / stitches_per_cm
        return abs(circumference - target_circumference_cm_value)

    down_deviation = deviation_for(down)
    up_deviation = deviation_for(up)

    chosen = up if up_deviation <= down_deviation else down
    chosen_deviation = up_deviation if chosen == up else down_deviation
    resulting_circumference = Decimal(chosen) / stitches_per_cm

    return RepeatCompatibleCount(
        raw=raw_count,
        chosen=chosen,
        repeat_multiple=repeat_multiple,
        resulting_circumference_cm=resulting_circumference,
        deviation_cm=chosen_deviation,
    )
