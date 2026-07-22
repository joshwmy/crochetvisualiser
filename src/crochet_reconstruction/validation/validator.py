"""Validation entry point: runs the full rule catalogue and returns a report.

A pattern must never be shown as ``valid`` or rendered while any fatal
result remains (decision package §15, closing invariant). Callers must
check ``report.has_fatal`` (or ``ReportBuilder.has_fatal`` before building)
before invoking the renderer.
"""

from __future__ import annotations

from crochet_reconstruction.domain.pattern import Pattern, ValidationReport
from crochet_reconstruction.templates.base import BeanieTemplate
from crochet_reconstruction.validation.arithmetic import check_round_arithmetic
from crochet_reconstruction.validation.dimensions import (
    check_circumference_deviation,
    check_supported_ranges,
)
from crochet_reconstruction.validation.models import ReportBuilder
from crochet_reconstruction.validation.structure import (
    check_closures,
    check_component_transitions,
    check_round_numbering,
    check_template_support,
)

ENGINE_VERSION = "0.1.0"


def validate(pattern: Pattern, template: BeanieTemplate) -> ValidationReport:
    builder = ReportBuilder()

    check_template_support(pattern, template, builder)
    check_round_numbering(pattern, builder)
    check_closures(pattern, builder)

    previous_total: int | None = None
    for component in pattern.components:
        for round_ in component.rounds:
            path = f"components[{component.kind.value}].rounds[{round_.number}]"
            previous_total = check_round_arithmetic(round_, previous_total, path, builder)

    check_component_transitions(pattern, builder)
    check_supported_ranges(pattern, template, builder)
    check_circumference_deviation(pattern, template, builder)

    return builder.build(ENGINE_VERSION)
