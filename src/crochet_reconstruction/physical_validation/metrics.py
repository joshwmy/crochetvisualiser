"""Measurable evaluation metrics over ingested physical results.

Every function here is a pure calculation over already-validated data
(:mod:`crochet_reconstruction.physical_validation.result_schema`). None of
them decide whether the engine "passes" — that judgement, and the
proposed thresholds it is compared against, live in
:mod:`crochet_reconstruction.physical_validation.evaluation_report` and
docs/decision-gates.md, kept deliberately separate from the arithmetic
itself.

Per the Phase 1.5 brief: acceptance is reported as separate proportions
across four categories, never collapsed into a single "accuracy" score.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from crochet_reconstruction.physical_validation.result_schema import (
    AcceptanceStatus,
    PhysicalTrialResult,
)


@dataclass(frozen=True, slots=True)
class DimensionalError:
    """A signed error: ``actual - expected``, plus the percentage version.

    Signed (not absolute) so a report can distinguish "runs large" from
    "runs small" — that distinction is itself useful crochet-engineering
    signal. Use :func:`median_absolute_error` when aggregating across
    trials for a single pass/fail-style number.
    """

    actual: Decimal
    expected: Decimal
    absolute_error_cm: Decimal
    percentage_error: Decimal | None
    """None only when ``expected`` is exactly zero (undefined percentage)."""


def _dimensional_error(actual: Decimal, expected: Decimal) -> DimensionalError:
    difference = actual - expected
    percentage = (difference / expected) * Decimal(100) if expected != 0 else None
    return DimensionalError(
        actual=actual,
        expected=expected,
        absolute_error_cm=difference,
        percentage_error=percentage,
    )


def circumference_error(
    actual_relaxed_cm: Decimal, expected_finished_cm: Decimal
) -> DimensionalError:
    """``actual relaxed circumference - expected finished circumference``."""
    return _dimensional_error(actual_relaxed_cm, expected_finished_cm)


def height_error(actual_height_cm: Decimal, target_height_cm: Decimal) -> DimensionalError:
    """``actual height - target height``."""
    return _dimensional_error(actual_height_cm, target_height_cm)


def crown_diameter_error(
    measured_crown_diameter_cm: Decimal, calculated_crown_diameter_cm: Decimal
) -> DimensionalError:
    """Compares a measured crown diameter against the engine's diagnostic target.

    Recall the engine's crown diameter is itself an approximation
    (``C_t / pi``, decision package §14) — a nonzero error here does not by
    itself indicate a defect, only a data point for expert review.
    """
    return _dimensional_error(measured_crown_diameter_cm, calculated_crown_diameter_cm)


def median_absolute_error(errors: Sequence[DimensionalError]) -> Decimal | None:
    """Median of ``|absolute_error_cm|`` across trials. ``None`` if empty."""
    if not errors:
        return None
    magnitudes = sorted(abs(e.absolute_error_cm) for e in errors)
    return statistics.median(magnitudes)


def instruction_correction_rate(result: PhysicalTrialResult, total_rounds: int) -> Decimal:
    """``number of rounds requiring correction / total rounds`` for one trial."""
    if total_rounds <= 0:
        raise ValueError("total_rounds must be positive")
    corrected = len(result.during_crochet.corrected_rounds)
    return Decimal(corrected) / Decimal(total_rounds)


def is_arithmetic_failure(result: PhysicalTrialResult) -> bool:
    """A trial where actual stitch totals could not follow the generated
    round totals without correction (tester reported a mismatch)."""
    return not result.during_crochet.round_totals_matched


def arithmetic_failure_rate(results: Sequence[PhysicalTrialResult]) -> Decimal:
    """Proportion of ``results`` flagged as arithmetic failures. Zero if empty."""
    if not results:
        return Decimal(0)
    failures = sum(1 for r in results if is_arithmetic_failure(r))
    return Decimal(failures) / Decimal(len(results))


def acceptance_proportions(results: Sequence[PhysicalTrialResult]) -> dict[str, Decimal]:
    """Proportion of ``results`` in each of the four acceptance categories.

    Always returns all four keys (zero-filled if a category is unused) so a
    report can render a complete breakdown rather than a partial one.
    Deliberately not combined into a single score.
    """
    counts = Counter(r.ratings.acceptance for r in results)
    total = len(results)
    if total == 0:
        return {status.value: Decimal(0) for status in AcceptanceStatus}
    return {
        status.value: Decimal(counts.get(status, 0)) / Decimal(total) for status in AcceptanceStatus
    }
