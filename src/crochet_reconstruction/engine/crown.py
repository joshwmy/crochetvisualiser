"""Top-down crown: diameter diagnostic and constant-increase round schedule.

Formulas follow decision package §14 ("Approximate crown diameter",
"Approximate increases per flat round", "Top-down crown schedule"). See
docs/mathematical-assumptions.md for full derivation and limitations.
"""

from __future__ import annotations

from decimal import Decimal

from crochet_reconstruction.domain.enums import ClosureKind, StitchFamily
from crochet_reconstruction.domain.errors import UnsupportedDimensionsError
from crochet_reconstruction.domain.operations import (
    IncreaseOp,
    MagicRingOp,
    Operation,
    RepeatOp,
    StitchOp,
)
from crochet_reconstruction.domain.rounds import Round
from crochet_reconstruction.engine.sizing import PI
from crochet_reconstruction.templates.base import BeanieTemplate


def crown_diameter_cm(target_circumference_cm: Decimal) -> Decimal:
    """``D_c ≈ C_t / π`` — a diagnostic approximation, not a fit guarantee.

    Assumes the crown behaves as a flat disk up to the point it meets the
    target circumference; a real fitted crown curves into the head before
    that point, so this is used only to sanity-check the crown schedule,
    never as the stopping condition itself (decision package §14, "Use").
    """
    return target_circumference_cm / PI


def estimate_increases_per_round(
    stitches_per_cm: Decimal,
    rounds_per_cm: Decimal,
    template: BeanieTemplate,
) -> int:
    """``k ≈ 2π * g_s / g_r``, snapped to the nearest expert-approved schedule.

    Ties are broken toward the smaller allowed value for determinism.
    """
    k = 2 * PI * stitches_per_cm / rounds_per_cm
    allowed = template.crown_profile.allowed_increases_per_round
    return min(allowed, key=lambda m: (abs(Decimal(m) - k), m))


def build_crown_rounds(
    target_count: int,
    increases_per_round: int,
    stitch_family: StitchFamily,
) -> list[Round]:
    """Generate the constant-increase crown schedule.

    ``Round r`` total is ``increases_per_round * r`` (decision package's
    "simple constant-increase family": ``s0 = m``, ``total_r = s0 + (r-1)*m``).
    Each of the ``m`` repeat groups in round ``r >= 2`` consumes ``r - 1``
    previous-round stitches: ``r - 2`` plain stitches plus one increase.

    Raises :class:`UnsupportedDimensionsError` if ``target_count`` is not an
    exact multiple of ``increases_per_round`` — this should not happen given
    :func:`crochet_reconstruction.engine.sizing.repeat_compatible_count` is
    always called with this same multiple beforehand, but is checked
    defensively rather than silently producing a tapered final round.
    """
    m = increases_per_round
    if m < 1 or target_count % m != 0:
        raise UnsupportedDimensionsError(
            f"target body stitch count {target_count} is not a multiple of increases_per_round {m}"
        )

    rounds: list[Round] = [
        Round(
            number=1,
            operations=[MagicRingOp(stitch=stitch_family, output=m)],
            stated_total=m,
            closure=ClosureKind.NONE,
        )
    ]

    total = m
    round_number = 2
    while total < target_count:
        plain_stitches = round_number - 2
        body: list[Operation] = []
        if plain_stitches > 0:
            body.append(StitchOp(stitch=stitch_family, count=plain_stitches))
        body.append(IncreaseOp(stitch=stitch_family, input=1, output=2))

        total = round_number * m
        rounds.append(
            Round(
                number=round_number,
                operations=[RepeatOp(times=m, body=body)],
                stated_total=total,
                closure=ClosureKind.NONE,
            )
        )
        round_number += 1

    return rounds
