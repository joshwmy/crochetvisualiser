"""Gauge and optional materials metadata.

Gauge is the authoritative relation between stitch/round counts and real
centimetres (decision package §14, "Design principles"). It must be
user-measured; Phase 1 has no automatic gauge inference.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from crochet_reconstruction.domain.enums import StitchFamily

_TEN = Decimal(10)


class Gauge(BaseModel):
    """Stitch and round gauge, measured over a 10 cm swatch."""

    model_config = ConfigDict(frozen=True)

    stitch_family: StitchFamily = Field(description="Body stitch the gauge was measured in.")
    stitches_per_10cm: Decimal = Field(
        gt=0,
        le=100,
        description="Stitch gauge: number of stitches spanning 10 cm.",
    )
    rounds_per_10cm: Decimal = Field(
        gt=0,
        le=100,
        description="Round gauge: number of rounds spanning 10 cm.",
    )

    @property
    def stitches_per_cm(self) -> Decimal:
        return self.stitches_per_10cm / _TEN

    @property
    def rounds_per_cm(self) -> Decimal:
        return self.rounds_per_10cm / _TEN


class YarnMetadata(BaseModel):
    """Optional, user-entered yarn description. Never inferred from images."""

    model_config = ConfigDict(frozen=True)

    weight_category: str | None = Field(
        default=None,
        max_length=40,
        description='User-entered yarn weight/category label, e.g. "DK", "Worsted".',
    )
    fibre: str | None = Field(default=None, max_length=80)


class HookMetadata(BaseModel):
    """Optional, user-entered hook size. Never inferred from images or gauge."""

    model_config = ConfigDict(frozen=True)

    hook_mm: Decimal | None = Field(default=None, gt=0, le=25)
