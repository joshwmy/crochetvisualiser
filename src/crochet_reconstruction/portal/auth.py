"""Session-based auth for admins, invitation-token session for contributors,
and CSRF protection shared by both.

Sessions are Starlette's signed-cookie `SessionMiddleware` (already a
FastAPI dependency, so no new package is needed) — the cookie is signed
with `Settings.secret_key` and never stores a password or invitation token,
only opaque numeric IDs.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from crochet_reconstruction.portal.db import get_db
from crochet_reconstruction.portal.models import AdminUser, Contributor
from crochet_reconstruction.portal.security import constant_time_equals, generate_csrf_token

_ADMIN_LOGIN_PATH = "/admin/login"


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, submitted_token: str | None) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not submitted_token or not constant_time_equals(expected, submitted_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid form submission"
        )


# --- Admin ------------------------------------------------------------------


def login_admin(request: Request, admin: AdminUser) -> None:
    request.session.clear()
    request.session["admin_id"] = admin.id
    request.session["csrf_token"] = generate_csrf_token()


def logout_admin(request: Request) -> None:
    request.session.clear()


def get_current_admin(request: Request, db: Session) -> AdminUser | None:
    admin_id = request.session.get("admin_id")
    if admin_id is None:
        return None
    admin = db.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        return None
    return admin


def require_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    admin = get_current_admin(request, db)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"{_ADMIN_LOGIN_PATH}?next={request.url.path}"},
        )
    return admin


# --- Contributor --------------------------------------------------------


def start_contributor_session(
    request: Request, contributor: Contributor, invitation_id: int
) -> None:
    request.session["contributor_id"] = contributor.id
    request.session["invitation_id"] = invitation_id
    request.session.setdefault("csrf_token", generate_csrf_token())


def get_current_contributor(request: Request, db: Session) -> Contributor | None:
    contributor_id = request.session.get("contributor_id")
    if contributor_id is None:
        return None
    return db.get(Contributor, contributor_id)
