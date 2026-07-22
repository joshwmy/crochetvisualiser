from decimal import Decimal

import pytest

from crochet_reconstruction.physical_validation.metrics import (
    acceptance_proportions,
    arithmetic_failure_rate,
    circumference_error,
    crown_diameter_error,
    height_error,
    instruction_correction_rate,
    is_arithmetic_failure,
    median_absolute_error,
)
from crochet_reconstruction.physical_validation.result_schema import (
    AcceptanceStatus,
    RoundCorrection,
)
from tests.physical_validation.conftest import make_synthetic_result


def test_circumference_error_is_signed_actual_minus_expected() -> None:
    error = circumference_error(Decimal("44.0"), Decimal("42.0"))
    assert error.absolute_error_cm == Decimal("2.0")


def test_circumference_error_negative_when_smaller_than_expected() -> None:
    error = circumference_error(Decimal("40.0"), Decimal("42.0"))
    assert error.absolute_error_cm == Decimal("-2.0")


def test_percentage_error_computed_relative_to_expected() -> None:
    error = height_error(Decimal("22.0"), Decimal("20.0"))
    assert error.percentage_error == Decimal("10.0")


def test_percentage_error_is_none_when_expected_is_zero() -> None:
    error = height_error(Decimal("5.0"), Decimal("0"))
    assert error.percentage_error is None
    assert error.absolute_error_cm == Decimal("5.0")


def test_crown_diameter_error() -> None:
    error = crown_diameter_error(Decimal("14.0"), Decimal("13.4"))
    assert error.absolute_error_cm == Decimal("0.6")


def test_median_absolute_error_of_mixed_sign_errors() -> None:
    errors = [
        circumference_error(Decimal("40"), Decimal("42")),  # -2
        circumference_error(Decimal("44"), Decimal("42")),  # +2
        circumference_error(Decimal("45"), Decimal("42")),  # +3
    ]
    assert median_absolute_error(errors) == Decimal("2")


def test_median_absolute_error_empty_is_none() -> None:
    assert median_absolute_error([]) is None


def test_instruction_correction_rate() -> None:
    corrections = [RoundCorrection(round_number=3, problem="p", correction="c")]
    result = make_synthetic_result(corrected_rounds=corrections)
    assert instruction_correction_rate(result, total_rounds=20) == Decimal("1") / Decimal("20")


def test_instruction_correction_rate_rejects_non_positive_total() -> None:
    result = make_synthetic_result()
    with pytest.raises(ValueError, match="total_rounds must be positive"):
        instruction_correction_rate(result, total_rounds=0)


def test_is_arithmetic_failure_true_when_totals_did_not_match() -> None:
    result = make_synthetic_result(round_totals_matched=False)
    assert is_arithmetic_failure(result) is True


def test_is_arithmetic_failure_false_when_totals_matched_even_with_corrections() -> None:
    # A tester can correct wording/clarity issues without the arithmetic
    # itself having failed - these are independent signals.
    corrections = [RoundCorrection(round_number=5, problem="unclear wording", correction="reread")]
    result = make_synthetic_result(round_totals_matched=True, corrected_rounds=corrections)
    assert is_arithmetic_failure(result) is False


def test_arithmetic_failure_rate_across_results() -> None:
    results = [
        make_synthetic_result(round_totals_matched=True),
        make_synthetic_result(round_totals_matched=False),
        make_synthetic_result(round_totals_matched=False),
        make_synthetic_result(round_totals_matched=True),
    ]
    assert arithmetic_failure_rate(results) == Decimal("1") / Decimal("2")


def test_arithmetic_failure_rate_empty_is_zero() -> None:
    assert arithmetic_failure_rate([]) == Decimal(0)


def test_acceptance_proportions_all_four_categories_present() -> None:
    results = [
        make_synthetic_result(acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION),
        make_synthetic_result(acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION),
        make_synthetic_result(acceptance=AcceptanceStatus.UNUSABLE),
    ]
    proportions = acceptance_proportions(results)
    assert set(proportions) == {status.value for status in AcceptanceStatus}
    assert proportions["acceptable_no_correction"] == Decimal("2") / Decimal("3")
    assert proportions["unusable"] == Decimal("1") / Decimal("3")
    assert proportions["acceptable_minor_correction"] == Decimal(0)
    assert proportions["requires_major_correction"] == Decimal(0)


def test_acceptance_proportions_empty_is_all_zero() -> None:
    proportions = acceptance_proportions([])
    assert all(v == Decimal(0) for v in proportions.values())
