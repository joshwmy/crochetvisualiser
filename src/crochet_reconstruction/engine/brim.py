"""Brim: either no separate brim, or a simple back-loop-only in-round brim.

Decision package §14, "Brim calculations" ("In-round brim"). Folded and
vertical-ribbed brims are out of Phase 1 scope.
"""

from __future__ import annotations

from decimal import Decimal

from crochet_reconstruction.domain.enums import BrimType, ClosureKind, LoopPlacement, StitchFamily
from crochet_reconstruction.domain.operations import StitchOp
from crochet_reconstruction.domain.rounds import Round
from crochet_reconstruction.engine.sizing import round_half_up


def brim_round_count(
    brim_type: BrimType, brim_height_cm: Decimal | None, rounds_per_cm: Decimal
) -> int:
    """``R_brim = round(b_t * g_r)``; zero when there is no separate brim."""
    if brim_type is BrimType.NONE:
        return 0
    if brim_height_cm is None:
        raise ValueError("brim_height_cm is required when brim_type is not NONE")
    return int(round_half_up(brim_height_cm * rounds_per_cm))


def build_brim_rounds(
    start_round_number: int,
    round_count: int,
    stitch_count: int,
    stitch_family: StitchFamily,
    brim_type: BrimType,
) -> list[Round]:
    """Back-loop-only rounds at the body stitch count (no shaping)."""
    if brim_type is BrimType.NONE or round_count == 0:
        return []

    loop = (
        LoopPlacement.BACK_LOOP_ONLY if brim_type is BrimType.BLO_IN_ROUND else LoopPlacement.BOTH
    )
    rounds: list[Round] = []
    for offset in range(round_count):
        rounds.append(
            Round(
                number=start_round_number + offset,
                operations=[StitchOp(stitch=stitch_family, count=stitch_count, loop=loop)],
                stated_total=stitch_count,
                closure=ClosureKind.NONE,
            )
        )
    return rounds
