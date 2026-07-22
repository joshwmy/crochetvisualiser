"""Stage 4-5: semantic expansion + conversion into existing ``domain.operations``.

This module produces only ``crochet_reconstruction.domain.operations.Operation``
instances (``StitchOp``/``IncreaseOp``/``DecreaseOp``/``MagicRingOp``/``RepeatOp``)
— the same types ``engine/crown.py``/``engine/body.py`` already emit. No new
operation type is introduced.

Documented deterministic assumptions (see docs/written-pattern-grammar.md
for the full list):

* **"X around" / "X in each stitch around"** always means "repeat X enough
  times to consume the entire previous round" — the repeat count is
  ``previous_round_total // consumed_per_repeat(X)``, never guessed from the
  declared count (the declared count, when present, is still cross-checked
  afterward in ``semantic.py``).
* **Increase/decrease stitch type** defaults to the pattern's "dominant"
  plain-stitch family (the first ``sc``/``hdc``/``dc`` token found anywhere
  in the pattern, or ``sc`` if none exists) — a written pattern's ``inc``/
  ``dec`` tokens never name their own stitch type, unlike this domain
  model's ``IncreaseOp.stitch``/``DecreaseOp.stitch`` fields, which do.
* **``N inc`` / ``N dec`` (count > 1)** means "N separate increases/decreases
  in sequence", not one increase with a larger input/output ratio —
  represented as ``RepeatOp(times=N, body=[<single increase/decrease>])``.
* **Magic ring** always starts round 1 with no prior parent stitches,
  exactly like ``engine/crown.py``'s ``MagicRingOp`` usage.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from crochet_reconstruction.domain.enums import LoopPlacement, StitchFamily
from crochet_reconstruction.domain.operations import (
    DecreaseOp,
    IncreaseOp,
    MagicRingOp,
    Operation,
    RepeatOp,
    StitchOp,
    consumed_count,
    produced_count,
)
from crochet_reconstruction.parsing.written.diagnostics import Diagnostic, DiagnosticCode
from crochet_reconstruction.parsing.written.syntax import (
    ParsedAround,
    ParsedGroup,
    ParsedNode,
    ParsedRepeat,
    ParsedSection,
    ParsedStitch,
)

_PLAIN_STITCH_WORDS = {"sc": StitchFamily.SC, "hdc": StitchFamily.HDC, "dc": StitchFamily.DC}
UNSUPPORTED_STITCH_WORDS = {"chain", "slipstitch"}


class SemanticError(Exception):
    """Raised when a syntactically valid section cannot be converted deterministically."""

    def __init__(self, code: DiagnosticCode, message: str, **extra: int | None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra

    def to_diagnostic(self, *, line: int, source_text: str, section: int) -> Diagnostic:
        return Diagnostic(
            severity="error",
            code=self.code,
            message=self.message,
            line=line,
            section=section,
            source_text=source_text,
            **self.extra,
        )


def contains_unsupported_stitch(nodes: list[ParsedNode]) -> bool:
    for node in nodes:
        if isinstance(node, ParsedStitch) and node.stitch in UNSUPPORTED_STITCH_WORDS:
            return True
        if isinstance(node, ParsedGroup) and contains_unsupported_stitch(node.items):
            return True
        if isinstance(node, ParsedRepeat) and contains_unsupported_stitch(node.group.items):
            return True
        if isinstance(node, ParsedAround) and contains_unsupported_stitch([node.stitch]):
            return True
    return False


def infer_dominant_family(all_nodes: list[ParsedNode]) -> StitchFamily:
    """The first plain sc/hdc/dc stitch word anywhere in the pattern, else ``sc``."""
    for node in all_nodes:
        if isinstance(node, ParsedStitch) and node.stitch in _PLAIN_STITCH_WORDS:
            return _PLAIN_STITCH_WORDS[node.stitch]
        if isinstance(node, ParsedGroup):
            found = infer_dominant_family(node.items)
            if found is not None:
                return found
        if isinstance(node, ParsedRepeat):
            found = infer_dominant_family(node.group.items)
            if found is not None:
                return found
        if isinstance(node, ParsedAround):
            found = infer_dominant_family([node.stitch])
            if found is not None:
                return found
    return StitchFamily.SC


def _single_unit_op(stitch: ParsedStitch, dominant_family: StitchFamily) -> Operation:
    """Convert one ``ParsedStitch`` at count=1 into its base Operation (no repeat wrapping)."""
    if stitch.stitch == "inc":
        return IncreaseOp(stitch=dominant_family, input=1, output=2, loop=LoopPlacement.BOTH)
    if stitch.stitch == "dec":
        return DecreaseOp(stitch=dominant_family, input=2, output=1, loop=LoopPlacement.BOTH)
    family = _PLAIN_STITCH_WORDS[stitch.stitch]
    if stitch.into_magic_ring:
        return MagicRingOp(stitch=family, output=1)
    return StitchOp(stitch=family, count=1, loop=LoopPlacement.BOTH)


def _convert_stitch(stitch: ParsedStitch, dominant_family: StitchFamily) -> Operation:
    if stitch.into_magic_ring:
        if stitch.stitch not in _PLAIN_STITCH_WORDS:
            raise SemanticError(
                DiagnosticCode.INVALID_SYNTAX,
                "'inc'/'dec' cannot be worked directly into a magic ring.",
            )
        return MagicRingOp(stitch=_PLAIN_STITCH_WORDS[stitch.stitch], output=stitch.count)
    if stitch.stitch in ("inc", "dec"):
        if stitch.count == 1:
            return _single_unit_op(stitch, dominant_family)
        return RepeatOp(times=stitch.count, body=[_single_unit_op(stitch, dominant_family)])
    family = _PLAIN_STITCH_WORDS[stitch.stitch]
    return StitchOp(stitch=family, count=stitch.count, loop=LoopPlacement.BOTH)


def _convert_node(
    node: ParsedNode, dominant_family: StitchFamily, previous_total: int | None
) -> list[Operation]:
    if isinstance(node, ParsedStitch):
        return [_convert_stitch(node, dominant_family)]

    if isinstance(node, ParsedGroup):
        ops: list[Operation] = []
        for item in node.items:
            ops.extend(_convert_node(item, dominant_family, previous_total))
        return ops

    if isinstance(node, ParsedRepeat):
        body: list[Operation] = []
        for item in node.group.items:
            body.extend(_convert_node(item, dominant_family, previous_total))
        return [RepeatOp(times=node.times, body=body)]

    if isinstance(node, ParsedAround):
        if previous_total is None:
            raise SemanticError(
                DiagnosticCode.MISSING_FOUNDATION,
                "'around' cannot be used on the first section — there is no previous "
                "round to repeat around. Start with a magic ring foundation.",
            )
        base_op = _single_unit_op(node.stitch, dominant_family)
        consumed_per_repeat = consumed_count(base_op)
        if consumed_per_repeat == 0:
            raise SemanticError(
                DiagnosticCode.INVALID_REPEAT,
                f"'{node.stitch.stitch} around' does not consume any previous-round "
                "stitches, so its repeat count cannot be determined from the previous round.",
            )
        if previous_total % consumed_per_repeat != 0:
            raise SemanticError(
                DiagnosticCode.INVALID_REPEAT,
                f"Previous round has {previous_total} stitches, which is not evenly "
                f"divisible by {consumed_per_repeat} (stitches consumed per "
                f"'{node.stitch.stitch}'), so 'around' cannot be resolved exactly.",
                expected=previous_total,
            )
        repeat_times = previous_total // consumed_per_repeat
        return [RepeatOp(times=repeat_times, body=[base_op])]

    raise AssertionError(f"unhandled ParsedNode type: {type(node).__name__}")


@dataclass(frozen=True)
class ConvertedSection:
    operations: list[Operation]
    produced_total: int
    consumed_total: int


def convert_section(
    section: ParsedSection, previous_total: int | None, dominant_family: StitchFamily
) -> ConvertedSection:
    """Convert one section's parsed instructions into ``Operation``s.

    Raises :class:`SemanticError` for foundation/repeat/increase/decrease
    problems detected during conversion itself (before the existing
    ``domain``/``graph`` validation ever runs) — callers still let
    ``graph.validation`` be the final authority, this is an earlier,
    friendlier check with source-line context attached.
    """
    operations: list[Operation] = []
    try:
        for node in section.instructions:
            operations.extend(_convert_node(node, dominant_family, previous_total))
    except ValidationError as exc:
        raise SemanticError(
            DiagnosticCode.INVALID_INCREASE, f"Could not build a valid stitch operation: {exc}"
        ) from exc

    consumed_total = sum(consumed_count(op) for op in operations)
    produced_total = sum(produced_count(op) for op in operations)

    if previous_total is None:
        if consumed_total != 0:
            raise SemanticError(
                DiagnosticCode.MISSING_FOUNDATION,
                "The first section must start from a magic ring (or another "
                "zero-parent foundation) — it cannot consume previous-round stitches "
                "that don't exist yet.",
            )
    elif consumed_total != previous_total:
        raise SemanticError(
            DiagnosticCode.INSUFFICIENT_PARENT_STITCHES,
            f"This section's instructions consume {consumed_total} previous-round "
            f"stitch(es), but the previous round has {previous_total}.",
            expected=previous_total,
            actual=consumed_total,
        )

    return ConvertedSection(
        operations=operations, produced_total=produced_total, consumed_total=consumed_total
    )
