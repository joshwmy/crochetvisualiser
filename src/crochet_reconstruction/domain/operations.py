"""Stitch operations: the atoms the compiler expands and the validator checks.

Each operation has explicit consumed/produced semantics (see
:func:`consumed_count` / :func:`produced_count`). The renderer is forbidden
from parsing operation text to recover these counts — it reads the
structured fields directly. This is the same invariant the decision
package's IR insists on (§12, "Parsing rules" #6-#7).

``DecreaseOp`` is modelled per the Phase 1 requirement to represent
decreases "even if decreases are not yet generated" — no Phase 1 template
currently emits one.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crochet_reconstruction.domain.enums import LoopPlacement, StitchFamily

MAX_REPEAT_TIMES = 200
"""Safe upper bound on a single repeat's multiplier, to bound expansion cost."""

MAX_REPEAT_DEPTH = 4
"""Safe upper bound on nested repeat depth. No Phase 1 template nests repeats."""


class MagicRingOp(BaseModel):
    """Adjustable ring starting method: work ``output`` stitches into the ring.

    ``stitch`` records which stitch type is worked into the ring so the
    renderer can name it without inferring it from surrounding context.
    """

    model_config = ConfigDict(frozen=True)

    op: Literal["magic_ring"] = "magic_ring"
    stitch: StitchFamily
    output: int = Field(ge=1, le=20)


class StitchOp(BaseModel):
    """Work ``count`` plain stitches, one loop consumed per stitch produced."""

    model_config = ConfigDict(frozen=True)

    op: Literal["stitch"] = "stitch"
    stitch: StitchFamily
    count: int = Field(default=1, ge=1)
    loop: LoopPlacement = LoopPlacement.BOTH


class IncreaseOp(BaseModel):
    """Work ``output`` stitches into ``input`` previous-round stitch(es)."""

    model_config = ConfigDict(frozen=True)

    op: Literal["increase"] = "increase"
    stitch: StitchFamily
    input: int = Field(default=1, ge=1)
    output: int = Field(ge=2)
    loop: LoopPlacement = LoopPlacement.BOTH

    @model_validator(mode="after")
    def _output_exceeds_input(self) -> IncreaseOp:
        if self.output <= self.input:
            raise ValueError("increase output must exceed input")
        return self


class DecreaseOp(BaseModel):
    """Work ``output`` stitches by combining ``input`` previous-round stitches."""

    model_config = ConfigDict(frozen=True)

    op: Literal["decrease"] = "decrease"
    stitch: StitchFamily
    input: int = Field(ge=2)
    output: int = Field(default=1, ge=1)
    loop: LoopPlacement = LoopPlacement.BOTH

    @model_validator(mode="after")
    def _output_below_input(self) -> DecreaseOp:
        if self.output >= self.input:
            raise ValueError("decrease output must be less than input")
        return self


class RepeatOp(BaseModel):
    """Repeat a body of operations ``times`` times."""

    model_config = ConfigDict(frozen=True)

    op: Literal["repeat"] = "repeat"
    times: int = Field(ge=1, le=MAX_REPEAT_TIMES)
    body: list[Operation] = Field(min_length=1)


Operation = Annotated[
    MagicRingOp | StitchOp | IncreaseOp | DecreaseOp | RepeatOp,
    Field(discriminator="op"),
]

RepeatOp.model_rebuild()


def consumed_count(op: Operation, *, depth: int = 0) -> int:
    """Previous-round stitches this operation consumes."""
    if depth > MAX_REPEAT_DEPTH:
        raise ValueError(f"repeat nesting exceeds MAX_REPEAT_DEPTH={MAX_REPEAT_DEPTH}")
    match op:
        case MagicRingOp():
            return 0
        case StitchOp(count=count):
            return count
        case IncreaseOp(input=input_count):
            return input_count
        case DecreaseOp(input=input_count):
            return input_count
        case RepeatOp(times=times, body=body):
            return times * sum(consumed_count(child, depth=depth + 1) for child in body)
    raise TypeError(f"unhandled operation type: {type(op).__name__}")


def produced_count(op: Operation, *, depth: int = 0) -> int:
    """Stitches this operation produces into the current round."""
    if depth > MAX_REPEAT_DEPTH:
        raise ValueError(f"repeat nesting exceeds MAX_REPEAT_DEPTH={MAX_REPEAT_DEPTH}")
    match op:
        case MagicRingOp(output=output):
            return output
        case StitchOp(count=count):
            return count
        case IncreaseOp(output=output):
            return output
        case DecreaseOp(output=output):
            return output
        case RepeatOp(times=times, body=body):
            return times * sum(produced_count(child, depth=depth + 1) for child in body)
    raise TypeError(f"unhandled operation type: {type(op).__name__}")
