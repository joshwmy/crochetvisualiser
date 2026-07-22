"""The Phase 1.5 physical-validation trial matrix.

Ten trials (``BV-001``…``BV-010``) selected to stress the *boundaries* of
the currently-declared supported ranges (head circumference, stitch gauge,
round gauge, negative ease) rather than comfortable mid-range values —
mid-range behaviour is already covered by Phase 1's property tests. This is
a hand-constructed, pairwise-*inspired* selection, not a certified
orthogonal covering array; every level of every variable appears at least
twice, and both range extremes are represented for every numeric variable.
See docs/physical-validation-protocol.md for the full rationale.

Trial IDs, and therefore every value here, are fixed literals — there is no
randomness anywhere in this module, so trial generation is deterministic by
construction (verified by a test, not just asserted here).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from crochet_reconstruction.domain.enums import BrimType, Construction, StitchFamily
from crochet_reconstruction.domain.gauge import Gauge
from crochet_reconstruction.domain.measurements import UserMeasurements
from crochet_reconstruction.domain.pattern import (
    Pattern,
    ProjectInput,
    ProjectMetadata,
    TemplateRef,
)
from crochet_reconstruction.engine.compiler import compile_pattern

_TEMPLATE_REF = TemplateRef(id="top_down_basic", version="1.0.0")


class TrialConfig(BaseModel):
    """One physical-trial input specification, plus why it exists."""

    model_config = ConfigDict(frozen=True)

    trial_id: str
    reason: str
    assumptions_tested: list[str]

    stitch_family: StitchFamily
    head_circumference_cm: Decimal
    target_height_cm: Decimal
    brim_height_cm: Decimal | None
    stitches_per_10cm: Decimal
    rounds_per_10cm: Decimal
    negative_ease_pct: Decimal
    brim_type: BrimType


def build_project_input(trial: TrialConfig) -> ProjectInput:
    """Deterministically build the ``ProjectInput`` for one trial."""
    return ProjectInput(
        project=ProjectMetadata(
            project_id=trial.trial_id,
            title=f"Physical Validation {trial.trial_id}",
        ),
        template=_TEMPLATE_REF,
        measurements=UserMeasurements(
            head_circumference_cm=trial.head_circumference_cm,
            target_height_cm=trial.target_height_cm,
            brim_height_cm=trial.brim_height_cm,
        ),
        gauge=Gauge(
            stitch_family=trial.stitch_family,
            stitches_per_10cm=trial.stitches_per_10cm,
            rounds_per_10cm=trial.rounds_per_10cm,
        ),
        negative_ease_pct=trial.negative_ease_pct,
        construction=Construction.CONTINUOUS,
        brim_type=trial.brim_type,
    )


def compile_trial(trial: TrialConfig) -> Pattern:
    """Compile a trial through the unmodified Phase 1 engine.

    Raises the same domain errors ``compile_pattern`` would for any other
    input if a trial's measurements/gauge turn out to be unsatisfiable —
    that is a trial-matrix authoring bug (fix the trial's height/brim
    depth), not something this function should swallow.
    """
    return compile_pattern(build_project_input(trial))


def input_filename(trial: TrialConfig) -> str:
    return f"{trial.trial_id}.json"


@dataclass(frozen=True, slots=True)
class TrialRow:
    """One row of the trial matrix export (CSV/JSON), per the required schema."""

    trial_id: str
    input_filename: str
    stitch_family: str
    head_circumference_cm: str
    target_finished_circumference_cm: str
    target_height_cm: str
    stitches_per_10cm: str
    rounds_per_10cm: str
    negative_ease_pct: str
    brim_type: str
    calculated_crown_diameter_cm: str
    final_body_stitch_count: int
    crown_round_count: int
    body_round_count: int
    brim_round_count: int
    pattern_fingerprint: str
    validation_status: str
    assumptions_tested: str
    reason: str


def build_trial_row(trial: TrialConfig, pattern: Pattern) -> TrialRow:
    assert pattern.validation is not None
    assert pattern.fingerprint is not None
    calculated = pattern.calculated
    return TrialRow(
        trial_id=trial.trial_id,
        input_filename=input_filename(trial),
        stitch_family=trial.stitch_family.value,
        head_circumference_cm=str(trial.head_circumference_cm),
        target_finished_circumference_cm=str(calculated.target_circumference_cm),
        target_height_cm=str(trial.target_height_cm),
        stitches_per_10cm=str(trial.stitches_per_10cm),
        rounds_per_10cm=str(trial.rounds_per_10cm),
        negative_ease_pct=str(trial.negative_ease_pct),
        brim_type=trial.brim_type.value,
        calculated_crown_diameter_cm=str(calculated.crown_diameter_cm),
        final_body_stitch_count=calculated.body_stitch_count,
        crown_round_count=calculated.crown_round_count,
        body_round_count=calculated.body_round_count,
        brim_round_count=calculated.brim_round_count,
        pattern_fingerprint=pattern.fingerprint,
        validation_status=pattern.validation.status.value,
        assumptions_tested="; ".join(trial.assumptions_tested),
        reason=trial.reason,
    )


def build_trial_matrix_rows() -> list[tuple[TrialConfig, Pattern, TrialRow]]:
    """Compile every trial and return (config, pattern, row) triples, in order."""
    results = []
    for trial in TRIAL_MATRIX:
        pattern = compile_trial(trial)
        row = build_trial_row(trial, pattern)
        results.append((trial, pattern, row))
    return results


MINIMUM_TRIAL_SET: tuple[str, ...] = ("BV-001", "BV-002", "BV-004", "BV-006")
"""If resources allow only 4-6 physical beanies, make these first (see
docs/physical-validation-protocol.md for the coverage rationale). BV-003 and
BV-005 are the recommended next two if capacity allows 6."""

RECOMMENDED_EXTENDED_MINIMUM_SET: tuple[str, ...] = (*MINIMUM_TRIAL_SET, "BV-003", "BV-005")


TRIAL_MATRIX: list[TrialConfig] = [
    TrialConfig(
        trial_id="BV-001",
        reason=(
            "All-minimum boundary corner: smallest supported head, lowest "
            "stitch gauge, lowest round gauge, zero ease, no brim. Tests "
            "whether the low end of every range is simultaneously usable."
        ),
        assumptions_tested=[
            "supported range floor (head circumference, stitch gauge, round gauge)",
            "zero negative ease produces a wearable (not just mathematically valid) fit",
            "crown schedule m in {6,8} at low stitch gauge",
        ],
        stitch_family=StitchFamily.SC,
        head_circumference_cm=Decimal("42.0"),
        target_height_cm=Decimal("22.0"),
        brim_height_cm=None,
        stitches_per_10cm=Decimal("10.0"),
        rounds_per_10cm=Decimal("7.0"),
        negative_ease_pct=Decimal("0.0"),
        brim_type=BrimType.NONE,
    ),
    TrialConfig(
        trial_id="BV-002",
        reason=(
            "All-maximum boundary corner (paired with BV-001): mid-size head, "
            "highest stitch and round gauge, maximum ease, BLO brim. Tests "
            "the high end of every range plus the BLO brim at fine gauge."
        ),
        assumptions_tested=[
            "supported range ceiling (stitch gauge, round gauge, ease)",
            "BLO brim behaviour at fine gauge",
            "12% ease does not produce an unwearably tight fit",
        ],
        stitch_family=StitchFamily.SC,
        head_circumference_cm=Decimal("54.0"),
        target_height_cm=Decimal("22.0"),
        brim_height_cm=Decimal("4.0"),
        stitches_per_10cm=Decimal("24.0"),
        rounds_per_10cm=Decimal("20.0"),
        negative_ease_pct=Decimal("12.0"),
        brim_type=BrimType.BLO_IN_ROUND,
    ),
    TrialConfig(
        trial_id="BV-003",
        reason=(
            "Largest supported head at low round gauge with zero ease and a "
            "brim: tests whether the crown schedule still closes cleanly "
            "when many crown rounds are needed (large head, coarse gauge)."
        ),
        assumptions_tested=[
            "supported range ceiling (head circumference)",
            "crown schedule stability with a high crown-round count",
            "zero ease at the largest supported size",
        ],
        stitch_family=StitchFamily.SC,
        head_circumference_cm=Decimal("64.0"),
        target_height_cm=Decimal("28.0"),
        brim_height_cm=Decimal("4.0"),
        stitches_per_10cm=Decimal("16.0"),
        rounds_per_10cm=Decimal("7.0"),
        negative_ease_pct=Decimal("0.0"),
        brim_type=BrimType.BLO_IN_ROUND,
    ),
    TrialConfig(
        trial_id="BV-004",
        reason=(
            "hdc counterpart to BV-002's high-gauge corner, no brim: isolates "
            "whether hdc specifically behaves differently from sc at the "
            "gauge/ease ceiling (a documented 'narrow to one stitch' trigger)."
        ),
        assumptions_tested=[
            "hdc crown schedule at high stitch/round gauge",
            "hdc does not require a different increase schedule than sc",
        ],
        stitch_family=StitchFamily.HDC,
        head_circumference_cm=Decimal("42.0"),
        target_height_cm=Decimal("22.0"),
        brim_height_cm=None,
        stitches_per_10cm=Decimal("24.0"),
        rounds_per_10cm=Decimal("20.0"),
        negative_ease_pct=Decimal("12.0"),
        brim_type=BrimType.NONE,
    ),
    TrialConfig(
        trial_id="BV-005",
        reason=(
            "hdc at the low-gauge, high-ease corner with a brim: isolates "
            "whether hdc's taller stitch height interacts badly with coarse "
            "gauge and high ease (a plausible physical failure mode not "
            "visible to any software test)."
        ),
        assumptions_tested=[
            "hdc crown schedule at low stitch/round gauge",
            "BLO brim with hdc",
            "12% ease with hdc's taller stitch",
        ],
        stitch_family=StitchFamily.HDC,
        head_circumference_cm=Decimal("54.0"),
        target_height_cm=Decimal("22.0"),
        brim_height_cm=Decimal("4.0"),
        stitches_per_10cm=Decimal("10.0"),
        rounds_per_10cm=Decimal("7.0"),
        negative_ease_pct=Decimal("12.0"),
        brim_type=BrimType.BLO_IN_ROUND,
    ),
    TrialConfig(
        trial_id="BV-006",
        reason=(
            "hdc counterpart to BV-003: largest head, high round gauge, zero "
            "ease, no brim. Completes the 2x2 (stitch x brim) coverage at "
            "the large-head/zero-ease corner."
        ),
        assumptions_tested=[
            "hdc crown schedule at the largest supported head",
            "zero ease with hdc",
        ],
        stitch_family=StitchFamily.HDC,
        head_circumference_cm=Decimal("64.0"),
        target_height_cm=Decimal("24.0"),
        brim_height_cm=None,
        stitches_per_10cm=Decimal("16.0"),
        rounds_per_10cm=Decimal("20.0"),
        negative_ease_pct=Decimal("0.0"),
        brim_type=BrimType.NONE,
    ),
    TrialConfig(
        trial_id="BV-007",
        reason=(
            "sc at low stitch gauge crossed with high round gauge (the pair "
            "not yet hit by BV-001/002): tests a gauge-ratio extreme that "
            "drives the k=2*pi*g_s/g_r increase-rate estimate to its low end."
        ),
        assumptions_tested=[
            "increase-rate estimate k at a low-gauge-ratio extreme",
            "crown schedule choice (m in {6,8}) at that extreme",
        ],
        stitch_family=StitchFamily.SC,
        head_circumference_cm=Decimal("54.0"),
        target_height_cm=Decimal("22.0"),
        brim_height_cm=None,
        stitches_per_10cm=Decimal("10.0"),
        rounds_per_10cm=Decimal("20.0"),
        negative_ease_pct=Decimal("0.0"),
        brim_type=BrimType.NONE,
    ),
    TrialConfig(
        trial_id="BV-008",
        reason=(
            "hdc at mid stitch gauge, low round gauge, zero ease, with a "
            "brim, on the smallest supported head: tests the BLO brim "
            "specifically at the small-head boundary."
        ),
        assumptions_tested=[
            "BLO brim at the smallest supported head",
            "hdc at mid stitch gauge / low round gauge",
        ],
        stitch_family=StitchFamily.HDC,
        head_circumference_cm=Decimal("42.0"),
        target_height_cm=Decimal("22.0"),
        brim_height_cm=Decimal("4.0"),
        stitches_per_10cm=Decimal("16.0"),
        rounds_per_10cm=Decimal("7.0"),
        negative_ease_pct=Decimal("0.0"),
        brim_type=BrimType.BLO_IN_ROUND,
    ),
    TrialConfig(
        trial_id="BV-009",
        reason=(
            "sc at the small-head/high-gauge-ratio extreme opposite BV-007, "
            "maximum ease, with a brim: the remaining unhit corner of the "
            "gauge-ratio x ease design space for sc."
        ),
        assumptions_tested=[
            "increase-rate estimate k at a high-gauge-ratio extreme",
            "12% ease on the smallest supported head",
            "BLO brim with sc at fine-ish gauge",
        ],
        stitch_family=StitchFamily.SC,
        head_circumference_cm=Decimal("42.0"),
        target_height_cm=Decimal("22.0"),
        brim_height_cm=Decimal("4.0"),
        stitches_per_10cm=Decimal("16.0"),
        rounds_per_10cm=Decimal("20.0"),
        negative_ease_pct=Decimal("12.0"),
        brim_type=BrimType.BLO_IN_ROUND,
    ),
    TrialConfig(
        trial_id="BV-010",
        reason=(
            "hdc at mid head size, high stitch gauge, low round gauge, "
            "maximum ease, no brim: completes hdc's coverage of the "
            "gauge-ratio extreme opposite BV-005."
        ),
        assumptions_tested=[
            "increase-rate estimate k at a high-gauge-ratio extreme with hdc",
            "12% ease with hdc, no brim",
        ],
        stitch_family=StitchFamily.HDC,
        head_circumference_cm=Decimal("54.0"),
        target_height_cm=Decimal("26.0"),
        brim_height_cm=None,
        stitches_per_10cm=Decimal("24.0"),
        rounds_per_10cm=Decimal("7.0"),
        negative_ease_pct=Decimal("12.0"),
        brim_type=BrimType.NONE,
    ),
]

_ids = [t.trial_id for t in TRIAL_MATRIX]
assert len(_ids) == len(set(_ids)), "trial IDs must be unique"
