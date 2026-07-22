"""Human-readable US-terminology instructions from a validated Pattern.

This module performs no arithmetic and parses no text back out of the
structured pattern — every number shown here is read directly from
``pattern.calculated`` or a round's ``operations``/``stated_total``. It may
improve wording, but per the Phase 1 requirement it must never alter
stitch totals, operations, round count, gauge calculations, dimensions, or
template parameters.

Rendering a pattern with any fatal validation result is refused.
"""

from __future__ import annotations

from crochet_reconstruction.domain.enums import ComponentKind, LoopPlacement, Severity, StitchFamily
from crochet_reconstruction.domain.errors import CrochetReconstructionError
from crochet_reconstruction.domain.operations import (
    DecreaseOp,
    IncreaseOp,
    MagicRingOp,
    Operation,
    RepeatOp,
    StitchOp,
)
from crochet_reconstruction.domain.pattern import Pattern
from crochet_reconstruction.domain.rounds import Round

_STITCH_LABELS: dict[StitchFamily, tuple[str, str]] = {
    StitchFamily.SC: ("sc", "single crochet"),
    StitchFamily.HDC: ("hdc", "half double crochet"),
}

_LOOP_SUFFIX: dict[LoopPlacement, str] = {
    LoopPlacement.BOTH: "",
    LoopPlacement.BACK_LOOP_ONLY: " (back loop only)",
    LoopPlacement.FRONT_LOOP_ONLY: " (front loop only)",
}


class PatternNotRenderableError(CrochetReconstructionError):
    """Raised when attempting to render a pattern with fatal validation results."""


def _abbr(stitch: StitchFamily) -> str:
    return _STITCH_LABELS[stitch][0]


def _render_operation(op: Operation) -> str:
    match op:
        case MagicRingOp(stitch=stitch, output=output):
            return f"work {output} {_abbr(stitch)} into an adjustable (magic) ring"
        case StitchOp(stitch=stitch, count=count, loop=loop):
            suffix = _LOOP_SUFFIX[loop]
            noun = "st" if count == 1 else "sts"
            return f"{_abbr(stitch)} in next {count} {noun}{suffix}"
        case IncreaseOp(stitch=stitch, output=output, loop=loop):
            suffix = _LOOP_SUFFIX[loop]
            return f"{output} {_abbr(stitch)} in next st{suffix}"
        case DecreaseOp(stitch=stitch, input=input_count, output=output, loop=loop):
            suffix = _LOOP_SUFFIX[loop]
            return (
                f"{_abbr(stitch)}{input_count}tog over next {input_count} sts "
                f"(makes {output}){suffix}"
            )
        case RepeatOp(times=times, body=body):
            inner = ", ".join(_render_operation(child) for child in body)
            return f"*{inner}* around ({times} times)"
    raise TypeError(f"unhandled operation type: {type(op).__name__}")


def _render_round(round_: Round) -> str:
    phrase = "; ".join(_render_operation(op) for op in round_.operations)
    phrase = phrase[0].upper() + phrase[1:]
    return f"Round {round_.number}: {phrase}. ({round_.stated_total})"


def _render_component(kind: ComponentKind, rounds: list[Round]) -> list[str]:
    lines = [f"## {kind.value.capitalize()}"]
    lines.extend(_render_round(r) for r in rounds)
    return lines


