import pytest
from pydantic import ValidationError

from crochet_reconstruction.physical_validation.result_schema import (
    AcceptanceStatus,
    ExpertRatings,
    Handedness,
    RoundCorrection,
    StitchFamiliarity,
    TesterInfo,
)
from tests.physical_validation.conftest import make_synthetic_result


def test_synthetic_result_builds_successfully() -> None:
    result = make_synthetic_result()
    assert result.trial_id == "BV-001"
    assert result.ratings.acceptance is AcceptanceStatus.ACCEPTABLE_NO_CORRECTION


def test_rating_out_of_range_is_rejected() -> None:
    # model_copy(update=...) skips validation by design, so the invalid value
    # is constructed directly through the model's own __init__ instead.
    with pytest.raises(ValidationError):
        ExpertRatings(
            mathematical_correctness=5,
            instruction_clarity=4,
            construction_plausibility=4,
            fit=4,
            shape=4,
            visual_quality=4,
            beginner_suitability=3,
            overall_usability=6,  # out of the 1-5 range
            would_use_again=True,
            would_recommend=True,
            acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION,
        )


def test_invalid_enum_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TesterInfo(
            tester_id="SYN-1",
            experience_level="wizard",  # type: ignore[arg-type]
            stitch_familiarity=StitchFamiliarity.COMFORTABLE,
            handedness=Handedness.RIGHT,
        )


def test_negative_circumference_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_synthetic_result(relaxed_circumference_cm="-5.0")


def test_multiple_testers_can_report_on_same_trial_independently() -> None:
    result_a = make_synthetic_result(tester_id="SYN-1", relaxed_circumference_cm="42.0")
    result_b = make_synthetic_result(tester_id="SYN-2", relaxed_circumference_cm="45.0")

    assert result_a.trial_id == result_b.trial_id
    assert result_a.tester.tester_id != result_b.tester.tester_id
    assert result_a.finished_measurements.relaxed_circumference_cm != (
        result_b.finished_measurements.relaxed_circumference_cm
    )


def test_corrected_rounds_are_preserved_raw() -> None:
    corrections = [
        RoundCorrection(round_number=4, problem="wrong total", correction="added one increase"),
        RoundCorrection(round_number=7, problem="unclear wording", correction="reread twice"),
    ]
    result = make_synthetic_result(corrected_rounds=corrections)
    assert len(result.during_crochet.corrected_rounds) == 2
    assert result.during_crochet.corrected_rounds[0].round_number == 4
