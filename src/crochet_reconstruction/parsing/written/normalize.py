"""Stage 1: source normalisation.

Regex use here is deliberately narrow and documented, per the brief:
"Regex may be used for controlled preprocessing, token normalisation, or
local extraction, but the parser must not become an undocumented sequence
of regex replacements." Every substitution below maps a fixed phrase (or a
tightly-anchored numeric pattern) to exactly one canonical token that the
Lark grammar (``grammar.lark``) then matches literally — the grammar, not
this module, is responsible for structural parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

# Longest-phrase-first so "half double crochet" is replaced before a
# hypothetical shorter "double crochet" pattern could partially match it.
_PHRASE_CANONICALIZATIONS: list[tuple[str, str]] = [
    (r"\bhalf\s+double\s+crochet\b", "hdc"),
    (r"\bdouble\s+crochet\b", "dc"),
    (r"\bsingle\s+crochet\b", "sc"),
    (r"\bslip\s+stitch\b", "slipstitch"),
    (r"\bsl\s*st\b", "slipstitch"),
    (r"\bmagic\s+ring\b", "magicring"),
    (r"\bmagic\s+circle\b", "magicring"),
    (r"\bin\s+each\s+stitch\s+around\b", "ineachstitcharound"),
    (r"\bincrease\b", "inc"),
    (r"\bdecrease\b", "dec"),
    (r"\bchain\b", "chain"),
    (r"\bch\b", "chain"),
    (r"\brep\b", "repeat"),
    (r"\brounds\b", "round"),
    (r"\brnds\b", "round"),
    (r"\brnd\b", "round"),
    (r"\brows\b", "row"),
]

_COMMENT_RE = re.compile(r"(//|#).*$")
_DECLARED_COUNT_RE = re.compile(
    r"""
    \s*
    (?:
        \[(?P<bracket>\d+)\]
        |\((?P<paren>\d+)\)
        |(?P<sts>\d+)\s*sts\b
    )
    \s*\.?\s*$
    """,
    re.VERBOSE,
)
_SECTION_HEADER_RE = re.compile(
    r"^\s*(?P<kind>round|row)\s+(?P<start>\d+)(?:\s*-\s*(?P<end>\d+))?\s*:\s*(?P<body>.*)$"
)


@dataclass(frozen=True)
class NormalizedLine:
    line_number: int
    raw_text: str
    kind: Literal["round", "row"]
    number_start: int
    number_end: int
    body: str  # instruction text, lowercased + phrase-canonicalized, count stripped
    declared_count: int | None


def canonicalize_phrases(text: str) -> str:
    """Apply the fixed phrase -> single-token substitution table, in order."""
    result = text
    for pattern, replacement in _PHRASE_CANONICALIZATIONS:
        result = re.sub(pattern, replacement, result)
    return result


def strip_declared_count(body: str) -> tuple[str, int | None]:
    """Pull a trailing ``[N]``/``(N)``/``N sts`` off the end of the line, if present."""
    match = _DECLARED_COUNT_RE.search(body)
    if not match:
        return body.strip().rstrip(".").strip(), None
    count_str = match.group("bracket") or match.group("paren") or match.group("sts")
    remainder = body[: match.start()].strip()
    return remainder, int(count_str)


def split_into_lines(source: str) -> list[tuple[int, str]]:
    """Split into (1-indexed line number, text) pairs, dropping blank/comment-only lines."""
    result: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        without_comment = _COMMENT_RE.sub("", raw_line).strip()
        if not without_comment:
            continue
        result.append((line_number, raw_line.strip()))
    return result


def normalize_section_line(line_number: int, raw_text: str) -> NormalizedLine | None:
    """Lowercase, canonicalize, split header/body, strip declared count.

    Returns ``None`` if the line doesn't even look like a section header —
    the caller turns that into an ``INVALID_SYNTAX`` diagnostic rather than
    this module raising, so every line gets a chance to be reported.
    """
    lowered = canonicalize_phrases(raw_text.lower())
    match = _SECTION_HEADER_RE.match(lowered)
    if not match:
        return None
    kind = cast(Literal["round", "row"], match.group("kind"))
    start = int(match.group("start"))
    end = int(match.group("end")) if match.group("end") else start
    body, declared_count = strip_declared_count(match.group("body"))
    return NormalizedLine(
        line_number=line_number,
        raw_text=raw_text,
        kind=kind,
        number_start=start,
        number_end=end,
        body=body,
        declared_count=declared_count,
    )
