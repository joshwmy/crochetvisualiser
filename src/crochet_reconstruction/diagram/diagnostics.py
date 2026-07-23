"""Structured diagnostics for the diagram-ingestion pipeline.

Deliberately a separate enum/model from
``parsing.written.diagnostics.Diagnostic`` — that type's ``DiagnosticCode``
is written-pattern-specific (syntax/count-mismatch codes with no SVG/spatial
meaning) and its ``line``/``column``/``section`` fields describe a text
source, not an SVG element. Sharing one flat code enum across both pipelines
would force meaningless fields on one side or the other. Both still share
the same *shape philosophy* (severity + code + message + structured
location, never a raw exception message) — see ``docs/diagnostic-codes.md``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

DiagramSeverity = Literal["info", "warning", "error"]


class DiagramDiagnosticCode(StrEnum):
    INVALID_SVG = "INVALID_SVG"
    UNSAFE_SVG_CONTENT = "UNSAFE_SVG_CONTENT"
    UNSUPPORTED_SVG_FEATURE = "UNSUPPORTED_SVG_FEATURE"
    SOURCE_TOO_LARGE = "SOURCE_TOO_LARGE"
    TOO_MANY_ELEMENTS = "TOO_MANY_ELEMENTS"
    UNSUPPORTED_EXTERNAL_REFERENCE = "UNSUPPORTED_EXTERNAL_REFERENCE"
    TRANSFORM_FAILURE = "TRANSFORM_FAILURE"
    UNCLASSIFIED_SYMBOL = "UNCLASSIFIED_SYMBOL"
    AMBIGUOUS_SYMBOL = "AMBIGUOUS_SYMBOL"
    UNSUPPORTED_SYMBOL = "UNSUPPORTED_SYMBOL"
    DUPLICATE_SYMBOL_ID = "DUPLICATE_SYMBOL_ID"
    MISSING_CENTRE = "MISSING_CENTRE"
    AMBIGUOUS_CENTRE = "AMBIGUOUS_CENTRE"
    ROUND_CLUSTERING_AMBIGUITY = "ROUND_CLUSTERING_AMBIGUITY"
    MISSING_PARENT = "MISSING_PARENT"
    AMBIGUOUS_PARENT = "AMBIGUOUS_PARENT"
    INVALID_CONNECTOR = "INVALID_CONNECTOR"
    NON_ADJACENT_DECREASE_PARENTS = "NON_ADJACENT_DECREASE_PARENTS"
    DISCONNECTED_COMPONENT = "DISCONNECTED_COMPONENT"
    UNSUPPORTED_CHART_CONSTRUCTION = "UNSUPPORTED_CHART_CONSTRUCTION"
    GRAPH_VALIDATION_FAILURE = "GRAPH_VALIDATION_FAILURE"
    MANUAL_CORRECTION_CONFLICT = "MANUAL_CORRECTION_CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DiagramDiagnostic(BaseModel):
    """One structured diagram-pipeline diagnostic.

    Ordering is always the order diagnostics were produced during a single
    deterministic pass (parse -> extract -> classify -> topology -> convert)
    — never re-sorted, so identical input always produces an identically
    ordered diagnostics list, matching the written-pattern parser's
    convention.
    """

    model_config = ConfigDict(frozen=True)

    severity: DiagramSeverity
    code: DiagramDiagnosticCode
    message: str
    svg_element_id: str | None = None
    symbol_id: str | None = None
    element_path: str | None = None
    round_index: int | None = None
    confidence: float | None = None
    suggested_action: str | None = None


def is_fatal(diagnostics: list[DiagramDiagnostic]) -> bool:
    return any(d.severity == "error" for d in diagnostics)
