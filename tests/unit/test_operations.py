import pytest

from crochet_reconstruction.domain.enums import StitchFamily
from crochet_reconstruction.domain.operations import (
    DecreaseOp,
    IncreaseOp,
    MagicRingOp,
    RepeatOp,
    StitchOp,
    consumed_count,
    produced_count,
)


def test_magic_ring_consumes_nothing() -> None:
    op = MagicRingOp(stitch=StitchFamily.SC, output=6)
    assert consumed_count(op) == 0
    assert produced_count(op) == 6


def test_stitch_consumes_and_produces_equally() -> None:
    op = StitchOp(stitch=StitchFamily.HDC, count=5)
    assert consumed_count(op) == 5
    assert produced_count(op) == 5


def test_increase_output_must_exceed_input() -> None:
    with pytest.raises(ValueError, match="output must exceed input"):
        IncreaseOp(stitch=StitchFamily.SC, input=2, output=2)


def test_increase_counts() -> None:
    op = IncreaseOp(stitch=StitchFamily.SC, input=1, output=2)
    assert consumed_count(op) == 1
    assert produced_count(op) == 2


def test_decrease_output_must_be_below_input() -> None:
    with pytest.raises(ValueError, match="output must be less than input"):
        DecreaseOp(stitch=StitchFamily.SC, input=2, output=2)


def test_decrease_counts() -> None:
    op = DecreaseOp(stitch=StitchFamily.SC, input=2, output=1)
    assert consumed_count(op) == 2
    assert produced_count(op) == 1


def test_repeat_multiplies_child_counts() -> None:
    op = RepeatOp(
        times=8,
        body=[
            StitchOp(stitch=StitchFamily.HDC, count=2),
            IncreaseOp(stitch=StitchFamily.HDC, input=1, output=2),
        ],
    )
    # per repeat: consumed = 2 + 1 = 3, produced = 2 + 2 = 4
    assert consumed_count(op) == 8 * 3
    assert produced_count(op) == 8 * 4


def test_repeat_times_must_be_positive() -> None:
    with pytest.raises(ValueError):
        RepeatOp(times=0, body=[StitchOp(stitch=StitchFamily.SC, count=1)])


def test_repeat_body_must_not_be_empty() -> None:
    with pytest.raises(ValueError):
        RepeatOp(times=1, body=[])


def test_nested_repeat_depth_is_bounded() -> None:
    inner = StitchOp(stitch=StitchFamily.SC, count=1)
    for _ in range(10):
        inner = RepeatOp(times=1, body=[inner])
    with pytest.raises(ValueError, match="MAX_REPEAT_DEPTH"):
        consumed_count(inner)
