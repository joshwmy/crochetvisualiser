"""``POST /api/visualizer/compile`` — the visualiser's only business route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from crochet_reconstruction.api.config import ApiSettings, load_settings
from crochet_reconstruction.api.schemas import CompileRequest, CompileResponse
from crochet_reconstruction.api.service import compile_written_pattern

router = APIRouter(prefix="/api/visualizer", tags=["visualizer"])


def get_settings() -> ApiSettings:
    return load_settings()


@router.post("/compile", response_model=CompileResponse)
def compile_pattern(
    request: CompileRequest, settings: ApiSettings = Depends(get_settings)
) -> CompileResponse:
    return compile_written_pattern(
        request.source,
        max_source_length=settings.max_source_length,
        options=request.options,
    )
