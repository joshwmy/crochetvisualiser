"""Parser-stage syntax model: preserves parsed source structure only.

This is deliberately a thin, source-shaped tree — it exists only to carry
what a line of written pattern text said before ``semantic.py`` converts it
into the existing ``domain.operations``/``domain.rounds`` model. It is not,
and must not become, a second crochet domain model: it has no notion of
insertion targets, consumed/produced counts, or graph structure — those
concepts live only in ``domain``/``graph``, exactly once each.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StitchWord = Literal["sc", "hdc", "dc", "chain", "slipstitch", "inc", "dec"]
AroundMode = Literal["around", "each_stitch_around"]


@dataclass(frozen=True)
class ParsedStitch:
    """One stitch-instruction token, e.g. ``"6 sc"`` or ``"sc in magicring"``."""

    stitch: StitchWord
    count: int = 1
    into_magic_ring: bool = False


@dataclass(frozen=True)
class ParsedGroup:
    """A parenthesised instruction list, e.g. ``"(sc, inc)"``."""

    items: list[ParsedNode]


@dataclass(frozen=True)
class ParsedRepeat:
    """``group "repeat" N "times"``, e.g. ``"(sc, inc) repeat 6 times"``."""

    group: ParsedGroup
    times: int


@dataclass(frozen=True)
class ParsedAround:
    """``stitch "around"`` or ``stitch "in each stitch around"``.

    The repeat count is not known at parse time — it depends on the
    previous round's stitch total, resolved in ``semantic.py``.
    """

    stitch: ParsedStitch
    mode: AroundMode


ParsedNode = ParsedStitch | ParsedGroup | ParsedRepeat | ParsedAround


@dataclass(frozen=True)
class ParsedSection:
    """One ``"Round N:"``/``"Rows N-M:"`` line, before range expansion."""

    kind: Literal["round", "row"]
    number_start: int
    number_end: int
    instructions: list[ParsedNode]
    declared_count: int | None
    line: int
    raw_text: str


@dataclass(frozen=True)
class ParsedPattern:
    """The full parsed source: an ordered list of sections."""

    sections: list[ParsedSection]
