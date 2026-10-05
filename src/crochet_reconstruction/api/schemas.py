"""Typed request/response models for ``POST /api/visualizer/compile``.

JSON on the wire is camelCase (matching the TypeScript viewer's existing
``types/geometry.ts`` conventions would suggest, and the brief's own
example payloads); Python attributes stay snake_case. Pydantic's
``model_json_schema()`` on these models is this API's JSON Schema — see
``docs/open-source-resource-adoption.md``'s JSON Schema entry for why no
separate schema file is hand-authored.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from crochet_reconstruction.geometry.models import GeometryDocument
from crochet_reconstruction.graph.models import StitchGraph
from crochet_reconstruction.parsing.written.diagnostics import Diagnostic


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CompileOptions(_CamelModel):
    strict: bool = False
    """Block a compile that only succeeded because something was assumed or
    flagged — any ``warning`` diagnostic, plus ``ASSUMPTION_APPLIED`` (the
    default gauge substituted for one the pattern never stated).

    Defaults to ``False``, which is exactly the behaviour this field had while
    it was a documented no-op, so no existing caller changes behaviour without
    opting in. See ``api/strict_mode.py`` for the shared policy and
    ``docs/compile-api.md``'s "Strict mode" section."""


class CompileRequest(_CamelModel):
    source: str
    terminology: Literal["US"] = "US"
    options: CompileOptions = CompileOptions()


class ComponentsPayload(_CamelModel):
    """The compiled crochet structure: ``list[Component]``, not a full beanie
    ``Pattern`` — a written pattern has no ``ProjectInput``/
    ``CalculatedParameters`` (beanie-sizing fields that don't apply here).
    See docs/crochet-ir-spec.md."""

    components: list[dict[str, object]]


class CompileSummary(_CamelModel):
    section_count: int
    stitch_count: int
    component_count: int
    graph_fingerprint: str | None
    geometry_fingerprint: str | None


class CompileResponse(_CamelModel):
    success: bool
    pattern: ComponentsPayload | None
    stitch_graph: StitchGraph | None
    geometry: GeometryDocument | None
    diagnostics: list[Diagnostic]
    summary: CompileSummary | None
