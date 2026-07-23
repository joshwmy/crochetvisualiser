"""``POST /api/visualizer/diagram/analyse`` and ``.../compile`` — the SVG
diagram-ingestion routes. Same prefix family as ``visualizer.py``'s
written-pattern compile route, kept in a separate router module (not a
separate app) so the two input paths stay independently testable and
readable without mixing unrelated request/response shapes in one file.
"""

from __future__ import annotations

from fastapi import APIRouter

from crochet_reconstruction.api.diagram_schemas import (
    DiagramAnalyseRequest,
    DiagramAnalyseResponse,
    DiagramCompileRequest,
    DiagramCompileResponse,
)
from crochet_reconstruction.api.diagram_service import analyse_diagram, compile_diagram

router = APIRouter(prefix="/api/visualizer/diagram", tags=["visualizer", "diagram"])


@router.post("/analyse", response_model=DiagramAnalyseResponse)
def analyse(request: DiagramAnalyseRequest) -> DiagramAnalyseResponse:
    return analyse_diagram(request.svg_source)


@router.post("/compile", response_model=DiagramCompileResponse)
def compile_route(request: DiagramCompileRequest) -> DiagramCompileResponse:
    return compile_diagram(request.diagram, request.corrections)
