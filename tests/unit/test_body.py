import pytest

from crochet_reconstruction.domain.enums import StitchFamily
from crochet_reconstruction.domain.errors import UnsupportedDimensionsError
from crochet_reconstruction.engine.body import body_round_count, build_body_rounds
from crochet_reconstruction.templates.top_down_beanie import TOP_DOWN_BASIC


def test_body_round_count_subtracts_crown_and_brim() -> None:
    assert body_round_count(25, 10, 5, TOP_DOWN_BASIC) == 10


def test_body_round_count_rejects_below_minimum() -> None:
    with pytest.raises(UnsupportedDimensionsError, match="below template minimum"):
        body_round_count(10, 10, 5, TOP_DOWN_BASIC)  # remaining = -5


def test_build_body_rounds_numbers_continue_from_crown() -> None:
    rounds = build_body_rounds(
        start_round_number=11, round_count=3, stitch_count=80, stitch_family=StitchFamily.HDC
    )
    assert [r.number for r in rounds] == [11, 12, 13]
    assert all(r.stated_total == 80 for r in rounds)
    assert all(len(r.operations) == 1 for r in rounds)