def render_text(pattern: Pattern) -> str:
    """Render a validated pattern as US-terminology plain-text instructions.

    Raises :class:`PatternNotRenderableError` if the pattern has not been
    validated, or has any fatal validation result.
    """
    if pattern.validation is None:
        raise PatternNotRenderableError("pattern has not been validated")
    if pattern.validation.has_fatal:
        raise PatternNotRenderableError(
            "pattern has fatal validation results and cannot be rendered as final"
        )

    input_ = pattern.input
    calculated = pattern.calculated
    stitch_family = input_.gauge.stitch_family
    stitch_full_name = _STITCH_LABELS[stitch_family][1]

    lines: list[str] = []
    lines.append(f"# {input_.project.title}")
    lines.append("")
    lines.append(
        "This is an original, deterministically generated reconstruction. It is "
        "not a recovered designer pattern. Make and measure a gauge swatch before "
        "beginning."
    )
    lines.append("")

    lines.append("## Materials and assumptions")
    lines.append(f"- Body stitch: {stitch_full_name} ({_abbr(stitch_family)}), US terminology")
    lines.append(f"- Construction: {input_.construction.value.replace('_', ' ')}")
    lines.append(f"- Template: {input_.template.id}@{input_.template.version}")
    if input_.yarn is not None and input_.yarn.weight_category:
        lines.append(f"- Yarn weight (user-entered): {input_.yarn.weight_category}")
    if input_.yarn is not None and input_.yarn.fibre:
        lines.append(f"- Yarn fibre (user-entered): {input_.yarn.fibre}")
    if input_.hook is not None and input_.hook.hook_mm is not None:
        lines.append(f"- Hook (user-entered): {input_.hook.hook_mm} mm")
    lines.append("")

    lines.append("## Gauge")
    lines.append(
        f"- {input_.gauge.stitches_per_10cm} {_abbr(stitch_family)} and "
        f"{input_.gauge.rounds_per_10cm} rounds per 10 cm"
    )
    lines.append("")

    lines.append("## Finished measurements")
    lines.append(f"- Head circumference (input): {input_.measurements.head_circumference_cm} cm")
    lines.append(f"- Negative ease: {input_.negative_ease_pct}%")
    lines.append(f"- Target finished circumference: {calculated.target_circumference_cm} cm")
    lines.append(
        f"- Body stitch count: {calculated.body_stitch_count} "
        f"(raw gauge calculation: {calculated.body_stitch_count_raw:.2f}, "
        f"dimensional deviation: {calculated.circumference_deviation_cm:.2f} cm)"
    )
    lines.append(f"- Target height: {input_.measurements.target_height_cm} cm")
    if input_.measurements.brim_height_cm is not None:
        lines.append(f"- Brim height: {input_.measurements.brim_height_cm} cm")
    lines.append("")

    lines.append("## Abbreviations")
    lines.append(f"- {_abbr(stitch_family)} = {stitch_full_name}")
    lines.append("- st(s) = stitch(es)")
    lines.append("- MR = magic ring")
    lines.append("- inc = increase")
    if any(
        isinstance(op, DecreaseOp)
        for component in pattern.components
        for round_ in component.rounds
        for op in round_.operations
    ):
        lines.append("- dec = decrease")
    lines.append("")

    lines.append("## Construction notes")
    lines.append(
        "- Worked in continuous spiral rounds (no slip-stitch join). Use a "
        "stitch marker to track the start of each round."
    )
    lines.append("")

    for component in pattern.components:
        lines.extend(_render_component(component.kind, component.rounds))
        lines.append("")

    lines.append("## Validation status")
    lines.append(f"- Status: {pattern.validation.status.value}")
    lines.append(f"- Engine version: {pattern.validation.engine_version}")
    non_fatal = [r for r in pattern.validation.results if r.severity is not Severity.FATAL]
    if non_fatal:
        lines.append("- Warnings / notes:")
        for result in non_fatal:
            lines.append(f"  - [{result.severity.value}] {result.rule_id}: {result.message}")
    lines.append("")

    if pattern.assumptions:
        lines.append("## Assumptions")
        for assumption in pattern.assumptions:
            note = f" ({assumption.note})" if assumption.note else ""
            lines.append(
                f"- {assumption.field} = {assumption.value} [{assumption.source.value}]{note}"
            )
        lines.append("")

    lines.append(f"Pattern fingerprint: {pattern.fingerprint}")

    return "\n".join(lines)
