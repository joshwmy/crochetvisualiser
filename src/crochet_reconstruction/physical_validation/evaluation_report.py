"""Turn ingested physical results into an honest, non-fabricated report.

Structure mirrors the required separation of concerns:

- **Observations** (what testers actually reported) are never altered.
- **Metrics** (:mod:`crochet_reconstruction.physical_validation.metrics`) are
  pure calculations over those observations.
- **Recommendations** are a heuristic reading of the metrics against the
  *qualitative* rules stated in docs/decision-gates.md — never against an
  invented centimetre tolerance. Where a numeric tolerance is required and
  none has expert approval yet, the report says so explicitly instead of
  guessing.

This module never modifies engine code, templates, or formulas. It only
reads and reports.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from crochet_reconstruction.physical_validation.ingestion import (
    IngestionFailure,
    ingest_results_dir,
)
from crochet_reconstruction.physical_validation.metrics import (
    DimensionalError,
    acceptance_proportions,
    arithmetic_failure_rate,
    circumference_error,
    crown_diameter_error,
    height_error,
    instruction_correction_rate,
    is_arithmetic_failure,
    median_absolute_error,
)
from crochet_reconstruction.physical_validation.result_schema import PhysicalTrialResult

# Fields in DuringCrochetEvaluation where True is a physically bad outcome.
_PROBLEM_WHEN_TRUE = ("crown_cupped_early", "crown_rippled")
# Fields where False is a physically bad outcome (None = not applicable, skipped).
_PROBLEM_WHEN_FALSE = (
    "instructions_understandable",
    "abbreviations_clear",
    "round_totals_matched",
    "remained_flat_during_crown",
    "increases_well_distributed",
    "crown_to_body_transition_sensible",
    "blo_brim_behaved_as_expected",
)


@dataclass(frozen=True, slots=True)
class TrialExpectation:
    """The engine-calculated values a trial's results are compared against.

    Loaded from the expert-review pack's ``trial-matrix.json`` — i.e. from
    exactly what was actually handed to the tester, not from whatever the
    trial matrix module currently contains (which may have changed since).
    """

    trial_id: str
    stitch_family: str
    brim_type: str
    head_circumference_cm: Decimal
    stitches_per_10cm: Decimal
    rounds_per_10cm: Decimal
    negative_ease_pct: Decimal
    target_finished_circumference_cm: Decimal
    target_height_cm: Decimal
    calculated_crown_diameter_cm: Decimal
    crown_round_count: int
    body_round_count: int
    brim_round_count: int

    @property
    def total_rounds(self) -> int:
        return self.crown_round_count + self.body_round_count + self.brim_round_count


def load_trial_expectations(trials_dir: Path) -> dict[str, TrialExpectation]:
    matrix_path = trials_dir / "trial-matrix.json"
    rows = json.loads(matrix_path.read_text(encoding="utf-8-sig"))
    expectations: dict[str, TrialExpectation] = {}
    for row in rows:
        expectations[row["trial_id"]] = TrialExpectation(
            trial_id=row["trial_id"],
            stitch_family=row["stitch_family"],
            brim_type=row["brim_type"],
            head_circumference_cm=Decimal(row["head_circumference_cm"]),
            stitches_per_10cm=Decimal(row["stitches_per_10cm"]),
            rounds_per_10cm=Decimal(row["rounds_per_10cm"]),
            negative_ease_pct=Decimal(row["negative_ease_pct"]),
            target_finished_circumference_cm=Decimal(row["target_finished_circumference_cm"]),
            target_height_cm=Decimal(row["target_height_cm"]),
            calculated_crown_diameter_cm=Decimal(row["calculated_crown_diameter_cm"]),
            crown_round_count=int(row["crown_round_count"]),
            body_round_count=int(row["body_round_count"]),
            brim_round_count=int(row["brim_round_count"]),
        )
    return expectations


@dataclass(frozen=True, slots=True)
class ResultMetrics:
    """One ingested result plus every metric computed against its trial's expectations."""

    result: PhysicalTrialResult
    trial: TrialExpectation
    circumference: DimensionalError
    height: DimensionalError
    crown_diameter: DimensionalError | None
    correction_rate: Decimal
    arithmetic_failure: bool


def compute_result_metrics(
    result: PhysicalTrialResult, expectations: dict[str, TrialExpectation]
) -> ResultMetrics:
    trial = expectations[result.trial_id]
    measurements = result.finished_measurements

    crown_diameter = None
    if measurements.crown_diameter_cm is not None:
        crown_diameter = crown_diameter_error(
            measurements.crown_diameter_cm, trial.calculated_crown_diameter_cm
        )

    return ResultMetrics(
        result=result,
        trial=trial,
        circumference=circumference_error(
            measurements.relaxed_circumference_cm, trial.target_finished_circumference_cm
        ),
        height=height_error(measurements.total_height_cm, trial.target_height_cm),
        crown_diameter=crown_diameter,
        correction_rate=instruction_correction_rate(result, trial.total_rounds),
        arithmetic_failure=is_arithmetic_failure(result),
    )


