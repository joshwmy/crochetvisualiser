"""FastAPI application factory for the visualizer compile API.

Separate from ``portal.app.create_app`` — no shared routers, no shared
database, no shared session middleware. The two apps may run in the same
process for local development convenience, but neither imports the other.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crochet_reconstruction.api.config import ApiSettings, load_settings
from crochet_reconstruction.api.routers import visualizer


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()

    app = FastAPI(
        title="Crochet Scientific Visualizer API",
        description="Compiles a written crochet pattern into stitch-graph geometry.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type"],
    )

    app.include_router(visualizer.router)
    # Without this override, the route's `Depends(get_settings)` re-derives
    # settings from the environment on every request, ignoring whatever
    # `settings` was explicitly passed to this factory — the same class of
    # bug documented in docs/portal-architecture.md's settings-cache note.
    app.dependency_overrides[visualizer.get_settings] = lambda: resolved_settings

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
