"""Rounds and components: the structural layers between operations and a pattern."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from crochet_reconstruction.domain.enums import ClosureKind, ComponentKind, Construction
from crochet_reconstruction.domain.operations import Operation


class Round(BaseModel):
    """One round of stitching, with its expected (stated) resulting total.

    ``stated_total`` is produced by the compiler from the same formulas used
    to generate ``operations`` — it is not independently guessed. The
    validator re-derives the total from ``operations`` and compares it
    against ``stated_total`` (rule ``V-COUNT-001``); a mismatch is fatal.
    """

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1)
    operations: list[Operation] = Field(min_length=1)
    stated_total: int = Field(ge=0)
    closure: ClosureKind = ClosureKind.NONE


class Component(BaseModel):
    """A named section of the hat (crown, body, or brim) made of ordered rounds."""

    model_config = ConfigDict(frozen=True)

    kind: ComponentKind
    construction: Construction
    rounds: list[Round] = Field(min_length=1)
