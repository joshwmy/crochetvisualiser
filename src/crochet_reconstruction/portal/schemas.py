"""Pydantic validation for contributor-submitted form data.

Routes parse raw form fields into these models before calling `services.*`
— validation errors are caught by the router and re-rendered as
plain-language messages next to the relevant field, with everything the
contributor already typed preserved (see `routers/contributor.py`).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, field_validator, model_validator

from crochet_reconstruction.portal.models import (
    AttributionPreference,
    ConstructionDirection,
    CraftType,
    GaugeBlockingState,
    ProjectCategory,
    RoundStyle,
    TriState,
    WorkedIn,
)

ALLOWED_STITCH_FAMILIES = frozenset({"sc", "hdc", "dc", "other", "unknown"})


def blank_to_none(value: object) -> object | None:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class ConsentInput(BaseModel):
    contributor_provided_identifier: str = Field(min_length=1, max_length=200)
    owns_photographs: bool = False
    research_evaluation_use: bool = False
    product_development_use: bool = False
    model_training_use: bool = False
    public_demonstration_use: bool = False
    contact_for_missing_details: bool = False
    privacy_notice_accepted: bool = False
    attribution_preference: AttributionPreference = AttributionPreference.ANONYMOUS
    attribution_text: str | None = Field(default=None, max_length=200)

    @field_validator("attribution_text", mode="before")
    @classmethod
    def _blank_attribution(cls, value: object) -> object | None:
        return blank_to_none(value)

    @model_validator(mode="after")
    def _required_permissions(self) -> ConsentInput:
        if not self.owns_photographs:
            raise ValueError(
                "you must confirm you own or control the photographs before submitting"
            )
        if not self.privacy_notice_accepted:
            raise ValueError("you must accept the privacy notice before submitting")
        return self


class ProjectDetailsInput(BaseModel):
    name_or_description: str | None = Field(default=None, max_length=300)
    craft_type: CraftType = CraftType.UNKNOWN
    project_category: ProjectCategory
    made_by_contributor: TriState = TriState.UNKNOWN
    used_existing_pattern: TriState = TriState.UNKNOWN
    pattern_owned_by_contributor: TriState = TriState.UNKNOWN
    construction_direction: ConstructionDirection = ConstructionDirection.UNKNOWN
    worked_in: WorkedIn = WorkedIn.UNKNOWN
    round_style: RoundStyle = RoundStyle.UNKNOWN
    stitch_families: list[str] = Field(default_factory=list)
    component_notes: str | None = Field(default=None, max_length=2000)
    free_text_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name_or_description", "component_notes", "free_text_notes", mode="before")
    @classmethod
    def _blank_text(cls, value: object) -> object | None:
        return blank_to_none(value)

    @field_validator("stitch_families")
    @classmethod
    def _validate_stitch_families(cls, value: list[str]) -> list[str]:
        unknown = set(value) - ALLOWED_STITCH_FAMILIES
        if unknown:
            raise ValueError(f"unrecognised stitch families: {sorted(unknown)}")
        return value


def _parse_optional_decimal(value: object, *, field_name: str) -> Decimal | None:
    cleaned = blank_to_none(value)
    if cleaned is None:
        return None
    try:
        return Decimal(str(cleaned))
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a number") from exc


class MaterialsAndGaugeInput(BaseModel):
    yarn_brand: str | None = Field(default=None, max_length=200)
    yarn_name: str | None = Field(default=None, max_length=200)
    fibre: str | None = Field(default=None, max_length=200)
    yarn_weight: str | None = Field(default=None, max_length=50)
    colour: str | None = Field(default=None, max_length=100)
    hook_mm: Decimal | None = Field(default=None, gt=0, le=25)
    strands_held: int | None = Field(default=None, ge=1, le=10)
    substitutions_made: bool | None = None
    materials_notes: str | None = Field(default=None, max_length=2000)

    stitches_per_10cm: Decimal | None = Field(default=None, gt=0, le=100)
    rounds_per_10cm: Decimal | None = Field(default=None, gt=0, le=100)
    gauge_blocking_state: GaugeBlockingState = GaugeBlockingState.UNKNOWN
    relaxed_circumference_cm: Decimal | None = Field(default=None, gt=0, le=200)
    stretched_circumference_cm: Decimal | None = Field(default=None, gt=0, le=200)
    total_height_cm: Decimal | None = Field(default=None, gt=0, le=100)
    crown_diameter_cm: Decimal | None = Field(default=None, gt=0, le=100)
    brim_height_cm: Decimal | None = Field(default=None, gt=0, le=30)
    swatch_flat_width_cm: Decimal | None = Field(default=None, gt=0, le=100)
    swatch_flat_height_cm: Decimal | None = Field(default=None, gt=0, le=100)
    measurement_notes: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "yarn_brand",
        "yarn_name",
        "fibre",
        "yarn_weight",
        "colour",
        "materials_notes",
        "measurement_notes",
        mode="before",
    )
    @classmethod
    def _blank_text(cls, value: object) -> object | None:
        return blank_to_none(value)

    @field_validator(
        "hook_mm",
        "stitches_per_10cm",
        "rounds_per_10cm",
        "relaxed_circumference_cm",
        "stretched_circumference_cm",
        "total_height_cm",
        "crown_diameter_cm",
        "brim_height_cm",
        "swatch_flat_width_cm",
        "swatch_flat_height_cm",
        mode="before",
    )
    @classmethod
    def _blank_decimal(cls, value: object) -> object | None:
        return blank_to_none(value)

    @field_validator("strands_held", mode="before")
    @classmethod
    def _blank_int(cls, value: object) -> object | None:
        return blank_to_none(value)


class TrialLinkInput(BaseModel):
    trial_id: str = Field(min_length=1, max_length=20)
    pattern_fingerprint: str = Field(min_length=1, max_length=64)
    physical_result_id: str | None = Field(default=None, max_length=100)

    @field_validator("physical_result_id", mode="before")
    @classmethod
    def _blank_text(cls, value: object) -> object | None:
        return blank_to_none(value)
