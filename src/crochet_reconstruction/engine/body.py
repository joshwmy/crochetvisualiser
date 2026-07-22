"""Straight body: round count allocation and even-round generation.

Decision package §14, "Hat height and body rounds": total height rounds
minus crown depth minus brim rounds gives the straight body allocation.
"""

from __future__ import annotations

from crochet_reconstruction.domain.enums import ClosureKind, StitchFamily
from crochet_reconstruction.domain.errors import UnsupportedDimensionsError
from crochet_reconstruction.domain.operations import StitchOp
from crochet_reconstruction.domain.rounds import Round
from crochet_reconstruction.templates.base import BeanieTemplate


def body_round_count(
    total_rounds_for_height: int,
    crown_round_count: int,
    brim_round_count: int,
    template: BeanieTemplate,
) -> int:
    """``R_body = R_h - R_crown_depth - R_brim``.

    Raises :class:`UnsupportedDimensionsError` (never silently clamps to
    zero) when the result falls below ``template.min_body_rounds`` — the
    requested height is too short for the crown/brim it implies.
    """
    remaining = total_rounds_for_height - crown_round_count - brim_round_count
    if remaining < template.min_body_rounds:
        raise UnsupportedDimensionsError(
            f"body round count {remaining} is below template minimum "
            f"{template.min_body_rounds}; increase target height or reduce "
            f"brim depth"
        )
    return remaining


def build_body_rounds(
    start_round_number: int,
    round_count: int,
    stitch_count: int,
    stitch_family: StitchFamily,
) -> list[Round]:
    """Even rounds: every round works ``stitch_count`` plain stitches around."""
    rounds: list[Round] = []
    for offset in range(round_count):
        rounds.append(
            Round(
                number=start_round_number + offset,
                operations=[StitchOp(stitch=stitch_family, count=stitch_count)],
                stated_total=stitch_count,
                closure=ClosureKind.NONE,
            )
        )
    return rounds
