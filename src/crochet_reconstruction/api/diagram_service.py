"""Diagram-ingestion compile orchestration, mirroring ``api/service.py``'s
"never raise, always return a structured response" contract.

Source-size/element/topology limits are enforced inside
``diagram.pipeline`` itself (``diagram.security.SafetyLimits``) — unlike the
written-pattern path's ``ApiSettings.max_source_length`` (a character count
sized for hand-typed text), an SVG diagram's own byte-size limit is already
diagram-domain-specific and does not belong in the generic API settings
object.
"""

from __future__ import annotations

from crochet_reconstruction.api.diagram_schemas import (
    DiagramAnalyseResponse,
    DiagramAnalyseSummary,
    DiagramCompileResponse,
    DiagramCompileSummary,
)
from crochet_reconstruction.api.strict_mode import (
    strict_block_message,
    strict_blocking_diagnostics,
)
from crochet_reconstruction.diagram.corrections import DiagramCorrectionSet
from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.diagram.ir import DiagramDocument
from crochet_reconstruction.diagram.pipeline import analyse_svg_diagram, compile_svg_diagram
from crochet_reconstruction.geometry.layout import build_geometry
from crochet_reconstruction.graph.errors import StitchGraphError
from crochet_reconstruction.graph.validation import validate_graph
from crochet_reconstruction.parsing.written.semantic import DEFAULT_WRITTEN_PATTERN_GAUGE


def analyse_diagram(svg_source: str, *, strict: bool = False) -> DiagramAnalyseResponse:
    analysis = analyse_svg_diagram(svg_source)

    # Strict analysis withholds readiness; it never turns a successfully parsed
    # chart into a failure. Reporting what the chart contains is analysis's
    # whole job — refusing to report it would leave the user with nothing to
    # correct in the 2D review step.
    ready_to_compile = analysis.summary is not None and analysis.summary.ready_to_compile
    if strict and ready_to_compile and strict_blocking_diagnostics(analysis.diagnostics):
        ready_to_compile = False

    summary = (
        DiagramAnalyseSummary(
            symbol_count=analysis.summary.symbol_count,
            classified_count=analysis.summary.classified_count,
            unclassified_count=analysis.summary.unclassified_count,
            round_count=analysis.summary.round_count,
            low_confidence_count=analysis.summary.low_confidence_count,
            ready_to_compile=ready_to_compile,
        )
        if analysis.summary is not None
        else None
    )
    return DiagramAnalyseResponse(
        success=analysis.document is not None,
        diagram=analysis.document,
        diagnostics=analysis.diagnostics,
        summary=summary,
    )


def compile_diagram(
    diagram: DiagramDocument, corrections: DiagramCorrectionSet, *, strict: bool = False
) -> DiagramCompileResponse:
    result = compile_svg_diagram(diagram, corrections)

    if result.compiled is None:
        return DiagramCompileResponse(
            success=False,
            diagram=result.document,
            stitch_graph=None,
            geometry=None,
            diagnostics=result.diagnostics,
            summary=None,
        )

    graph = result.compiled.graph
    try:
        validate_graph(graph)
    except StitchGraphError as exc:
        return DiagramCompileResponse(
            success=False,
            diagram=result.document,
            stitch_graph=None,
            geometry=None,
            diagnostics=[
                *result.diagnostics,
                DiagramDiagnostic(
                    severity="error",
                    code=DiagramDiagnosticCode.GRAPH_VALIDATION_FAILURE,
                    message=f"The compiled diagram failed stitch-graph validation: {exc}",
                ),
            ],
            summary=None,
        )

    # As in the written path: checked last, so strict mode only ever refuses a
    # compile that would otherwise have succeeded. The corrected document is
    # still returned, so the user can see and fix what strict objected to.
    if strict:
        blocking = strict_blocking_diagnostics(result.diagnostics)
        if blocking:
            return DiagramCompileResponse(
                success=False,
                diagram=result.document,
                stitch_graph=None,
                geometry=None,
                diagnostics=[
                    *result.diagnostics,
                    DiagramDiagnostic(
                        severity="error",
                        code=DiagramDiagnosticCode.STRICT_MODE_BLOCKED,
                        message=strict_block_message(blocking),
                    ),
                ],
                summary=None,
            )

    geometry = build_geometry(result.compiled.components, DEFAULT_WRITTEN_PATTERN_GAUGE, graph)

    section_count = sum(len(component.rounds) for component in result.compiled.components)
    summary = DiagramCompileSummary(
        section_count=section_count,
        stitch_count=len(graph.nodes),
        component_count=len(result.compiled.components),
        graph_fingerprint=graph.fingerprint,
        geometry_fingerprint=geometry.geometry_fingerprint,
    )
    return DiagramCompileResponse(
        success=True,
        diagram=result.document,
        stitch_graph=graph,
        geometry=geometry,
        diagnostics=result.diagnostics,
        summary=summary,
    )
