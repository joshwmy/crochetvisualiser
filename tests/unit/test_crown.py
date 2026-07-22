from decimal import Decimal

import pytest

from crochet_reconstruction.domain.enums import StitchFamily
from crochet_reconstruction.domain.errors import UnsupportedDimensionsError
from crochet_reconstruction.domain.operations import consumed_count, produced_count
from crochet_reconstruction.engine.crown import (
    build_crown_rounds,
    crown_diameter_cm,
    estimate_increases_per_round,
)
from crochet_reconstruction.engine.sizing import PI
from crochet_reconstruction.templates.top_down_beanie import TOP_DOWN_BASIC


def test_crown_diameter_is_circumference_over_pi() -> None:
    target = Decimal("51.52")
    assert crown_diameter_cm(target) == target / PI


def test_estimate_increases_per_round_picks_nearest_allowed() -> None:
    # k = 2*pi*g_s/g_r; choose gauge so k lands near 8.
    g_s = Decimal("1.6")  # 16 st/10cm
    g_r = Decimal("1.2")  # 12 rounds/10cm -> k ~ 8.38 -> nearest of {6,8} is 8
    assert estimate_increases_per_round(g_s, g_r, TOP_DOWN_BASIC) == 8


def test_build_crown_rounds_totals_match_formula() -> None:
    rounds = build_crown_rounds(
        target_count=48, increases_per_round=8, stitch_family=StitchFamily.SC
    )
    totals = [r.stated_total for r in rounds]
    assert totals == [8, 16, 24, 32, 40, 48]
    assert [r.number for r in rounds] == list(range(1, len(rounds) + 1))


def test_build_crown_rounds_arithmetic_is_internally_consistent() -> None:
    rounds = build_crown_rounds(
        target_count=80, increases_per_round=8, stitch_family=StitchFamily.HDC
    )
    previous_total = None
    for round_ in rounds:
        consumed = sum(consumed_count(op) for op in round_.operations)
        produced = sum(produced_count(op) for op in round_.operations)
        assert produced == round_.stated_total
        if previous_total is not None:
            assert consumed == previous_total
        previous_total = produced


def test_build_crown_rounds_rejects_non_multiple_target() -> None:
    with pytest.raises(UnsupportedDimensionsError, match="not a multiple"):
        build_crown_rounds(target_count=50, increases_per_round=8, stitch_family=StitchFamily.SC)
