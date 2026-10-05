"""Typed request/response models for the diagram-ingestion endpoints
(``POST /api/visualizer/diagram/analyse`` and ``.../compile``).

Follows ``api/schemas.py``'s convention exactly: the thin request/response
wrapper types here use ``_CamelModel`` (camelCase on the wire), but the deep
domain payloads they carry (``DiagramDocument``, ``DiagramCorrectionSet``,
``StitchGraph``, ``GeometryDocument``) stay snake_case, matching how
``CompileResponse`` already carries snake_case ``StitchGraph``/
``GeometryDocument`` payloads without renaming their fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from crochet_reconstruction.diagram.corrections import DiagramCorrectionSet
from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic
from crochet_reconstruction.diagram.ir import DiagramDocument
from crochet_reconstruction.geometry.models import GeometryDocument
from crochet_reconstruction.graph.models import StitchGraph


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DiagramAnalyseOptions(_CamelModel):
    construction_mode: Literal["circular"] = "circular"
    strict: bool = False
    """Require a clean analysis before ``summary.ready_to_compile`` is true —
    any ``warning`` diagnostic withholds readiness in addition to the existing
    unclassified/low-confidence checks.

    Analysis itself never fails on strictness: an imperfect chart still returns
    ``success: true`` with the full document, exactly as documented for the
    non-strict case. Strict only tightens the *readiness* verdict, because
    analysis's job is to report what the chart contains, not to refuse to
    report it. See ``api/strict_mode.py``."""


class DiagramAnalyseRequest(_CamelModel):
    svg_source: str
    options: DiagramAnalyseOptions = DiagramAnalyseOptions()


class DiagramAnalyseSummary(_CamelModel):
    symbol_count: int
    classified_count: int
    unclassified_count: int
    round_count: int
    low_confidence_count: int
    ready_to_compile: bool


class DiagramAnalyseResponse(_CamelModel):
    success: bool
    diagram: DiagramDocument | None
    diagnostics: list[DiagramDiagnostic]
    summary: DiagramAnalyseSummary | None


class DiagramCompileOptions(_CamelModel):
    strict: bool = False
    """Same policy as ``CompileOptions.strict`` (``api/strict_mode.py``): any
    ``warning`` diagnostic blocks the compile. Defaults to ``False`` so the
    previous no-op behaviour is preserved for callers that don't opt in."""


class DiagramCompileRequest(_CamelModel):
    diagram: DiagramDocument
    corrections: DiagramCorrectionSet = DiagramCorrectionSet()
    options: DiagramCompileOptions = DiagramCompileOptions()


class DiagramCompileSummary(_CamelModel):
    section_count: int
    stitch_count: int
    component_count: int
    graph_fingerprint: str | None
    geometry_fingerprint: str | None


class DiagramCompileResponse(_CamelModel):
    success: bool
    source_kind: Literal["svg_diagram"] = "svg_diagram"
    diagram: DiagramDocument | None
    stitch_graph: StitchGraph | None
    geometry: GeometryDocument | None
    diagnostics: list[DiagramDiagnostic]
    summary: DiagramCompileSummary | None
