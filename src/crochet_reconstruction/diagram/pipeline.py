"""End-to-end orchestration: SVG source -> Diagram IR (``analyse``) and
Diagram IR + corrections -> ``StitchGraph``/``GeometryDocument``
(``compile``). Mirrors ``api/service.py``'s "never raise, always return a
structured result" contract for the written-pattern pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from crochet_reconstruction.diagram.compiler import CompiledDiagram, compile_diagram_to_stitch_graph
from crochet_reconstruction.diagram.corrections import (
    DiagramCorrectionSet,
    apply_relationship_overrides,
    apply_symbol_overrides,
)
from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.diagram.extraction import extract_symbols
from crochet_reconstruction.diagram.fingerprint import compute_diagram_fingerprint
from crochet_reconstruction.diagram.ir import (
    ConstructionMode,
    DiagramConstruction,
    DiagramDocument,
    DiagramSource,
)
from crochet_reconstruction.diagram.ontology import REVIEW_REQUIRED_THRESHOLD
from crochet_reconstruction.diagram.security import DEFAULT_LIMITS, SafetyLimits
from crochet_reconstruction.diagram.svg_parser import parse_svg
from crochet_reconstruction.diagram.topology import infer_topology

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisSummary:
    symbol_count: int
    classified_count: int
    unclassified_count: int
    round_count: int
    low_confidence_count: int
    ready_to_compile: bool


@dataclass(frozen=True)
class DiagramAnalysis:
    document: DiagramDocument | None
    diagnostics: list[DiagramDiagnostic]
    summary: AnalysisSummary | None


def _blocking(diagnostics: list[DiagramDiagnostic]) -> bool:
    return any(d.severity == "error" for d in diagnostics)


def analyse_svg_diagram(
    svg_source: str, *, limits: SafetyLimits = DEFAULT_LIMITS
) -> DiagramAnalysis:
    normalized, diagnostics = parse_svg(svg_source, limits)
    if normalized is None:
        return DiagramAnalysis(document=None, diagnostics=diagnostics, summary=None)

    try:
        extraction = extract_symbols(normalized.root, limits)
    except Exception:
        logger.exception("Unexpected error extracting diagram symbols")
        return DiagramAnalysis(
            document=None,
            diagnostics=[
                *diagnostics,
                DiagramDiagnostic(
                    severity="error",
                    code=DiagramDiagnosticCode.INTERNAL_ERROR,
                    message="An internal error occurred while extracting chart symbols.",
                ),
            ],
            summary=None,
        )
    diagnostics = [*diagnostics, *extraction.diagnostics]

    construction = DiagramConstruction(mode=ConstructionMode.CIRCULAR)
    try:
        topology = infer_topology(extraction.symbols, extraction.connectors, construction, limits)
    except Exception:
        logger.exception("Unexpected error inferring diagram topology")
        return DiagramAnalysis(
            document=None,
            diagnostics=[
                *diagnostics,
                DiagramDiagnostic(
                    severity="error",
                    code=DiagramDiagnosticCode.INTERNAL_ERROR,
                    message="An internal error occurred while inferring chart topology.",
                ),
            ],
            summary=None,
        )
    diagnostics = [*diagnostics, *topology.diagnostics]

    updated_symbols = [
        symbol.model_copy(
            update={
                "round_index": topology.round_index_by_symbol.get(
                    symbol.symbol_id, symbol.round_index
                ),
                "sequence_index": topology.sequence_index_by_symbol.get(
                    symbol.symbol_id, symbol.sequence_index
                ),
                "round_start": symbol.symbol_id in topology.round_start_symbol_ids
                or symbol.round_start,
                "round_closure": symbol.symbol_id in topology.round_closure_symbol_ids
                or symbol.round_closure,
            }
        )
        for symbol in extraction.symbols
    ]

    view_box = normalized.view_box
    document = DiagramDocument(
        source=DiagramSource(
            fingerprint=normalized.fingerprint,
            width=normalized.width,
            height=normalized.height,
            view_box=(
                view_box.min_x,
                view_box.min_y,
                view_box.min_x + view_box.width,
                view_box.min_y + view_box.height,
            ),
        ),
        construction=topology.construction,
        symbols=updated_symbols,
        relationships=topology.relationships,
        rounds=topology.rounds,
        diagnostics=diagnostics,
    )
    document = document.model_copy(update={"fingerprint": compute_diagram_fingerprint(document)})

    summary = _summarize(document, diagnostics)
    return DiagramAnalysis(document=document, diagnostics=diagnostics, summary=summary)


def _summarize(document: DiagramDocument, diagnostics: list[DiagramDiagnostic]) -> AnalysisSummary:
    classified = [s for s in document.symbols if s.stitch_type is not None and not s.ambiguous]
    unclassified = [s for s in document.symbols if s.stitch_type is None]
    low_confidence = [s for s in document.symbols if s.confidence < REVIEW_REQUIRED_THRESHOLD]
    return AnalysisSummary(
        symbol_count=len(document.symbols),
        classified_count=len(classified),
        unclassified_count=len(unclassified),
        round_count=len(document.rounds),
        low_confidence_count=len(low_confidence),
        ready_to_compile=not _blocking(diagnostics),
    )


@dataclass(frozen=True)
class DiagramCompileResult:
    compiled: CompiledDiagram | None
    document: DiagramDocument | None
    diagnostics: list[DiagramDiagnostic]


def compile_svg_diagram(
    document: DiagramDocument,
    corrections: DiagramCorrectionSet,
    *,
    limits: SafetyLimits = DEFAULT_LIMITS,
) -> DiagramCompileResult:
    """Apply corrections (see ``corrections.py`` for the documented
    application order), re-run topology inference, then convert to the
    existing ``StitchGraph``. Never raises."""
    diagnostics: list[DiagramDiagnostic] = []

    construction = document.construction
    if corrections.construction_overrides is not None:
        overrides = corrections.construction_overrides
        update = {k: v for k, v in overrides.model_dump().items() if v is not None}
        if "centre" in update:
            update["centre_method"] = "user_specified"
        construction = construction.model_copy(update=update)

    corrected_symbols, symbol_diagnostics = apply_symbol_overrides(document, corrections)
    diagnostics.extend(symbol_diagnostics)

    # Re-derive (never reuse stale) blocking diagnostics for any symbol
    # still unresolved after corrections. The original UNCLASSIFIED_SYMBOL/
    # AMBIGUOUS_SYMBOL diagnostics live on `document.diagnostics` from the
    # analyse pass — extraction never re-runs here, so that list would
    # otherwise silently go stale the moment corrections change which
    # symbols are actually still a problem (a corrected symbol must stop
    # blocking; an uncorrected one must keep blocking).
    for symbol in corrected_symbols:
        if symbol.stitch_type is not None:
            continue
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.AMBIGUOUS_SYMBOL
                if symbol.ambiguous
                else DiagramDiagnosticCode.UNCLASSIFIED_SYMBOL,
                message=f"symbol {symbol.symbol_id} still has no resolved stitch type",
                symbol_id=symbol.symbol_id,
                suggested_action="Assign this symbol's stitch type or mark it ignored.",
            )
        )

    original_explicit_parents: dict[str, list[str]] = {
        rel.source_symbol_ids[0]: list(rel.target_symbol_ids)
        for rel in document.relationships
        if rel.inference_method == "explicit_connector"
    }

    sequence_pins = {
        symbol_id: override.sequence_index
        for symbol_id, override in corrections.symbol_overrides.items()
        if override.sequence_index is not None
    }

    try:
        topology = infer_topology(
            corrected_symbols,
            [],
            construction,
            limits,
            explicit_parent_overrides=original_explicit_parents,
            sequence_pins=sequence_pins,
        )
    except Exception:
        logger.exception("Unexpected error re-inferring diagram topology during compile")
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.INTERNAL_ERROR,
                message="An internal error occurred while re-inferring chart topology.",
            )
        )
        return DiagramCompileResult(compiled=None, document=None, diagnostics=diagnostics)
    diagnostics.extend(topology.diagnostics)

    known_ids = {s.symbol_id for s in corrected_symbols}
    base_parent_map = {
        rel.source_symbol_ids[0]: list(rel.target_symbol_ids)
        for rel in topology.relationships
        if rel.relationship_type in ("parent_attachment", "centre_attachment")
    }
    final_parent_map, relationship_diagnostics = apply_relationship_overrides(
        base_parent_map, corrections, known_ids
    )
    diagnostics.extend(relationship_diagnostics)

    if _blocking(diagnostics):
        rebuilt_document = document.model_copy(
            update={
                "construction": topology.construction,
                "symbols": corrected_symbols,
                "relationships": topology.relationships,
                "rounds": topology.rounds,
                "diagnostics": diagnostics,
            }
        )
        return DiagramCompileResult(
            compiled=None, document=rebuilt_document, diagnostics=diagnostics
        )

    try:
        compiled, compile_diagnostics = compile_diagram_to_stitch_graph(
            corrected_symbols, topology, final_parent_map
        )
    except Exception:
        logger.exception("Unexpected error compiling diagram to stitch graph")
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.INTERNAL_ERROR,
                message="An internal error occurred while compiling the stitch graph.",
            )
        )
        return DiagramCompileResult(compiled=None, document=None, diagnostics=diagnostics)
    diagnostics.extend(compile_diagnostics)

    rebuilt_document = document.model_copy(
        update={
            "construction": topology.construction,
            "symbols": corrected_symbols,
            "relationships": topology.relationships,
            "rounds": topology.rounds,
            "diagnostics": diagnostics,
        }
    )
    rebuilt_document = rebuilt_document.model_copy(
        update={"fingerprint": compute_diagram_fingerprint(rebuilt_document)}
    )

    return DiagramCompileResult(
        compiled=compiled, document=rebuilt_document, diagnostics=diagnostics
    )
