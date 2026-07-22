"""Dimensional validation: supported ranges and circumference deviation.

Rule IDs: ``V-RANGE-001``, ``V-DIM-001``, ``V-ROUNDING-001``.
"""

from __future__ import annotations

from decimal import Decimal

from crochet_reconstruction.domain.pattern import Pattern
from crochet_reconstruction.templates.base import BeanieTemplate
from crochet_reconstruction.validation.models import ReportBuilder

_ZERO = Decimal(0)


def check_supported_ranges(
    pattern: Pattern, template: BeanieTemplate, builder: ReportBuilder
) -> None:
    measurements = pattern.input.measurements
    gauge = pattern.input.gauge
    ranges = template.ranges

    checks = (
        (
            "input.measurements.head_circumference_cm",
            measurements.head_circumference_cm,
            ranges.head_circumference_cm,
        ),
        ("input.gauge.stitches_per_10cm", gauge.stitches_per_10cm, ranges.stitches_per_10cm),
        ("input.gauge.rounds_per_10cm", gauge.rounds_per_10cm, ranges.rounds_per_10cm),
        ("input.negative_ease_pct", pattern.input.negative_ease_pct, ranges.negative_ease_pct),
    )
    for path, value, allowed in checks:
        if not allowed.contains(value):
            builder.fatal(
                "V-RANGE-001",
                path,
                f"value {value} is outside template {template.id}@{template.version} "
                f"supported range [{allowed.minimum}, {allowed.maximum}]",
                details={
                    "value": str(value),
                    "minimum": str(allowed.minimum),
                    "maximum": str(allowed.maximum),
                },
            )


def check_circumference_deviation(
    pattern: Pattern, template: BeanieTemplate, builder: ReportBuilder
) -> None:
    calculated = pattern.calculated
    target = calculated.target_circumference_cm
    if target <= _ZERO:
        return

    deviation_pct = (calculated.circumference_deviation_cm / target) * Decimal(100)
    path = "calculated.circumference_deviation_cm"
    details = {
        "deviation_cm": str(calculated.circumference_deviation_cm),
        "deviation_pct": str(deviation_pct),
        "target_circumference_cm": str(target),
    }

    if deviation_pct > template.circumference_fatal_tolerance_pct:
        builder.fatal(
            "V-DIM-001",
            path,
            f"repeat-compatible rounding changes target circumference by "
            f"{deviation_pct:.2f}%, exceeding the fatal tolerance of "
            f"{template.circumference_fatal_tolerance_pct}%",
            details=details,
        )
    elif deviation_pct > template.circumference_warning_tolerance_pct:
        builder.warning(
            "V-ROUNDING-001",
            path,
            f"repeat-compatible rounding changes target circumference by {deviation_pct:.2f}%",
            details=details,
        )
