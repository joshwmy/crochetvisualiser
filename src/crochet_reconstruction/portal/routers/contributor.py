"""Contributor-facing routes: invitation landing through confirmation.

Every `/contributor/project/{ref}/*` route checks that the current session's
contributor owns the project (`_get_owned_project`) — a mismatch returns 404
rather than 403, so the existence of another contributor's project is never
revealed.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from crochet_reconstruction.portal import services
from crochet_reconstruction.portal.auth import (
    get_or_create_csrf_token,
    start_contributor_session,
    validate_csrf,
)
from crochet_reconstruction.portal.config import Settings, get_settings
from crochet_reconstruction.portal.db import get_db
from crochet_reconstruction.portal.dependencies import get_storage, get_upload_rate_limiter
from crochet_reconstruction.portal.errors import (
    ImageLimitExceededError,
    InvitationError,
    ProjectNotEditableError,
    SubmissionValidationError,
)
from crochet_reconstruction.portal.images import ImageValidationError
from crochet_reconstruction.portal.models import Contributor, CrochetProject, ProjectImage
from crochet_reconstruction.portal.schemas import (
    ConsentInput,
    MaterialsAndGaugeInput,
    ProjectDetailsInput,
)
from crochet_reconstruction.portal.security import SlidingWindowRateLimiter
from crochet_reconstruction.portal.services import CONSENT_VERSION
from crochet_reconstruction.portal.storage import StorageBackend
from crochet_reconstruction.portal.templating import render, set_flash

router = APIRouter()

_IMAGE_SLOTS: dict[str, tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]] = {
    "beanie": (
        [
            ("front", "Front", "Full front view, laid flat or worn."),
            ("crown_top", "Crown / top", "Directly above the crown, showing the increase spiral."),
            ("stitch_macro", "Stitch macro", "Close enough to see individual stitches clearly."),
        ],
        [
            ("side", "Side", "Profile view."),
            ("interior", "Interior", "Inside of the hat."),
            ("brim", "Brim", "Close-up of the brim, if it has one."),
            ("seam_join", "Seam or join", "Any visible seam or round join."),
            ("scale_reference", "Scale reference", "The item next to a ruler or coin."),
        ],
    ),
    "stitch_swatch": (
        [
            ("swatch_full", "Full swatch", "The entire swatch, laid flat."),
            ("swatch_front_macro", "Front macro", "Close enough to see individual stitches."),
            ("swatch_edge", "Edge / side", "The swatch's side edge."),
        ],
        [("scale_reference", "Scale reference", "The swatch next to a ruler or coin.")],
    ),
    "other": (
        [],
        [
            ("front", "Front", "Full view of the item."),
            ("stitch_macro", "Stitch macro", "Close enough to see individual stitches."),
            ("scale_reference", "Scale reference", "The item next to a ruler or coin."),
        ],
    ),
}


def _get_owned_project(
    request: Request, db: Session, contributor: Contributor, ref: str
) -> CrochetProject:
    project = db.scalar(select(CrochetProject).where(CrochetProject.submission_reference == ref))
    if project is None or project.contributor_id != contributor.id:
        raise HTTPException(status_code=404, detail="not found")
    return project


def _form_str(form: object, key: str, default: str | None = None) -> str | None:
    """Extract a plain string field from Starlette form data, rejecting an
    unexpected file upload under that key rather than passing it through."""
    value = form.get(key, default)  # type: ignore[attr-defined]
    if value is None or isinstance(value, str):
        return value
    raise HTTPException(status_code=400, detail=f"expected a text value for {key!r}")


def _require_contributor(request: Request, db: Session = Depends(get_db)) -> Contributor:
    contributor_id = request.session.get("contributor_id")
    if contributor_id is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/"})
    contributor = db.get(Contributor, contributor_id)
    if contributor is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/"})
    return contributor


DbDep = Annotated[Session, Depends(get_db)]
StorageDep = Annotated[StorageBackend, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ContributorDep = Annotated[Contributor, Depends(_require_contributor)]


@router.get("/privacy")
def privacy_notice(request: Request) -> object:
    return render(request, "privacy.html", {})


@router.get("/invite/{token}")
def invitation_landing(request: Request, token: str, db: DbDep, settings: SettingsDep) -> object:
    try:
        invitation = services.get_valid_invitation(db, token)
    except InvitationError as exc:
        return render(
            request, "intro.html", {"error": str(exc), "token": token, "existing_projects": None}
        )

    contributor_id = request.session.get("contributor_id")
    contributor = db.get(Contributor, contributor_id) if contributor_id else None
    if contributor is not None and contributor.invitation_id == invitation.id:
        return render(
            request,
            "intro.html",
            {
                "token": token,
                "existing_projects": contributor.projects,
                "csrf_token": get_or_create_csrf_token(request),
            },
        )

    return render(
        request,
        "intro.html",
        {
            "token": token,
            "existing_projects": None,
            "contact_email_collection_enabled": settings.contact_email_collection_enabled,
            "csrf_token": get_or_create_csrf_token(request),
        },
    )


@router.post("/invite/{token}/redeem")
def redeem_invitation(
    request: Request,
    token: str,
    db: DbDep,
    display_identifier: Annotated[str, Form()],
    contact_email: Annotated[str | None, Form()] = None,
    csrf_token: Annotated[str | None, Form()] = None,
) -> object:
    validate_csrf(request, csrf_token)
    try:
        contributor = services.redeem_invitation(
            db,
            token,
            display_identifier=display_identifier.strip(),
            contact_email=contact_email or None,
        )
    except InvitationError as exc:
        set_flash(request, str(exc))
        return _redirect(f"/invite/{token}")

    start_contributor_session(request, contributor, contributor.invitation_id)
    project = services.create_draft_project(db, contributor)
    return _redirect(f"/contributor/project/{project.submission_reference}/consent")


@router.post("/invite/{token}/new-project")
def new_project(
    request: Request,
    token: str,
    db: DbDep,
    contributor: ContributorDep,
    csrf_token: Annotated[str | None, Form()] = None,
) -> object:
    validate_csrf(request, csrf_token)
    project = services.create_draft_project(db, contributor)
    return _redirect(f"/contributor/project/{project.submission_reference}/consent")


@router.post("/contributor/projects/new")
def new_project_from_session(
    request: Request,
    db: DbDep,
    contributor: ContributorDep,
    csrf_token: Annotated[str | None, Form()] = None,
) -> object:
    validate_csrf(request, csrf_token)
    project = services.create_draft_project(db, contributor)
    return _redirect(f"/contributor/project/{project.submission_reference}/consent")


def _redirect(location: str) -> object:
    from starlette.responses import RedirectResponse

    return RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/contributor/project/{ref}/consent")
def consent_form(request: Request, ref: str, db: DbDep, contributor: ContributorDep) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    form = project.consent
    return render(
        request,
        "consent.html",
        {
            "form": form,
            "errors": [],
            "consent_version": CONSENT_VERSION,
            "csrf_token": get_or_create_csrf_token(request),
        },
    )


@router.post("/contributor/project/{ref}/consent")
async def consent_submit(
    request: Request, ref: str, db: DbDep, contributor: ContributorDep
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    raw = await request.form()
    validate_csrf(request, _form_str(raw, "csrf_token"))

    checkboxes = (
        "owns_photographs",
        "research_evaluation_use",
        "product_development_use",
        "model_training_use",
        "public_demonstration_use",
        "contact_for_missing_details",
        "privacy_notice_accepted",
    )
    payload: dict[str, object] = {key: (key in raw) for key in checkboxes}
    payload["contributor_provided_identifier"] = contributor.display_identifier
    payload["attribution_preference"] = _form_str(raw, "attribution_preference", "anonymous")
    payload["attribution_text"] = _form_str(raw, "attribution_text")

    try:
        validated = ConsentInput.model_validate(payload)
    except ValidationError as exc:
        return render(
            request,
            "consent.html",
            {
                "form": _FormEcho(payload),
                "errors": _humanize_errors(exc),
                "consent_version": CONSENT_VERSION,
                "csrf_token": get_or_create_csrf_token(request),
            },
        )

    try:
        services.record_consent(db, project, **validated.model_dump())
    except ProjectNotEditableError as exc:
        set_flash(request, str(exc))
        return _redirect(f"/contributor/project/{ref}/review")

    return _redirect(f"/contributor/project/{ref}/details")


class _FormEcho(dict[str, object]):
    """Lets Jinja read `form.field` for both dict-based re-echoed submissions
    and ORM objects, by falling back to attribute-style dict access."""

    def __getattr__(self, item: str) -> object:
        return self.get(item)


def _humanize_errors(exc: ValidationError) -> list[str]:
    messages = []
    for error in exc.errors():
        message = error["msg"]
        message = message.removeprefix("Value error, ")
        messages.append(message)
    return messages


@router.get("/contributor/project/{ref}/details")
def details_form(request: Request, ref: str, db: DbDep, contributor: ContributorDep) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    return render(
        request,
        "details.html",
        {"form": project, "errors": [], "csrf_token": get_or_create_csrf_token(request)},
    )


@router.post("/contributor/project/{ref}/details")
async def details_submit(
    request: Request, ref: str, db: DbDep, contributor: ContributorDep
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))

    payload: dict[str, object] = {
        "name_or_description": _form_str(form, "name_or_description"),
        "craft_type": _form_str(form, "craft_type", "unknown"),
        "project_category": _form_str(form, "project_category"),
        "made_by_contributor": _form_str(form, "made_by_contributor", "unknown"),
        "used_existing_pattern": _form_str(form, "used_existing_pattern", "unknown"),
        "pattern_owned_by_contributor": _form_str(form, "pattern_owned_by_contributor", "unknown"),
        "construction_direction": _form_str(form, "construction_direction", "unknown"),
        "worked_in": _form_str(form, "worked_in", "unknown"),
        "round_style": _form_str(form, "round_style", "unknown"),
        "stitch_families": form.getlist("stitch_families"),
        "component_notes": _form_str(form, "component_notes"),
        "free_text_notes": _form_str(form, "free_text_notes"),
    }
    try:
        validated = ProjectDetailsInput.model_validate(payload)
    except ValidationError as exc:
        return render(
            request,
            "details.html",
            {
                "form": _FormEcho(payload),
                "errors": _humanize_errors(exc),
                "csrf_token": get_or_create_csrf_token(request),
            },
        )

    try:
        services.update_project_details(db, project, **validated.model_dump())
    except ProjectNotEditableError as exc:
        set_flash(request, str(exc))
        return _redirect(f"/contributor/project/{ref}/review")

    return _redirect(f"/contributor/project/{ref}/materials")


@router.get("/contributor/project/{ref}/materials")
def materials_form(request: Request, ref: str, db: DbDep, contributor: ContributorDep) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    return render(
        request,
        "materials_gauge.html",
        {"form": project.metadata_, "errors": [], "csrf_token": get_or_create_csrf_token(request)},
    )


@router.post("/contributor/project/{ref}/materials")
async def materials_submit(
    request: Request, ref: str, db: DbDep, contributor: ContributorDep
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))

    # Omit absent fields entirely rather than passing None explicitly: fields
    # like gauge_blocking_state have a non-None default (e.g. UNKNOWN) that
    # an explicit None would incorrectly override and fail validation on.
    payload: dict[str, object] = {
        key: value
        for key in MaterialsAndGaugeInput.model_fields
        if (value := _form_str(form, key)) is not None
    }
    payload["substitutions_made"] = "substitutions_made" in form
    try:
        validated = MaterialsAndGaugeInput.model_validate(payload)
    except ValidationError as exc:
        return render(
            request,
            "materials_gauge.html",
            {
                "form": _FormEcho(payload),
                "errors": _humanize_errors(exc),
                "csrf_token": get_or_create_csrf_token(request),
            },
        )

    try:
        services.upsert_project_metadata(db, project, **validated.model_dump())
    except ProjectNotEditableError as exc:
        set_flash(request, str(exc))
        return _redirect(f"/contributor/project/{ref}/review")

    return _redirect(f"/contributor/project/{ref}/images")


@router.get("/contributor/project/{ref}/images")
def images_form(
    request: Request, ref: str, db: DbDep, contributor: ContributorDep, settings: SettingsDep
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    required, recommended = _IMAGE_SLOTS.get(project.project_category.value, ([], []))
    have_types = {image.image_type.value for image in project.images}
    return render(
        request,
        "images.html",
        {
            "project_ref": ref,
            "uploaded_images": project.images,
            "required_slots": required,
            "recommended_slots": recommended,
            "have_types": have_types,
            "max_images": settings.max_images_per_project,
            "csrf_token": get_or_create_csrf_token(request),
        },
    )


@router.post("/contributor/project/{ref}/images/upload")
async def images_upload(
    request: Request,
    ref: str,
    db: DbDep,
    contributor: ContributorDep,
    storage: StorageDep,
    settings: SettingsDep,
    upload_limiter: Annotated[SlidingWindowRateLimiter, Depends(get_upload_rate_limiter)],
    image_type: Annotated[str, Form()],
    file: UploadFile,
    csrf_token: Annotated[str | None, Form()] = None,
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    validate_csrf(request, csrf_token)

    if not upload_limiter.allow(f"contributor:{contributor.id}"):
        set_flash(request, "Too many uploads in a short time. Please wait a minute and try again.")
        return _redirect(f"/contributor/project/{ref}/images")

    raw_bytes = await file.read()
    try:
        services.add_project_image(
            db,
            storage,
            project,
            image_type=image_type,
            raw_bytes=raw_bytes,
            original_filename=file.filename or "upload",
            max_upload_bytes=settings.max_upload_bytes,
            min_image_dimension_px=settings.min_image_dimension_px,
            max_images_per_project=settings.max_images_per_project,
        )
    except (ImageValidationError, ImageLimitExceededError, ProjectNotEditableError) as exc:
        set_flash(request, str(exc))
        return _redirect(f"/contributor/project/{ref}/images")

    return _redirect(f"/contributor/project/{ref}/images")


@router.post("/contributor/project/{ref}/images/{image_id}/delete")
async def images_delete(
    request: Request,
    ref: str,
    image_id: int,
    db: DbDep,
    contributor: ContributorDep,
    storage: StorageDep,
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    form = await request.form()
    validate_csrf(request, _form_str(form, "csrf_token"))

    image = db.get(ProjectImage, image_id)
    if image is None or image.project_id != project.id:
        raise HTTPException(status_code=404)

    db.delete(image)
    db.commit()
    services.log_audit(db, actor="contributor", event_type="image_deleted", project=project)
    return _redirect(f"/contributor/project/{ref}/images")


@router.get("/contributor/project/{ref}/images/{image_id}/preview")
def image_preview(
    request: Request,
    ref: str,
    image_id: int,
    db: DbDep,
    contributor: ContributorDep,
    storage: StorageDep,
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    image = db.get(ProjectImage, image_id)
    if image is None or image.project_id != project.id:
        raise HTTPException(status_code=404)

    from starlette.responses import Response

    data = storage.read_preview(project.submission_reference, image.stored_filename)
    return Response(content=data, media_type="image/jpeg")


@router.get("/contributor/project/{ref}/review")
def review_form(request: Request, ref: str, db: DbDep, contributor: ContributorDep) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    if project.status.value in ("draft", "changes_requested"):
        errors = services.missing_submission_requirements(project)
    else:
        errors = []
    return render(
        request,
        "review.html",
        {"project": project, "errors": errors, "csrf_token": get_or_create_csrf_token(request)},
    )


@router.post("/contributor/project/{ref}/submit")
def submit(
    request: Request,
    ref: str,
    db: DbDep,
    contributor: ContributorDep,
    csrf_token: Annotated[str | None, Form()] = None,
) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    validate_csrf(request, csrf_token)
    try:
        services.submit_project(db, project)
    except SubmissionValidationError:
        return _redirect(f"/contributor/project/{ref}/review")

    return _redirect(f"/contributor/project/{ref}/confirmation")


@router.get("/contributor/project/{ref}/confirmation")
def confirmation(request: Request, ref: str, db: DbDep, contributor: ContributorDep) -> object:
    project = _get_owned_project(request, db, contributor, ref)
    return render(request, "confirmation.html", {"project": project})


@router.get("/contributor/projects")
def my_projects(request: Request, db: DbDep, contributor: ContributorDep) -> object:
    """Session-driven project list — used once a contributor is already
    authenticated, since the plaintext invitation token is never stored and
    so cannot be recovered to rebuild an `/invite/{token}` link."""
    return render(
        request,
        "my_projects.html",
        {
            "existing_projects": contributor.projects,
            "csrf_token": get_or_create_csrf_token(request),
        },
    )
