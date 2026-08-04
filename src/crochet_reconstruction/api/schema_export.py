"""Reproducible, versioned JSON Schema artefact generation.

Every model here already generates a correct JSON Schema via Pydantic's
``model_json_schema()`` — this module's only job is to make that
reproducible as *committed files* rather than an ad-hoc one-liner (see
``docs/open-source-resource-adoption.md``'s JSON Schema entry for why a
committed artefact was judged unnecessary for the written-pattern slice
alone, and ``docs/procedural-yarn-milestone-audit.md`` for why this
completion slice raised the bar to "committed and match-tested").

Determinism guarantees:

* ``sort_keys=True`` — no key-ordering drift between runs or Python
  versions.
* No timestamps, no absolute file paths, no non-deterministic ordering
  anywhere in the emitted JSON.
* ``$id`` and ``version`` are added deterministically from this module's
  own constants, never from wall-clock time or environment.

Run ``python -m crochet_reconstruction.api.schema_export`` to (re)write the
files under ``schemas/`` at the repository root. ``tests/test_schema_export.py``
asserts the committed files match what this module would generate right now.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from crochet_reconstruction.api.diagram_schemas import (
    DiagramAnalyseRequest,
    DiagramAnalyseResponse,
    DiagramCompileRequest,
    DiagramCompileResponse,
)
from crochet_reconstruction.api.schemas import CompileRequest, CompileResponse
from crochet_reconstruction.diagram.corrections import (
    CORRECTIONS_SCHEMA_VERSION,
    DiagramCorrectionSet,
)
from crochet_reconstruction.diagram.ir import (
    DIAGRAM_SCHEMA_VERSION,
    DiagramDocument,
    DiagramRelationship,
    DiagramSymbol,
)
from crochet_reconstruction.geometry.models import GEOMETRY_SCHEMA_VERSION, GeometryDocument
from crochet_reconstruction.graph.models import GRAPH_SCHEMA_VERSION, StitchGraph
from crochet_reconstruction.parsing.written.diagnostics import Diagnostic

# The compile API's own request/response contract version — independent of
# GeometryDocument/StitchGraph's own schema_version fields, since the API
# shape (e.g. adding an optional field to CompileResponse) can change on a
# different cadence than the geometry/graph payload shapes it carries.
#
# 1.1.0: `options.strict` became real behaviour (api/strict_mode.py) and its
# default flipped from true to false; `STRICT_MODE_BLOCKED` was added to both
# diagnostic code enums. Minor rather than major because omitting `options`
# entirely — what every current client does, including the viewer — behaves
# exactly as it did at 1.0.0. See docs/schema-artifacts.md's compatibility
# section for the one case that does change.
API_CONTRACT_VERSION = "1.1.0"

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "schemas"

_BASE_URL = "https://crochet-reconstruction.invalid/schemas"


def _schema_for(model: type[BaseModel], *, filename: str, version: str) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema["$id"] = f"{_BASE_URL}/{filename}"
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["version"] = version
    return schema


def generate_schema_files() -> dict[str, dict[str, Any]]:
    """Returns ``{filename: schema_dict}`` for every artefact this project commits.

    The single source of truth for *which* models get a committed schema
    and what version each carries — both ``__main__`` (writes files) and
    the match-test import this function, so they can never drift apart.
    """
    return {
        "stitch_graph.schema.json": _schema_for(
            StitchGraph, filename="stitch_graph.schema.json", version=GRAPH_SCHEMA_VERSION
        ),
        "geometry_document.schema.json": _schema_for(
            GeometryDocument,
            filename="geometry_document.schema.json",
            version=GEOMETRY_SCHEMA_VERSION,
        ),
        "compile_request.schema.json": _schema_for(
            CompileRequest, filename="compile_request.schema.json", version=API_CONTRACT_VERSION
        ),
        "compile_response.schema.json": _schema_for(
            CompileResponse, filename="compile_response.schema.json", version=API_CONTRACT_VERSION
        ),
        "diagnostic.schema.json": _schema_for(
            Diagnostic, filename="diagnostic.schema.json", version=API_CONTRACT_VERSION
        ),
        "diagram_ir.schema.json": _schema_for(
            DiagramDocument, filename="diagram_ir.schema.json", version=DIAGRAM_SCHEMA_VERSION
        ),
        "diagram_symbol.schema.json": _schema_for(
            DiagramSymbol, filename="diagram_symbol.schema.json", version=DIAGRAM_SCHEMA_VERSION
        ),
        "diagram_relationship.schema.json": _schema_for(
            DiagramRelationship,
            filename="diagram_relationship.schema.json",
            version=DIAGRAM_SCHEMA_VERSION,
        ),
        "diagram_correction_set.schema.json": _schema_for(
            DiagramCorrectionSet,
            filename="diagram_correction_set.schema.json",
            version=CORRECTIONS_SCHEMA_VERSION,
        ),
        "diagram_analyse_request.schema.json": _schema_for(
            DiagramAnalyseRequest,
            filename="diagram_analyse_request.schema.json",
            version=API_CONTRACT_VERSION,
        ),
        "diagram_analyse_response.schema.json": _schema_for(
            DiagramAnalyseResponse,
            filename="diagram_analyse_response.schema.json",
            version=API_CONTRACT_VERSION,
        ),
        "diagram_compile_request.schema.json": _schema_for(
            DiagramCompileRequest,
            filename="diagram_compile_request.schema.json",
            version=API_CONTRACT_VERSION,
        ),
        "diagram_compile_response.schema.json": _schema_for(
            DiagramCompileResponse,
            filename="diagram_compile_response.schema.json",
            version=API_CONTRACT_VERSION,
        ),
    }


def render(schema: dict[str, Any]) -> str:
    """The one canonical text rendering every writer/reader must use."""
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_schema_files(directory: Path = SCHEMAS_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for filename, schema in generate_schema_files().items():
        (directory / filename).write_text(render(schema), encoding="utf-8")


if __name__ == "__main__":
    write_schema_files()
    print(f"Wrote {len(generate_schema_files())} schema files to {SCHEMAS_DIR}")
