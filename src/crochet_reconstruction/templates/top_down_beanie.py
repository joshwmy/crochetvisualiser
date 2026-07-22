"""``top_down_basic`` — the sole Phase 1 template.

Continuous (spiral) rounds only, sc or hdc body, optional unshaped BLO
in-round brim. Joined rounds, vertical ribbing, folded brims, and dc are
deliberately absent from ``supported_*`` lists rather than silently
downgraded — selecting them raises
:class:`~crochet_reconstruction.domain.errors.UnsupportedConstructionError`
or a template-support validation failure.
"""

from __future__ import annotations

from decimal import Decimal

from crochet_reconstruction.domain.enums import BrimType, Construction, StitchFamily
from crochet_reconstruction.templates.base import (
    BeanieTemplate,
    CrownProfile,
    DecimalRange,
    TemplateRanges,
)

TOP_DOWN_BASIC = BeanieTemplate(
    id="top_down_basic",
    version="1.0.0",
    supported_stitch_families=[StitchFamily.SC, StitchFamily.HDC],
    supported_constructions=[Construction.CONTINUOUS],
    supported_brim_types=[BrimType.NONE, BrimType.BLO_IN_ROUND],
    ranges=TemplateRanges(
        head_circumference_cm=DecimalRange(minimum=Decimal(42), maximum=Decimal(64)),
        stitches_per_10cm=DecimalRange(minimum=Decimal(10), maximum=Decimal(24)),
        rounds_per_10cm=DecimalRange(minimum=Decimal(7), maximum=Decimal(20)),
        negative_ease_pct=DecimalRange(minimum=Decimal(0), maximum=Decimal(12)),
    ),
    crown_profile=CrownProfile(allowed_increases_per_round=[6, 8]),
    min_body_rounds=1,
    circumference_warning_tolerance_pct=Decimal("3"),
    circumference_fatal_tolerance_pct=Decimal("8"),
)

TEMPLATES: dict[str, BeanieTemplate] = {TOP_DOWN_BASIC.id: TOP_DOWN_BASIC}


def get_template(template_id: str, version: str) -> BeanieTemplate:
    template = TEMPLATES.get(template_id)
    if template is None or template.version != version:
        raise KeyError(f"unknown template {template_id}@{version}")
    return template
