"""Typed, validated user measurements.

Field bounds here are sanity limits (catch unit mistakes, negative values,
typos) enforced unconditionally by Pydantic — construction fails loudly via
``pydantic.ValidationError`` rather than clamping or silently repairing a
value. The *narrower* template-supported range (e.g. "adult beanies between
42 and 64 cm head circumference") is a separate, template-specific check
performed by the validator (rule ``V-RANGE-001``), because that range can
legitimately differ between templates and template versions.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UserMeasurements(BaseModel):
    """Manually entered measurements. No measurement is inferred from images."""

    model_config = ConfigDict(frozen=True)

    head_circumference_cm: Decimal = Field(
        gt=0,
        le=200,
        description="Wearer's head circumference in centimetres.",
    )
    target_height_cm: Decimal = Field(
        gt=0,
        le=100,
        description="Desired finished hat height, crown to brim edge, in centimetres.",
    )
    brim_height_cm: Decimal | None = Field(
        default=None,
        gt=0,
        le=30,
        description=(
            "Desired brim depth in centimetres. Required only when brim_type "
            "is not BrimType.NONE; enforced at the project-input level."
        ),
    )