def gauge_bucket(stitches_per_10cm: Decimal) -> str:
    """Reporting bucket only — not a template boundary. See docs/decision-gates.md."""
    if stitches_per_10cm <= Decimal("13"):
        return "low (<=13 st/10cm)"
    if stitches_per_10cm <= Decimal("19"):
        return "medium (14-19 st/10cm)"
    return "high (>=20 st/10cm)"


def size_bucket(head_circumference_cm: Decimal) -> str:
    """Reporting bucket only — not a template boundary. See docs/decision-gates.md."""
    if head_circumference_cm <= Decimal("46"):
        return "small (<=46cm)"
    if head_circumference_cm <= Decimal("58"):
        return "medium (47-58cm)"
    return "large (>=59cm)"


def _group_by(
    items: Iterable[ResultMetrics], key: Callable[[ResultMetrics], str]
) -> dict[str, list[ResultMetrics]]:
    groups: dict[str, list[ResultMetrics]] = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return groups


def summarize_group(items: list[ResultMetrics]) -> dict[str, object]:
    raw_results = [m.result for m in items]
    return {
        "count": len(items),
        "median_absolute_circumference_error_cm": _stringify_optional_decimal(
            median_absolute_error([m.circumference for m in items])
        ),
        "median_absolute_height_error_cm": _stringify_optional_decimal(
            median_absolute_error([m.height for m in items])
        ),
        "arithmetic_failure_rate": str(arithmetic_failure_rate(raw_results)),
        "acceptance_proportions": {
            k: str(v) for k, v in acceptance_proportions(raw_results).items()
        },
    }


def _stringify_optional_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def failure_mode_counts(results: list[PhysicalTrialResult]) -> dict[str, int]:
    """How many submitted results exhibited each named physical problem."""
    counts: Counter[str] = Counter()
    for result in results:
        during = result.during_crochet
        for field in _PROBLEM_WHEN_TRUE:
            if getattr(during, field):
                counts[field] += 1
        for field in _PROBLEM_WHEN_FALSE:
            value = getattr(during, field)
            if value is False:
                counts[field] += 1
    return dict(counts)


def recommend_for_group(label: str, items: list[ResultMetrics]) -> dict[str, object]:
    """A heuristic continue/narrow/redesign reading using only the qualitative
    rules given in docs/decision-gates.md — never an invented tolerance.

    This is a recommendation for human review, not an automated decision;
    nothing in this codebase acts on it.
    """
    if not items:
        return {
            "label": label,
            "recommendation": "insufficient_data",
            "rationale": "no physical results submitted for this group yet",
            "evidence_count": 0,
        }

    raw_results = [m.result for m in items]
    failure_rate = arithmetic_failure_rate(raw_results)
    acceptance = acceptance_proportions(raw_results)
    poor_fraction = Decimal(acceptance["requires_major_correction"]) + Decimal(
        acceptance["unusable"]
    )

    if failure_rate > 0:
        recommendation = "narrow_or_redesign"
        rationale = (
            f"{failure_rate * 100:.0f}% of results in this group reported an "
            f"arithmetic failure (round totals did not match without correction)"
        )
    elif poor_fraction > Decimal("0.5"):
        recommendation = "narrow"
        rationale = (
            f"{poor_fraction * 100:.0f}% of results rated 'requires major correction' or 'unusable'"
        )
    elif poor_fraction > Decimal("0"):
        recommendation = "continue_with_caution"
        rationale = (
            "some results needed major correction or were unusable; review "
            "individually before treating this group as fully validated"
        )
    else:
        recommendation = "continue"
        rationale = "no arithmetic failures; no major-correction/unusable ratings"

    return {
        "label": label,
        "recommendation": recommendation,
        "rationale": rationale,
        "evidence_count": len(items),
        "arithmetic_failure_rate": str(failure_rate),
        "acceptance_proportions": {k: str(v) for k, v in acceptance.items()},
    }


