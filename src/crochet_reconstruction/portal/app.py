"""FastAPI application factory for the contributor portal."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from crochet_reconstruction.portal.config import Settings, get_settings, set_settings_cache
from crochet_reconstruction.portal.errors import PortalError
from crochet_reconstruction.portal.routers import admin, contributor

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Pin the process-wide cache to this exact instance so every dependency
    # provider that calls get_settings() independently (get_storage, the
    # rate limiters, db.py) sees the same settings this app was built with
    # — otherwise a caller-supplied Settings (as tests do) is silently
    # ignored everywhere except the routes that received it directly.
    set_settings_cache(settings)
    settings.ensure_data_directories()

    app = FastAPI(
        title="Crochet Contributor Portal",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.is_production,
    )

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    app.include_router(contributor.router)
    app.include_router(admin.router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'"
        )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    @app.exception_handler(PortalError)
    async def portal_error_handler(request: Request, exc: PortalError) -> JSONResponse:
        # A route that lets a PortalError propagate unhandled is a bug (every
        # route should catch the specific errors it expects and re-render a
        # friendly page) - this handler exists as a safety net, not the
        # primary error-handling path, so the message is generic externally.
        return JSONResponse(
            status_code=400, content={"detail": "the request could not be completed"}
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> RedirectResponse:
        return RedirectResponse("/healthz")

    return app
