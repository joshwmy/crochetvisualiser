"""Top-level structured pattern: the single source of truth.

``Pattern`` is what the compiler produces, the validator inspects, and the
renderer reads from. Nothing about a pattern's meaning is ever recovered by
parsing the human-readable text — the renderer is a one-way, read-only view
of this object (see :mod:`crochet_reconstruction.rendering.text_renderer`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crochet_reconstruction.domain.enums import (
    AssumptionSource,
    BrimType,
    Construction,
    PatternStatus,
    Severity,
    Terminology,
)
from crochet_reconstruction.domain.gauge import Gauge, HookMetadata, YarnMetadata
from crochet_reconstruction.domain.measurements import UserMeasurements
from crochet_reconstruction.domain.rounds import Component

SCHEMA_VERSION = "0.1.0"
"""Schema version of this structured representation. See docs/pattern-format.md."""


class TemplateRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: str


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)


class ProjectInput(BaseModel):
    """Validated user input: measurements + gauge + selected template + choices.

    This is the object at the top of the required flow
    ("Measurements + gauge + selected template"). Every field here is either
    required and user-supplied, or explicitly optional with no silent
    default substituted for a missing value.
    """

    model_config = ConfigDict(frozen=True)

    project: ProjectMetadata
    terminology: Terminology = Terminology.US
    template: TemplateRef
    measurements: UserMeasurements
    gauge: Gauge
    negative_ease_pct: Decimal = Field(
        ge=0,
        le=50,
        description=(
            "Negative ease as a percentage (e.g. 8 for 8%). Sanity-bounded here; "
            "the template's narrower supported range is enforced by the validator "
            "(rule V-RANGE-001), since it can vary by template."
        ),
    )
    construction: Construction
    brim_type: BrimType
    yarn: YarnMetadata | None = None
    hook: HookMetadata | None = None

    @model_validator(mode="after")
    def _brim_height_required_when_brim_enabled(self) -> ProjectInput:
        if self.brim_type is not BrimType.NONE and self.measurements.brim_height_cm is None:
            raise ValueError(
                f"measurements.brim_height_cm is required when brim_type is "
                f"{self.brim_type.value!r}"
            )
        return self


class Assumption(BaseModel):
    """A recorded fact/choice that materially affects the compiled pattern."""

    model_config = ConfigDict(frozen=True)

    id: str
    field: str
    value: str
    source: AssumptionSource
    note: str | None = None


class CalculatedParameters(BaseModel):
    """Every intermediate and final value the sizing/crown/body/brim engines derive.

    Kept as its own object (rather than folded into ``Pattern`` directly) so
    the "raw calculated value, final compatible value, resulting deviation"
    triple the decision package requires (§14, "Body stitch count") has an
    explicit, testable home distinct from the compiled rounds themselves.
    """

    model_config = ConfigDict(frozen=True)

    target_circumference_cm: Decimal
    crown_diameter_cm: Decimal
    body_stitch_count_raw: Decimal
    body_stitch_count: int
    repeat_multiple: int
    circumference_deviation_cm: Decimal
    total_rounds_for_height: int
    crown_round_count: int
    body_round_count: int
    brim_round_count: int
    starting_stitch_count: int


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    severity: Severity
    path: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: PatternStatus
    engine_version: str
    results: list[ValidationResult] = Field(default_factory=list)

    @property
    def has_fatal(self) -> bool:
        return any(r.severity is Severity.FATAL for r in self.results)


class Pattern(BaseModel):
    """The complete structured pattern: source of truth for everything else."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    input: ProjectInput
    calculated: CalculatedParameters
    assumptions: list[Assumption] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    validation: ValidationReport | None = None
    fingerprint: str | None = None
