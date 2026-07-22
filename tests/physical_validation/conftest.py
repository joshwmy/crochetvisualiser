"""Shared helpers for Phase 1.5 tests.

Every result built here is SYNTHETIC test data — never a real physical
crochet result. Used only to exercise ingestion, metrics, and reporting
code paths.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from crochet_reconstruction.physical_validation.result_schema import (
    AcceptanceStatus,
    DuringCrochetEvaluation,
    ExperienceLevel,
    ExpertRatings,
    FinishedMeasurements,
    GaugeMatch,
    Handedness,
    PhysicalTrialResult,
    PreCrochetInfo,
    RoundCorrection,
    StitchFamiliarity,
    TesterInfo,
    TrialStatus,
)


def make_synthetic_result(
    trial_id: str = "BV-001",
    pattern_fingerprint: str = "synthetic-fingerprint",
    tester_id: str = "SYN-1",
    relaxed_circumference_cm: str = "42.0",
    total_height_cm: str = "22.0",
    round_totals_matched: bool = True,
    acceptance: AcceptanceStatus = AcceptanceStatus.ACCEPTABLE_NO_CORRECTION,
    corrected_rounds: list[RoundCorrection] | None = None,
    crown_diameter_cm: str | None = None,
    **overrides: Any,
) -> PhysicalTrialResult:
    """Build a SYNTHETIC PhysicalTrialResult for tests. Never real trial data."""
    payload: dict[str, Any] = {
        "trial_id": trial_id,
        "pattern_fingerprint": pattern_fingerprint,
        "tester": TesterInfo(
            tester_id=tester_id,
            experience_level=ExperienceLevel.INTERMEDIATE,
            stitch_familiarity=StitchFamiliarity.COMFORTABLE,
            handedness=Handedness.RIGHT,
        ),
        "pre_crochet": PreCrochetInfo(
            measured_stitches_per_10cm=Decimal("16.0"),
            measured_rounds_per_10cm=Decimal("12.0"),
            gauge_matched_request=GaugeMatch.YES,
        ),
        "during_crochet": DuringCrochetEvaluation(
            instructions_understandable=True,
            abbreviations_clear=True,
            round_totals_matched=round_totals_matched,
            remained_flat_during_crown=True,
            crown_cupped_early=False,
            crown_rippled=False,
            increases_well_distributed=True,
            crown_to_body_transition_sensible=True,
            blo_brim_behaved_as_expected=None,
            corrected_rounds=corrected_rounds or [],
        ),
        "finished_measurements": FinishedMeasurements(
            relaxed_circumference_cm=Decimal(relaxed_circumference_cm),
            total_height_cm=Decimal(total_height_cm),
            crown_diameter_cm=Decimal(crown_diameter_cm) if crown_diameter_cm else None,
        ),
        "ratings": ExpertRatings(
            mathematical_correctness=5,
            instruction_clarity=4,
            construction_plausibility=4,
            fit=4,
            shape=4,
            visual_quality=4,
            beginner_suitability=3,
            overall_usability=4,
            would_use_again=True,
            would_recommend=True,
            acceptance=acceptance,
        ),
        "status": TrialStatus.COMPLETED,
        "notes": "SYNTHETIC test data",
    }
    payload.update(overrides)
    return PhysicalTrialResult(**payload)