def review_assumptions(
    expectations: dict[str, TrialExpectation],
    trial_reasons: dict[str, tuple[str, list[str]]],
    metrics_by_trial: dict[str, list[ResultMetrics]],
) -> list[dict[str, object]]:
    """Per assumption-under-test, classify as supported / contradicted / mixed
    / no evidence yet, based only on submitted results for that trial."""
    rows: list[dict[str, object]] = []
    for trial_id, (_reason, assumptions) in trial_reasons.items():
        items = metrics_by_trial.get(trial_id, [])
        if not items:
            verdict = "no evidence yet"
        else:
            raw_results = [m.result for m in items]
            any_arithmetic_failure = any(is_arithmetic_failure(r) for r in raw_results)
            poor_ratings = sum(
                1
                for r in raw_results
                if r.ratings.acceptance.value in ("requires_major_correction", "unusable")
            )
            if any_arithmetic_failure or poor_ratings == len(raw_results):
                verdict = "contradicted by available evidence"
            elif poor_ratings == 0:
                verdict = "supported by available evidence"
            else:
                verdict = "mixed evidence"

        for assumption in assumptions:
            rows.append(
                {
                    "trial_id": trial_id,
                    "assumption": assumption,
                    "verdict": verdict,
                    "evidence_count": len(items),
                }
            )
    return rows


