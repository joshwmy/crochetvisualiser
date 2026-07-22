from decimal import Decimal

import pytest

from crochet_reconstruction.engine.sizing import (
    repeat_compatible_count,
    round_half_up,
    rounds_from_height,
    stitches_from_circumference,
    target_circumference_cm,
)


def test_target_circumference_no_ease() -> None:
    assert target_circumference_cm(Decimal(56), Decimal(0)) == Decimal(56)


def test_target_circumference_with_ease() -> None:
    # C_t = H * (1 - e) = 56 * (1 - 0.08) = 51.52
    assert target_circumference_cm(Decimal(56), Decimal(8)) == Decimal("51.52")


def test_target_circumference_full_ease_gives_zero() -> None:
    assert target_circumference_cm(Decimal(56), Decimal(100)) == Decimal(0)


def test_stitches_from_circumference() -> None:
    # g_s given as stitches/cm here (already converted from per-10cm)
    assert stitches_from_circumference(Decimal(50), Decimal("1.6")) == Decimal(80)


def test_rounds_from_height_rounds_half_up() -> None:
    assert rounds_from_height(Decimal("21.0"), Decimal("1.2")) == 25  # 25.2 -> 25
    assert rounds_from_height(Decimal("20.0"), Decimal("1.25")) == 25  # 25.0 -> 25


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        (Decimal("2.5"), 0, Decimal("3")),
        (Decimal("2.4"), 0, Decimal("2")),
        (Decimal("-2.5"), 0, Decimal("-3")),  # ties away from zero, not banker's rounding
        (Decimal("1.005"), 2, Decimal("1.01")),
    ],
)
def test_round_half_up_policy(value: Decimal, places: int, expected: Decimal) -> None:
    assert round_half_up(value, places) == expected


def test_repeat_compatible_count_rounds_to_multiple() -> None:
    # raw=82.43, multiple=8 -> candidates 80 and 88; 80 is closer.
    result = repeat_compatible_count(Decimal("82.43"), 8, Decimal("1.6"), Decimal("51.52"))
    assert result.chosen == 80
    assert result.repeat_multiple == 8
    assert result.deviation_cm == abs(Decimal(80) / Decimal("1.6") - Decimal("51.52"))


def test_repeat_compatible_count_never_chooses_zero() -> None:
    result = repeat_compatible_count(Decimal("3"), 8, Decimal("1.6"), Decimal("2"))
    assert result.chosen > 0
    assert result.chosen % 8 == 0


def test_repeat_compatible_count_tie_breaks_upward() -> None:
    # raw exactly halfway between 72 and 80 in stitch count -> circumference
    # midpoint too (since deviation is linear in n for fixed g_s) -> prefer up.
    raw = Decimal(76)
    target = raw / Decimal("1.6")
    result = repeat_compatible_count(raw, 8, Decimal("1.6"), target)
    assert result.chosen == 80


def test_repeat_compatible_count_rejects_invalid_multiple() -> None:
    with pytest.raises(ValueError, match="repeat_multiple"):
        repeat_compatible_count(Decimal(10), 0, Decimal("1.6"), Decimal(10))
