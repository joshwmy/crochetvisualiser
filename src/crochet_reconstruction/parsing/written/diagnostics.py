"""Structured diagnostics shared by the parser and the compile API.

See ``docs/diagnostic-codes.md`` for the full catalogue with examples of
what triggers each code.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

Severity = Literal["info", "warning", "error"]


class DiagnosticCode(StrEnum):
    INVALID_SYNTAX = "INVALID_SYNTAX"
    UNSUPPORTED_SYNTAX = "UNSUPPORTED_SYNTAX"
    AMBIGUOUS_SYNTAX = "AMBIGUOUS_SYNTAX"
    UNKNOWN_ABBREVIATION = "UNKNOWN_ABBREVIATION"
    MISSING_FOUNDATION = "MISSING_FOUNDATION"
    INVALID_RANGE = "INVALID_RANGE"
    INVALID_REPEAT = "INVALID_REPEAT"
    STITCH_COUNT_MISMATCH = "STITCH_COUNT_MISMATCH"
    INSUFFICIENT_PARENT_STITCHES = "INSUFFICIENT_PARENT_STITCHES"
    INVALID_INCREASE = "INVALID_INCREASE"
    INVALID_DECREASE = "INVALID_DECREASE"
    GRAPH_VALIDATION_FAILURE = "GRAPH_VALIDATION_FAILURE"
    GEOMETRY_GENERATION_FAILURE = "GEOMETRY_GENERATION_FAILURE"
    INTERNAL_SERVER_FAILURE = "INTERNAL_SERVER_FAILURE"
    EMPTY_INPUT = "EMPTY_INPUT"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    INVALID_TERMINOLOGY = "INVALID_TERMINOLOGY"
    ASSUMPTION_APPLIED = "ASSUMPTION_APPLIED"
    STRICT_MODE_BLOCKED = "STRICT_MODE_BLOCKED"


class Diagnostic(BaseModel):
    """One structured parser/compiler diagnostic.

    Ordering is always: the order diagnostics were produced during a single
    deterministic left-to-right pass over the source (section by section,
    top to bottom) — never re-sorted afterward, so identical input always
    produces an identically-ordered diagnostics list.
    """

    model_config = ConfigDict(frozen=True)

    severity: Severity
    code: DiagnosticCode
    message: str
    line: int | None = None
    column: int | None = None
    section: int | None = None
    source_text: str | None = None
    expected: int | None = None
    actual: int | None = None


def is_fatal(diagnostics: list[Diagnostic]) -> bool:
    return any(d.severity == "error" for d in diagnostics)
