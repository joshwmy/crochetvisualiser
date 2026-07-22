"""Stage 2-3: lex + grammar-parse one section's instruction body into a syntax tree.

Uses Lark's Earley algorithm — this grammar is tiny and every input is a
handful of tokens, so parse speed is never the concern; Earley tolerates
the grammar's optional tokens (``NUMBER?``, ``in_magic_ring?``) without the
shift/reduce conflict analysis LALR would require, which matters more for a
first hand-written grammar than raw throughput.
"""

from __future__ import annotations

from pathlib import Path

from lark import Lark, Token, Transformer, UnexpectedInput
from lark import Tree as LarkTree

from crochet_reconstruction.parsing.written.syntax import (
    AroundMode,
    ParsedAround,
    ParsedGroup,
    ParsedNode,
    ParsedRepeat,
    ParsedStitch,
    StitchWord,
)

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"


class InstructionSyntaxError(Exception):
    """Raised when a section's instruction body doesn't match the grammar.

    ``column`` is 1-indexed and relative to the *normalized* body text (see
    ``normalize.py``), not the original raw line — canonicalization can
    change token lengths, so this is an approximate pointer, not a byte-exact
    one. Documented in docs/written-pattern-grammar.md.
    """

    def __init__(self, message: str, column: int | None) -> None:
        super().__init__(message)
        self.column = column


class _ToSyntaxTree(Transformer[Token, list[ParsedNode]]):
    def start(self, children: list[object]) -> list[ParsedNode]:
        (instruction_list,) = children
        result: list[ParsedNode] = instruction_list  # type: ignore[assignment]
        return result

    def instruction_list(self, children: list[ParsedNode]) -> list[ParsedNode]:
        return children

    def stitch_instruction(self, children: list[object]) -> ParsedStitch:
        count = 1
        stitch: StitchWord | None = None
        into_magic_ring = False
        for child in children:
            if isinstance(child, Token) and child.type == "NUMBER":
                count = int(child)
            elif isinstance(child, Token) and child.type == "STITCH_WORD":
                stitch = str(child)  # type: ignore[assignment]
            elif isinstance(child, LarkTree) and child.data == "in_magic_ring":
                into_magic_ring = True
        assert stitch is not None
        return ParsedStitch(stitch=stitch, count=count, into_magic_ring=into_magic_ring)

    def group(self, children: list[object]) -> ParsedGroup:
        (items,) = children
        assert isinstance(items, list)
        return ParsedGroup(items=items)

    def repeat_instruction(self, children: list[object]) -> ParsedRepeat:
        group, times_token = children[0], children[1]
        assert isinstance(group, ParsedGroup)
        assert isinstance(times_token, Token)
        return ParsedRepeat(group=group, times=int(times_token))

    def stitch_around_instruction(self, children: list[object]) -> ParsedAround:
        stitch, mode_marker = children[0], children[1]
        assert isinstance(stitch, ParsedStitch)
        mode: AroundMode = "each_stitch_around" if mode_marker == "each_stitch_around" else "around"
        return ParsedAround(stitch=stitch, mode=mode)

    def each_stitch_around(self, _children: list[object]) -> str:
        return "each_stitch_around"

    def plain_around(self, _children: list[object]) -> str:
        return "around"


_parser: Lark | None = None
_transformer = _ToSyntaxTree()


def _get_parser() -> Lark:
    global _parser
    if _parser is None:
        _parser = Lark(
            _GRAMMAR_PATH.read_text(encoding="utf-8"),
            parser="earley",
            ambiguity="resolve",
        )
    return _parser


def parse_instruction_body(body: str) -> list[ParsedNode]:
    """Parse one normalized instruction-list body into a list of :class:`ParsedNode`.

    Raises :class:`InstructionSyntaxError` on any grammar mismatch —
    callers convert that into a structured ``Diagnostic`` with the
    original source line number, never a raw traceback.
    """
    try:
        tree = _get_parser().parse(body)
    except UnexpectedInput as exc:
        column = getattr(exc, "column", None)
        raise InstructionSyntaxError(str(exc), column=column) from exc
    result = _transformer.transform(tree)
    return result
