"""Administrator routes: login through review, trial linking, export, and
withdrawal/deletion.

Every state-changing route validates CSRF and requires `require_admin`.
Image bytes are served only through `/admin/projects/{ref}/images/{id}/preview`,
which checks admin auth first — there is no static or otherwise
unauthenticated path to an uploaded image anywhere in the app.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse, Response

from crochet_reconstruction.portal import services
from crochet_reconstruction.portal.auth import (
    get_or_create_csrf_token,
    login_admin,
    logout_admin,
    require_admin,
    validate_csrf,
)
from crochet_reconstruction.portal.config import get_settings
from crochet_reconstruction.portal.db import get_db
from crochet_reconstruction.portal.dependencies import get_login_rate_limiter, get_storage
from crochet_reconstruction.portal.errors import (
    PortalError,
    ProjectNotEditableError,
    TrialLinkValidationError,
)
from crochet_reconstruction.portal.models import (
    AdminUser,
    AuditEvent,
    CraftType,
    CrochetProject,
    DataQualityStatus,
    ProjectCategory,
    ProjectImage,
    ProjectStatus,
    ReviewDecisionType,
)
from crochet_reconstruction.portal.security import SlidingWindowRateLimiter, verify_password
from crochet_reconstruction.portal.services import ReviewDecisionInput
from crochet_reconstruction.portal.storage import StorageBackend
from crochet_reconstruction.portal.templating import render, set_flash

router = APIRouter(prefix="/admin")

DbDep = Annotated[Session, Depends(get_db)]
StorageDep = Annotated[StorageBackend, Depends(get_storage)]
AdminDep = Annotated[AdminUser, Depends(require_admin)]


def _form_str(form: object, key: str, default: str | None = None) -> str | None:
    value = form.get(key, default)  # type: ignore[attr-defined]
    if value is None or isinstance(value, str):
        return value
    raise HTTPException(status_code=400, detail=f"expected a text value for {key!r}")


def _redirect(location: str) -> Response:
    return RedirectResponse(location, status_code=303)


def _get_project_or_404(db: Session, ref: str) -> CrochetProject:
    project = db.scalar(select(CrochetProject).where(CrochetProject.submission_reference == ref))
    if project is None:
        raise HTTPException(status_code=404)
    return project


@router.get("/login")
def login_form(request: Request, next: str = "/admin/pending") -> object:
    return render(
        request, "admin/login.html", {"next": next, "csrf_token": get_or_create_csrf_token(request)}
    )


@router.post("/login")
def login_submit(
    request: Request,
    db: DbDep,
    limiter: Annotated[SlidingWindowRateLimiter, Depends(get_login_rate_limiter)],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/admin/pending",
    csrf_token: Annotated[str | None, Form()] = None,
) -> object:
    validate_csrf(request, csrf_token)

    client_ip = request.client.host if request.client else "unknown"
    if not limiter.allow(f"login:{client_ip}"):
        set_flash(request, "Too many login attempts. Please wait a minute and try again.")
        return _redirect("/admin/login")

    admin = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if admin is None or not admin.is_active or not verify_password(password, admin.password_hash):
        set_flash(request, "Incorrect username or password.")
        return _redirect("/admin/login")

    login_admin(request, admin)
    services.log_audit(db, actor=f"admin:{admin.username}", event_type="admin_login")
    return _redirect(next or "/admin/pending")


@router.post("/logout")
def logout(
    request: Request, db: DbDep, admin: AdminDep, csrf_token: Annotated[str | None, Form()] = None
) -> object:
    validate_csrf(request, csrf_token)
    services.log_audit(db, actor=f"admin:{admin.username}", event_type="admin_logout")
    logout_admin(request)
    return _redirect("/admin/login")


@router.get("/pending")
def pending_list(request: Request, db: DbDep, admin: AdminDep) -> object:
    projects = db.scalars(
        select(CrochetProject)
        .where(CrochetProject.status.in_([ProjectStatus.SUBMITTED, ProjectStatus.UNDER_REVIEW]))
        .order_by(CrochetProject.submitted_at)
    ).all()
    return render(request, "admin/pending.html", {"projects": projects, "admin": admin})


@router.get("/projects/{ref}")
def project_detail(request: Request, ref: str, db: DbDep, admin: AdminDep) -> object:
    project = _get_project_or_404(db, ref)
    audit_events = sorted(
        [e for e in _project_audit_events(db, project)], key=lambda e: e.created_at, reverse=True
    )
    return render(
        request,
        "admin/detail.html",
        {
            "project": project,
            "audit_events": audit_events,
            "csrf_token": get_or_create_csrf_token(request),
        },
    )


def _project_audit_events(db: Session, project: CrochetProject) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.project_id == project.id)).all())


@router.get("/projects/{ref}/images/{image_id}/preview")
def admin_image_preview(
    request: Request, ref: str, image_id: int, db: DbDep, admin: AdminDep, storage: StorageDep
) -> Response:
    project = _get_project_or_404(db, ref)
    image = db.get(ProjectImage, image_id)
    if image is None or image.project_id != project.id:
        raise HTTPException(status_code=404)
    data = storage.read_preview(project.submission_reference, image.stored_filename)
    return Response(content=data, media_type="image/jpeg")


@router.post("/projects/{ref}/start-review")
async def start_review(request: Request, ref: str, db: DbDep, admin: AdminDep) -> object:
    project = _get_project_or_404(db, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))
    try:
        services.admin_start_review(db, project, admin_actor=f"admin:{admin.username}")
    except PortalError as exc:
        set_flash(request, str(exc))
    return _redirect(f"/admin/projects/{ref}")


@router.post("/projects/{ref}/decision")
async def record_decision(request: Request, ref: str, db: DbDep, admin: AdminDep) -> object:
    project = _get_project_or_404(db, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))

    decision_raw = _form_str(form, "decision")
    try:
        decision_value = ReviewDecisionType(decision_raw) if decision_raw else None
    except ValueError:
        decision_value = None
    if decision_value is None:
        set_flash(request, "no valid decision selected")
        return _redirect(f"/admin/projects/{ref}")

    stitch_labels_raw = _form_str(form, "verified_stitch_labels") or ""
    stitch_labels = [s.strip() for s in stitch_labels_raw.split(",") if s.strip()] or None

    verified_craft_type_raw = _form_str(form, "verified_craft_type") or None
    verified_project_category_raw = _form_str(form, "verified_project_category") or None
    data_quality_status_raw = _form_str(form, "data_quality_status") or None

    try:
        services.record_review_decision(
            db,
            project,
            admin_id=admin.id,
            admin_actor=f"admin:{admin.username}",
            decision_input=ReviewDecisionInput(
                decision=decision_value,
                reason=_form_str(form, "reason"),
                verified_craft_type=CraftType(verified_craft_type_raw)
                if verified_craft_type_raw
                else None,
                verified_project_category=(
                    ProjectCategory(verified_project_category_raw)
                    if verified_project_category_raw
                    else None
                ),
                verified_stitch_labels=stitch_labels,
                data_quality_status=(
                    DataQualityStatus(data_quality_status_raw) if data_quality_status_raw else None
                ),
                exclusion_reason=_form_str(form, "exclusion_reason"),
            ),
        )
    except (PortalError, ValueError) as exc:
        set_flash(request, str(exc))

    return _redirect(f"/admin/projects/{ref}")


@router.post("/projects/{ref}/link-trial")
async def link_trial(request: Request, ref: str, db: DbDep, admin: AdminDep) -> object:
    project = _get_project_or_404(db, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))

    trial_id = _form_str(form, "trial_id") or ""
    pattern_fingerprint = _form_str(form, "pattern_fingerprint") or ""
    physical_result_id = _form_str(form, "physical_result_id")

    try:
        services.link_physical_trial(
            db,
            project,
            trial_id=trial_id,
            pattern_fingerprint=pattern_fingerprint,
            physical_result_id=physical_result_id,
            admin_actor=f"admin:{admin.username}",
        )
    except TrialLinkValidationError as exc:
        set_flash(request, str(exc))

    return _redirect(f"/admin/projects/{ref}")


@router.post("/projects/{ref}/withdraw")
async def withdraw(request: Request, ref: str, db: DbDep, admin: AdminDep) -> object:
    project = _get_project_or_404(db, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))
    try:
        services.withdraw_project(
            db, project, actor=f"admin:{admin.username}", reason=_form_str(form, "reason")
        )
    except ProjectNotEditableError as exc:
        set_flash(request, str(exc))
    return _redirect(f"/admin/projects/{ref}")


@router.post("/projects/{ref}/delete")
async def delete_data(
    request: Request, ref: str, db: DbDep, admin: AdminDep, storage: StorageDep
) -> object:
    project = _get_project_or_404(db, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))
    services.delete_project_data(db, storage, project, actor=f"admin:{admin.username}")
    return _redirect(f"/admin/projects/{ref}")


@router.get("/export")
def export_form(request: Request, admin: AdminDep) -> object:
    return render(request, "admin/export.html", {"csrf_token": get_or_create_csrf_token(request)})


@router.post("/export")
async def export_submit(
    request: Request, db: DbDep, admin: AdminDep, storage: StorageDep
) -> object:
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))
    output_dir = Path(get_settings().exports_dir) / "latest"
    summary = services.export_approved_projects(db, storage, output_dir)
    set_flash(
        request,
        f"Exported {summary['project_count']} project(s) to {summary['output_dir']}",
        level="success",
    )
    return _redirect("/admin/export")
