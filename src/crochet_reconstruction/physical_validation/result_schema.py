"""Typed schema for a completed physical trial result.

This is raw observation data submitted by a real tester after crocheting a
generated pattern. Nothing here is computed by the engine — every field is
either what the tester directly reports or a rating they assign. Metrics
derived *from* this data (error percentages, correction rates, etc.) live
in :mod:`crochet_reconstruction.physical_validation.metrics` and are kept
strictly separate so raw observations are never silently overwritten by
calculated values, and so calculated values are never mistaken for
additional raw data.

Personal information is intentionally minimal: a tester ID (a code, not a
name), experience level, stitch familiarity, and handedness — nothing more.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    PROFESSIONAL = "professional"


class StitchFamiliarity(StrEnum):
    NEW_TO_IT = "new_to_it"
    COMFORTABLE = "comfortable"
    VERY_FAMILIAR = "very_familiar"


class Handedness(StrEnum):
    RIGHT = "right"
    LEFT = "left"


class GaugeMatch(StrEnum):
    YES = "yes"
    NO = "no"
    CLOSE = "close"


class AcceptanceStatus(StrEnum):
    ACCEPTABLE_NO_CORRECTION = "acceptable_no_correction"
    ACCEPTABLE_MINOR_CORRECTION = "acceptable_minor_correction"
    REQUIRES_MAJOR_CORRECTION = "requires_major_correction"
    UNUSABLE = "unusable"


class TrialStatus(StrEnum):
    """Submission completeness — distinct from crochet-quality acceptance
    (see :class:`AcceptanceStatus`), which lives in ``ExpertRatings``."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    ABANDONED = "abandoned"


class TesterInfo(BaseModel):
    __test__ = False  # not a pytest test class - name just happens to start with "Test"

    model_config = ConfigDict(frozen=True)

    tester_id: str = Field(min_length=1, max_length=60, description="A code, not a name.")
    experience_level: ExperienceLevel
    stitch_familiarity: StitchFamiliarity
    handedness: Handedness
    yarn_substitution: str | None = None
    hook_substitution: str | None = None


class PreCrochetInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    yarn_brand: str | None = None
    yarn_fibre: str | None = None
    yarn_weight: str | None = None
    hook_size_mm: Decimal | None = Field(default=None, gt=0, le=25)
    measured_stitches_per_10cm: Decimal = Field(gt=0, le=100)
    measured_rounds_per_10cm: Decimal = Field(gt=0, le=100)
    gauge_matched_request: GaugeMatch
    modifications_before_starting: str | None = None


class RoundCorrection(BaseModel):
    """A single instruction the tester had to manually correct while working."""

    model_config = ConfigDict(frozen=True)

    round_number: int = Field(ge=1)
    problem: str = Field(min_length=1)
    correction: str = Field(min_length=1)


class DuringCrochetEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    instructions_understandable: bool
    abbreviations_clear: bool
    round_totals_matched: bool
    remained_flat_during_crown: bool
    crown_cupped_early: bool
    crown_rippled: bool
    increases_well_distributed: bool
    crown_to_body_transition_sensible: bool
    blo_brim_behaved_as_expected: bool | None = Field(
        default=None, description="None means the trial had no brim (not applicable)."
    )
    corrected_rounds: list[RoundCorrection] = Field(default_factory=list)


class FinishedMeasurements(BaseModel):
    """Raw observed measurements. Never overwritten by engine expectations."""

    model_config = ConfigDict(frozen=True)

    relaxed_circumference_cm: Decimal = Field(gt=0, le=200)
    stretched_circumference_cm: Decimal | None = Field(default=None, gt=0, le=200)
    total_height_cm: Decimal = Field(gt=0, le=100)
    crown_diameter_cm: Decimal | None = Field(default=None, gt=0, le=100)
    brim_height_cm: Decimal | None = Field(default=None, gt=0, le=30)
    weight_g: Decimal | None = Field(default=None, gt=0, le=2000)
    yarn_used_g: Decimal | None = Field(default=None, gt=0, le=2000)
    yarn_used_m: Decimal | None = Field(default=None, gt=0, le=2000)


class ExpertRatings(BaseModel):
    """Anchored 1-5 scales — see docs/expert-evaluation-rubric.md for anchors."""

    model_config = ConfigDict(frozen=True)

    mathematical_correctness: int = Field(ge=1, le=5)
    instruction_clarity: int = Field(ge=1, le=5)
    construction_plausibility: int = Field(ge=1, le=5)
    fit: int = Field(ge=1, le=5)
    shape: int = Field(ge=1, le=5)
    visual_quality: int = Field(ge=1, le=5)
    beginner_suitability: int = Field(ge=1, le=5)
    overall_usability: int = Field(ge=1, le=5)
    would_use_again: bool
    would_recommend: bool
    acceptance: AcceptanceStatus


class PhysicalTrialResult(BaseModel):
    """One tester's complete, raw report on one physical trial.

    Multiple results may share the same ``trial_id`` (multiple testers
    evaluating the same generated pattern) — this model does not aggregate
    anything; aggregation happens only at the reporting stage
    (:mod:`crochet_reconstruction.physical_validation.evaluation_report`),
    never here and never during ingestion.
    """

    model_config = ConfigDict(frozen=True)

    trial_id: str = Field(min_length=1)
    pattern_fingerprint: str = Field(min_length=1)
    tester: TesterInfo
    pre_crochet: PreCrochetInfo
    during_crochet: DuringCrochetEvaluation
    finished_measurements: FinishedMeasurements
    ratings: ExpertRatings
    status: TrialStatus
    notes: str | None = None
