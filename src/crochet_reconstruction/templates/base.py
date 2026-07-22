"""Template definition: the whitelist a pattern must be compiled against.

A template fixes what the engine is *allowed* to produce — supported
stitch families, construction styles, brim types, dimensional ranges, and
the crown increase schedules considered expert-approved. The engine
computes candidate values; the template constrains which candidates are
legal (decision package §14, "Design principles").
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from crochet_reconstruction.domain.enums import BrimType, Construction, StitchFamily


class DecimalRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    minimum: Decimal
    maximum: Decimal

    def contains(self, value: Decimal) -> bool:
        return self.minimum <= value <= self.maximum


class TemplateRanges(BaseModel):
    """Supported-range validation bounds (rule ``V-RANGE-001``).

    Numeric bounds are taken directly from the decision package's Experiment
    1 dataset specification (§7): the only concrete numeric ranges the
    source document commits to. They are a starting point for the POC, not
    a physically proven safe range, and are flagged for expert review in
    docs/mathematical-assumptions.md.
    """

    model_config = ConfigDict(frozen=True)

    head_circumference_cm: DecimalRange
    stitches_per_10cm: DecimalRange
    rounds_per_10cm: DecimalRange
    negative_ease_pct: DecimalRange


class CrownProfile(BaseModel):
    """Constraints on the crown increase schedule.

    ``allowed_increases_per_round`` is the finite set of expert-approved
    constant increase rates (``m`` in the decision package's crown
    formulas). The engine estimates a continuous ``k`` and snaps to the
    nearest member of this set — it never invents an arbitrary schedule
    (decision package §14, "Approximate increases per flat round": "may
    select among expert-tested schedules but cannot invent arbitrary
    schedules outside template bounds").
    """

    model_config = ConfigDict(frozen=True)

    allowed_increases_per_round: list[int] = Field(min_length=1)


class BeanieTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: str
    supported_stitch_families: list[StitchFamily]
    supported_constructions: list[Construction]
    supported_brim_types: list[BrimType]
    ranges: TemplateRanges
    crown_profile: CrownProfile
    min_body_rounds: int = Field(ge=1)
    circumference_warning_tolerance_pct: Decimal
    circumference_fatal_tolerance_pct: Decimal
