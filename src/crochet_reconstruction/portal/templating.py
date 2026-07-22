"""Shared Jinja2 environment, plus small flash-message and CSRF helpers
routers use when rendering templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def set_flash(request: Request, message: str, level: str = "error") -> None:
    request.session["flash"] = {"message": message, "level": level}


def pop_flash(request: Request) -> dict[str, str] | None:
    flash: dict[str, str] | None = request.session.pop("flash", None)
    return flash


def render(request: Request, template_name: str, context: dict[str, Any]) -> Any:
    context = {**context, "request": request, "flash": pop_flash(request)}
    return templates.TemplateResponse(request, template_name, context)
