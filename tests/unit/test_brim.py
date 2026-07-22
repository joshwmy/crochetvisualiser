from decimal import Decimal

import pytest

from crochet_reconstruction.domain.enums import BrimType, LoopPlacement, StitchFamily
from crochet_reconstruction.engine.brim import brim_round_count, build_brim_rounds


def test_brim_round_count_is_zero_for_none_type() -> None:
    assert brim_round_count(BrimType.NONE, None, Decimal("1.2")) == 0


def test_brim_round_count_requires_height_when_enabled() -> None:
    with pytest.raises(ValueError, match="brim_height_cm is required"):
        brim_round_count(BrimType.BLO_IN_ROUND, None, Decimal("1.2"))


def test_brim_round_count_rounds_half_up() -> None:
    assert brim_round_count(BrimType.BLO_IN_ROUND, Decimal("4.0"), Decimal("1.2")) == 5  # 4.8 -> 5


def test_build_brim_rounds_none_type_produces_nothing() -> None:
    assert build_brim_rounds(21, 5, 80, StitchFamily.HDC, BrimType.NONE) == []


def test_build_brim_rounds_uses_back_loop_only() -> None:
    rounds = build_brim_rounds(21, 2, 80, StitchFamily.HDC, BrimType.BLO_IN_ROUND)
    assert [r.number for r in rounds] == [21, 22]
    for round_ in rounds:
        assert round_.stated_total == 80
        (op,) = round_.operations
        assert op.loop is LoopPlacement.BACK_LOOP_ONLY
