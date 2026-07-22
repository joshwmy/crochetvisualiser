"""Compile orchestration: request -> parser -> graph -> geometry -> response.

Kept independent of FastAPI/HTTP so it can be unit-tested directly (see
``tests/api/test_service.py``) without spinning up a test client.
"""

from __future__ import annotations

import logging

from crochet_reconstruction.api.schemas import (
    CompileOptions,
    CompileResponse,
    CompileSummary,
    ComponentsPayload,
)
from crochet_reconstruction.geometry.layout import build_geometry
from crochet_reconstruction.graph.builder import build_stitch_graph
from crochet_reconstruction.graph.errors import StitchGraphError
from crochet_reconstruction.graph.validation import validate_graph
from crochet_reconstruction.parsing.written import parse_written_pattern
from crochet_reconstruction.parsing.written.diagnostics import Diagnostic, DiagnosticCode
from crochet_reconstruction.parsing.written.semantic import DEFAULT_WRITTEN_PATTERN_GAUGE

logger = logging.getLogger(__name__)

FAILURE_RESPONSE_SHAPE = {"pattern": None, "stitch_graph": None, "geometry": None, "summary": None}


def _failure(diagnostics: list[Diagnostic]) -> CompileResponse:
    return CompileResponse(success=False, diagnostics=diagnostics, **FAILURE_RESPONSE_SHAPE)


def compile_written_pattern(
    source: str, *, max_source_length: int, options: CompileOptions | None = None
) -> CompileResponse:
    """Run the full written-pattern -> geometry pipeline, never raising.

    Every failure path (parse error, graph-validation failure, geometry
    failure, or a genuinely unexpected internal exception) returns a
    structured ``CompileResponse`` with ``success=False`` and at least one
    error-severity diagnostic — the caller (the HTTP route) never has to
    catch an exception from this function to build a clean response.
    """
    del options  # accepted for forward compatibility; see CompileOptions docstring

    if len(source) > max_source_length:
        return _failure(
            [
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.INPUT_TOO_LARGE,
                    message=f"Pattern source is {len(source)} characters, exceeding the "
                    f"limit of {max_source_length}.",
                    expected=max_source_length,
                    actual=len(source),
                )
            ]
        )

    try:
        components, diagnostics = parse_written_pattern(source)
    except Exception:
        logger.exception("Unexpected error in parse_written_pattern")
        return _failure(
            [
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.INTERNAL_SERVER_FAILURE,
                    message="An internal error occurred while parsing the pattern.",
                )
            ]
        )

    if components is None:
        return _failure(diagnostics)

    try:
        graph = build_stitch_graph(components)
        validate_graph(graph)
    except StitchGraphError as exc:
        return _failure(
            [
                *diagnostics,
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.GRAPH_VALIDATION_FAILURE,
                    message=f"The compiled pattern failed stitch-graph validation: {exc}",
                ),
            ]
        )
    except Exception:
        logger.exception("Unexpected error building/validating the stitch graph")
        return _failure(
            [
                *diagnostics,
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.INTERNAL_SERVER_FAILURE,
                    message="An internal error occurred while building the stitch graph.",
                ),
            ]
        )

    try:
        geometry = build_geometry(components, DEFAULT_WRITTEN_PATTERN_GAUGE, graph)
    except Exception:
        logger.exception("Unexpected error generating geometry")
        return _failure(
            [
                *diagnostics,
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.GEOMETRY_GENERATION_FAILURE,
                    message="An internal error occurred while generating 3D geometry.",
                ),
            ]
        )

    section_count = sum(len(component.rounds) for component in components)
    summary = CompileSummary(
        section_count=section_count,
        stitch_count=len(graph.nodes),
        component_count=len(components),
        graph_fingerprint=graph.fingerprint,
        geometry_fingerprint=geometry.geometry_fingerprint,
    )
    payload = ComponentsPayload(components=[c.model_dump(mode="json") for c in components])
    return CompileResponse(
        success=True,
        pattern=payload,
        stitch_graph=graph,
        geometry=geometry,
        diagnostics=diagnostics,
        summary=summary,
    )
