"""Structural validation: round numbering, component order, closures, template support.

Rule IDs: ``V-OP-001``, ``V-ROUND-001``, ``V-JOIN-001``, ``V-TRANS-001``,
``V-CROWN-001``, ``V-BRIM-001``.
"""

from __future__ import annotations

from crochet_reconstruction.domain.enums import ClosureKind, ComponentKind
from crochet_reconstruction.domain.operations import (
    DecreaseOp,
    IncreaseOp,
    MagicRingOp,
    Operation,
    RepeatOp,
    StitchOp,
)
from crochet_reconstruction.domain.pattern import Pattern
from crochet_reconstruction.templates.base import BeanieTemplate
from crochet_reconstruction.validation.models import ReportBuilder

_EXPECTED_COMPONENT_ORDER = (ComponentKind.CROWN, ComponentKind.BODY, ComponentKind.BRIM)


def _stitch_families_used(op: Operation) -> set[str]:
    match op:
        case (
            StitchOp(stitch=stitch)
            | IncreaseOp(stitch=stitch)
            | MagicRingOp(stitch=stitch)
            | DecreaseOp(stitch=stitch)
        ):
            return {stitch.value}
        case RepeatOp(body=body):
            found: set[str] = set()
            for child in body:
                found |= _stitch_families_used(child)
            return found
        case _:
            return set()


def check_template_support(
    pattern: Pattern, template: BeanieTemplate, builder: ReportBuilder
) -> None:
    if pattern.input.construction not in template.supported_constructions:
        builder.fatal(
            "V-TRANS-001",
            "input.construction",
            f"construction {pattern.input.construction.value!r} is not supported by "
            f"template {template.id}@{template.version}",
        )
    if pattern.input.brim_type not in template.supported_brim_types:
        builder.fatal(
            "V-BRIM-001",
            "input.brim_type",
            f"brim type {pattern.input.brim_type.value!r} is not supported by "
            f"template {template.id}@{template.version}",
        )

    supported = {f.value for f in template.supported_stitch_families}
    for component in pattern.components:
        for round_ in component.rounds:
            for op in round_.operations:
                used = _stitch_families_used(op)
                unsupported = used - supported
                if unsupported:
                    builder.fatal(
                        "V-OP-001",
                        f"components[{component.kind.value}].rounds[{round_.number}]",
                        f"stitch family/families {sorted(unsupported)} not supported by "
                        f"template {template.id}@{template.version}",
                        details={"unsupported": sorted(unsupported)},
                    )


def check_round_numbering(pattern: Pattern, builder: ReportBuilder) -> None:
    all_numbers = [r.number for c in pattern.components for r in c.rounds]
    expected = list(range(1, len(all_numbers) + 1))
    if all_numbers != expected:
        builder.fatal(
            "V-ROUND-001",
            "components[*].rounds[*].number",
            f"round numbers must be sequential starting at 1 with no gaps or "
            f"duplicates; got {all_numbers}",
            details={"expected": expected, "actual": all_numbers},
        )


def check_closures(pattern: Pattern, builder: ReportBuilder) -> None:
    for component in pattern.components:
        for round_ in component.rounds:
            path = f"components[{component.kind.value}].rounds[{round_.number}]"
            if round_.closure is not ClosureKind.NONE:
                builder.fatal(
                    "V-JOIN-001",
                    path,
                    f"round has closure {round_.closure.value!r} but Phase 1 only "
                    f"supports continuous (spiral) rounds with no closure",
                    details={"closure": round_.closure.value},
                )


def check_component_transitions(pattern: Pattern, builder: ReportBuilder) -> None:
    kinds = [c.kind for c in pattern.components]
    expected = [k for k in _EXPECTED_COMPONENT_ORDER if k in set(kinds)]
    if kinds != expected:
        builder.fatal(
            "V-TRANS-001",
            "components",
            f"components must appear in order crown, body, [brim]; got {[k.value for k in kinds]}",
            details={"expected": [k.value for k in expected], "actual": [k.value for k in kinds]},
        )
        return

    by_kind = {c.kind: c for c in pattern.components}
    crown = by_kind.get(ComponentKind.CROWN)
    body = by_kind.get(ComponentKind.BODY)
    brim = by_kind.get(ComponentKind.BRIM)

    if crown is not None and body is not None:
        crown_final = crown.rounds[-1].stated_total
        body_first = body.rounds[0].stated_total
        if crown_final != body_first:
            builder.fatal(
                "V-CROWN-001",
                "components[crown->body]",
                f"crown's final round has {crown_final} stitches but body's first "
                f"round has {body_first} stitches",
                details={"crown_final": crown_final, "body_first": body_first},
            )

    if body is not None and brim is not None:
        body_final = body.rounds[-1].stated_total
        brim_first = brim.rounds[0].stated_total
        if body_final != brim_first:
            builder.fatal(
                "V-BRIM-001",
                "components[body->brim]",
                f"body's final round has {body_final} stitches but brim's first "
                f"round has {brim_first} stitches",
                details={"body_final": body_final, "brim_first": brim_first},
            )