def generate_evaluation_report(trials_dir: Path, results_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    expectations = load_trial_expectations(trials_dir)
    successes, failures = ingest_results_dir(results_dir)

    metrics = [compute_result_metrics(result, expectations) for result in successes]
    metrics_by_trial: dict[str, list[ResultMetrics]] = {}
    for item in metrics:
        metrics_by_trial.setdefault(item.trial.trial_id, []).append(item)

    trial_reasons = _load_trial_reasons(trials_dir)

    groups = {
        "by_stitch_family": _group_by(metrics, lambda m: m.trial.stitch_family),
        "by_gauge_range": _group_by(metrics, lambda m: gauge_bucket(m.trial.stitches_per_10cm)),
        "by_size_range": _group_by(metrics, lambda m: size_bucket(m.trial.head_circumference_cm)),
        "by_brim_type": _group_by(metrics, lambda m: m.trial.brim_type),
    }

    group_summaries = {
        grouping: {key: summarize_group(items) for key, items in groups[grouping].items()}
        for grouping in groups
    }
    group_recommendations = {
        grouping: [recommend_for_group(key, items) for key, items in groups[grouping].items()]
        for grouping in groups
    }

    all_raw_results = [m.result for m in metrics]
    overall = {
        "trials_with_results": len(metrics_by_trial),
        "total_results_ingested": len(successes),
        "total_ingestion_failures": len(failures),
        "overall_arithmetic_failure_rate": str(arithmetic_failure_rate(all_raw_results)),
        "overall_acceptance_proportions": {
            k: str(v) for k, v in acceptance_proportions(all_raw_results).items()
        },
        "overall_median_absolute_circumference_error_cm": _stringify_optional_decimal(
            median_absolute_error([m.circumference for m in metrics])
        ),
        "overall_median_absolute_height_error_cm": _stringify_optional_decimal(
            median_absolute_error([m.height for m in metrics])
        ),
    }

    failure_modes = failure_mode_counts(all_raw_results)
    assumption_rows = review_assumptions(expectations, trial_reasons, metrics_by_trial)

    _write_metrics_json(output_dir, overall, group_summaries, failure_modes)
    _write_trial_results_csv(output_dir, metrics)
    _write_failed_trials_md(output_dir, failures, expectations, metrics_by_trial)
    _write_assumption_review_md(output_dir, assumption_rows)
    _write_recommended_decisions_md(output_dir, group_recommendations)
    _write_summary_md(output_dir, overall, group_summaries, failure_modes, len(expectations))


def _load_trial_reasons(trials_dir: Path) -> dict[str, tuple[str, list[str]]]:
    matrix_path = trials_dir / "trial-matrix.json"
    rows = json.loads(matrix_path.read_text(encoding="utf-8-sig"))
    return {
        row["trial_id"]: (
            row["reason"],
            [a.strip() for a in row["assumptions_tested"].split(";") if a.strip()],
        )
        for row in rows
    }


def _write_metrics_json(
    output_dir: Path,
    overall: dict[str, object],
    group_summaries: dict[str, dict[str, dict[str, object]]],
    failure_modes: dict[str, int],
) -> None:
    payload = {"overall": overall, "groups": group_summaries, "failure_mode_counts": failure_modes}
    (output_dir / "metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


def _write_trial_results_csv(output_dir: Path, metrics: list[ResultMetrics]) -> None:
    fieldnames = [
        "trial_id",
        "tester_id",
        "circumference_actual_cm",
        "circumference_expected_cm",
        "circumference_error_cm",
        "height_actual_cm",
        "height_expected_cm",
        "height_error_cm",
        "correction_rate",
        "arithmetic_failure",
        "acceptance",
        "status",
    ]
    with (output_dir / "trial-results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in metrics:
            writer.writerow(
                {
                    "trial_id": item.trial.trial_id,
                    "tester_id": item.result.tester.tester_id,
                    "circumference_actual_cm": str(item.circumference.actual),
                    "circumference_expected_cm": str(item.circumference.expected),
                    "circumference_error_cm": str(item.circumference.absolute_error_cm),
                    "height_actual_cm": str(item.height.actual),
                    "height_expected_cm": str(item.height.expected),
                    "height_error_cm": str(item.height.absolute_error_cm),
                    "correction_rate": str(item.correction_rate),
                    "arithmetic_failure": item.arithmetic_failure,
                    "acceptance": item.result.ratings.acceptance.value,
                    "status": item.result.status.value,
                }
            )


def _write_failed_trials_md(
    output_dir: Path,
    failures: list[IngestionFailure],
    expectations: dict[str, TrialExpectation],
    metrics_by_trial: dict[str, list[ResultMetrics]],
) -> None:
    lines = ["# Failed / missing trials", ""]

    lines.append("## Result files that failed ingestion")
    if failures:
        for failure in failures:
            lines.append(f"- `{failure.path.name}`: {failure.error}")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Trials with no submitted results yet")
    missing = [tid for tid in expectations if tid not in metrics_by_trial]
    if missing:
        for trial_id in missing:
            lines.append(f"- {trial_id}")
    else:
        lines.append("(none — every trial in the matrix has at least one result)")
    lines.append("")

    (output_dir / "failed-trials.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_assumption_review_md(output_dir: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# Assumption review",
        "",
        "Verdicts are derived only from submitted physical results.",
        "",
    ]
    lines.append("| Trial | Assumption | Verdict | Evidence count |")
    lines.append("|---|---|---|---:|")
    for row in rows:
        lines.append(
            f"| {row['trial_id']} | {row['assumption']} | {row['verdict']} | "
            f"{row['evidence_count']} |"
        )
    (output_dir / "assumption-review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_recommended_decisions_md(
    output_dir: Path, group_recommendations: dict[str, list[dict[str, object]]]
) -> None:
    lines = [
        "# Recommended decisions",
        "",
        "**These are recommendations for human crochet-expert review, not "
        "automated decisions.** Nothing in this codebase changes engine "
        "formulas, ranges, or schedules based on this file. Numeric "
        "dimensional tolerances are intentionally not applied here — see "
        "docs/decision-gates.md for which thresholds still need expert "
        "approval.",
        "",
    ]
    for grouping, recommendations in group_recommendations.items():
        lines.append(f"## {grouping.replace('_', ' ')}")
        for rec in recommendations:
            lines.append(
                f"- **{rec['label']}** → `{rec['recommendation']}` "
                f"({rec['evidence_count']} result(s)): {rec['rationale']}"
            )
        lines.append("")
    (output_dir / "recommended-decisions.md").write_text("\n".join(lines), encoding="utf-8")


def _write_summary_md(
    output_dir: Path,
    overall: dict[str, object],
    group_summaries: dict[str, dict[str, dict[str, object]]],
    failure_modes: dict[str, int],
    total_trials_in_matrix: int,
) -> None:
    lines = ["# Physical evaluation summary", ""]
    lines.append(
        f"{overall['total_results_ingested']} result(s) ingested across "
        f"{overall['trials_with_results']} of {total_trials_in_matrix} trials "
        f"in the matrix. {overall['total_ingestion_failures']} file(s) failed "
        f"ingestion — see failed-trials.md."
    )
    lines.append("")
    lines.append("## Observations (measured facts)")
    lines.append(f"- Overall arithmetic-failure rate: {overall['overall_arithmetic_failure_rate']}")
    lines.append(
        f"- Overall median absolute circumference error: "
        f"{overall['overall_median_absolute_circumference_error_cm']} cm"
    )
    lines.append(
        f"- Overall median absolute height error: "
        f"{overall['overall_median_absolute_height_error_cm']} cm"
    )
    lines.append("- Acceptance proportions (never combined into one score):")
    acceptance_proportions_by_status = cast(
        "dict[str, str]", overall["overall_acceptance_proportions"]
    )
    for status, proportion in acceptance_proportions_by_status.items():
        lines.append(f"  - {status}: {proportion}")
    lines.append("")
    if failure_modes:
        lines.append("## Repeated failure modes (count of results exhibiting each)")
        for mode, count in sorted(failure_modes.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {mode}: {count}")
        lines.append("")

    lines.append("## Interpretation (see recommended-decisions.md, assumption-review.md)")
    lines.append(
        "This file reports observations only. Continue/narrow/redesign "
        "recommendations, and which assumptions are supported or "
        "contradicted, are in the other generated files — kept separate so "
        "measured facts are never mixed with interpretation."
    )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ["generate_evaluation_report"]
