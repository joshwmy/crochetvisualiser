import json
from decimal import Decimal
from pathlib import Path

from crochet_reconstruction.physical_validation.evaluation_report import (
    ResultMetrics,
    TrialExpectation,
    failure_mode_counts,
    gauge_bucket,
    generate_evaluation_report,
    recommend_for_group,
    size_bucket,
)
from crochet_reconstruction.physical_validation.metrics import circumference_error, height_error
from crochet_reconstruction.physical_validation.result_schema import (
    AcceptanceStatus,
    RoundCorrection,
)
from crochet_reconstruction.physical_validation.review_pack import generate_expert_review_pack
from crochet_reconstruction.physical_validation.trial_matrix import TRIAL_MATRIX, compile_trial
from tests.physical_validation.conftest import make_synthetic_result

_EXPECTATION = TrialExpectation(
    trial_id="BV-001",
    stitch_family="sc",
    brim_type="none",
    head_circumference_cm=Decimal("42.0"),
    stitches_per_10cm=Decimal("10.0"),
    rounds_per_10cm=Decimal("7.0"),
    negative_ease_pct=Decimal("0.0"),
    target_finished_circumference_cm=Decimal("42.0"),
    target_height_cm=Decimal("22.0"),
    calculated_crown_diameter_cm=Decimal("13.4"),
    crown_round_count=5,
    body_round_count=10,
    brim_round_count=0,
)


def _metrics_item(*, acceptance: AcceptanceStatus, arithmetic_failure: bool) -> ResultMetrics:
    result = make_synthetic_result(
        acceptance=acceptance, round_totals_matched=not arithmetic_failure
    )
    return ResultMetrics(
        result=result,
        trial=_EXPECTATION,
        circumference=circumference_error(Decimal("42.0"), Decimal("42.0")),
        height=height_error(Decimal("22.0"), Decimal("22.0")),
        crown_diameter=None,
        correction_rate=Decimal(0),
        arithmetic_failure=arithmetic_failure,
    )


def test_gauge_bucket_boundaries() -> None:
    assert gauge_bucket(Decimal("13")) == gauge_bucket(Decimal("10"))
    assert gauge_bucket(Decimal("14")) != gauge_bucket(Decimal("13"))
    assert gauge_bucket(Decimal("24")) == gauge_bucket(Decimal("20"))


def test_size_bucket_boundaries() -> None:
    assert size_bucket(Decimal("46")) != size_bucket(Decimal("47"))
    assert size_bucket(Decimal("58")) != size_bucket(Decimal("59"))


def test_recommend_continue_when_no_failures() -> None:
    items = [
        _metrics_item(
            acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION, arithmetic_failure=False
        )
        for _ in range(3)
    ]
    rec = recommend_for_group("sc", items)
    assert rec["recommendation"] == "continue"


def test_recommend_narrow_or_redesign_on_any_arithmetic_failure() -> None:
    items = [
        _metrics_item(
            acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION, arithmetic_failure=False
        ),
        _metrics_item(
            acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION, arithmetic_failure=True
        ),
    ]
    rec = recommend_for_group("sc", items)
    assert rec["recommendation"] == "narrow_or_redesign"


def test_recommend_narrow_when_majority_poor_ratings() -> None:
    items = [
        _metrics_item(acceptance=AcceptanceStatus.UNUSABLE, arithmetic_failure=False),
        _metrics_item(
            acceptance=AcceptanceStatus.REQUIRES_MAJOR_CORRECTION, arithmetic_failure=False
        ),
        _metrics_item(
            acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION, arithmetic_failure=False
        ),
    ]
    rec = recommend_for_group("hdc", items)
    assert rec["recommendation"] == "narrow"


def test_recommend_continue_with_caution_for_minority_poor_ratings() -> None:
    items = [
        _metrics_item(acceptance=AcceptanceStatus.UNUSABLE, arithmetic_failure=False),
        _metrics_item(
            acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION, arithmetic_failure=False
        ),
        _metrics_item(
            acceptance=AcceptanceStatus.ACCEPTABLE_NO_CORRECTION, arithmetic_failure=False
        ),
    ]
    rec = recommend_for_group("hdc", items)
    assert rec["recommendation"] == "continue_with_caution"


def test_recommend_insufficient_data_when_empty() -> None:
    rec = recommend_for_group("hdc", [])
    assert rec["recommendation"] == "insufficient_data"
    assert rec["evidence_count"] == 0


def test_failure_mode_counts_counts_only_bad_outcomes() -> None:
    good = make_synthetic_result()
    bad_crown = make_synthetic_result(
        during_crochet=make_synthetic_result().during_crochet.model_copy(
            update={"crown_rippled": True}
        )
    )
    counts = failure_mode_counts([good, bad_crown])
    assert counts.get("crown_rippled") == 1
    assert "crown_cupped_early" not in counts


def _real_fingerprint(trial_id: str) -> str:
    trial = next(t for t in TRIAL_MATRIX if t.trial_id == trial_id)
    pattern = compile_trial(trial)
    assert pattern.fingerprint is not None
    return pattern.fingerprint


def test_generate_evaluation_report_end_to_end(tmp_path: Path) -> None:
    trials_dir = tmp_path / "expert_review"
    generate_expert_review_pack(trials_dir)

    results_dir = tmp_path / "results"
    results_dir.mkdir()

    good_result = make_synthetic_result(
        trial_id="BV-001",
        pattern_fingerprint=_real_fingerprint("BV-001"),
        tester_id="SYN-1",
    )
    (results_dir / "bv001.json").write_text(good_result.model_dump_json(), encoding="utf-8")

    failing_result = make_synthetic_result(
        trial_id="BV-004",
        pattern_fingerprint=_real_fingerprint("BV-004"),
        tester_id="SYN-2",
        round_totals_matched=False,
        corrected_rounds=[
            RoundCorrection(round_number=6, problem="count off", correction="added 2 sts")
        ],
    )
    (results_dir / "bv004.json").write_text(failing_result.model_dump_json(), encoding="utf-8")

    output_dir = tmp_path / "evaluation"
    generate_evaluation_report(trials_dir, results_dir, output_dir)

    for name in [
        "summary.md",
        "metrics.json",
        "trial-results.csv",
        "failed-trials.md",
        "assumption-review.md",
        "recommended-decisions.md",
    ]:
        assert (output_dir / name).exists(), f"missing {name}"

    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["overall"]["total_results_ingested"] == 2
    assert metrics["overall"]["trials_with_results"] == 2

    # sc (BV-001) had no arithmetic failure, hdc (BV-004) did.
    by_stitch = metrics["groups"]["by_stitch_family"]
    assert by_stitch["sc"]["arithmetic_failure_rate"] == "0"
    assert by_stitch["hdc"]["arithmetic_failure_rate"] == "1"

    failed_trials_text = (output_dir / "failed-trials.md").read_text(encoding="utf-8")
    # 8 of 10 trials have no submitted results.
    missing_count = sum(1 for t in TRIAL_MATRIX if t.trial_id not in ("BV-001", "BV-004"))
    for trial in TRIAL_MATRIX:
        if trial.trial_id not in ("BV-001", "BV-004"):
            assert trial.trial_id in failed_trials_text
    assert missing_count == len(TRIAL_MATRIX) - 2

    recommendations_text = (output_dir / "recommended-decisions.md").read_text(encoding="utf-8")
    assert "narrow_or_redesign" in recommendations_text  # hdc group, arithmetic failure
    assert "not automated decisions" in recommendations_text
