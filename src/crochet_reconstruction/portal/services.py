"""Business logic. Routes call these functions; they never query the DB or
enforce rules directly — see docs/portal-architecture.md.

Reuse note: `link_physical_trial` validates against
`crochet_reconstruction.physical_validation.trial_matrix` (the same
`TRIAL_MATRIX` / `compile_trial` the physical-validation ingestion pipeline
uses) rather than re-implementing trial/fingerprint knowledge here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from crochet_reconstruction.physical_validation.trial_matrix import TRIAL_MATRIX, compile_trial
from crochet_reconstruction.portal.errors import (
    ImageLimitExceededError,
    InvitationExhaustedError,
    InvitationExpiredError,
    InvitationInvalidError,
    InvitationRevokedError,
    ProjectNotEditableError,
    SubmissionValidationError,
    TrialLinkValidationError,
)
from crochet_reconstruction.portal.images import ProcessedImage, sanitize_original_filename
from crochet_reconstruction.portal.images import validate_and_process_image as _validate_image
from crochet_reconstruction.portal.models import (
    AuditEvent,
    ConsentRecord,
    Contributor,
    CrochetProject,
    Invitation,
    PhysicalTrialLink,
    ProjectImage,
    ProjectMetadata,
    ProjectStatus,
    ReviewDecision,
    ReviewDecisionType,
)
from crochet_reconstruction.portal.security import (
    generate_invitation_token,
    generate_submission_reference,
    hash_token,
)
from crochet_reconstruction.portal.state_machine import assert_valid_transition, is_withdrawable
from crochet_reconstruction.portal.storage import StorageBackend

CONSENT_VERSION = "1.0"
"""Bump whenever the consent question set or privacy notice materially
changes; existing ConsentRecord rows keep their original version, so a
change here never silently reinterprets past consent."""

_REQUIRED_IMAGE_TYPES_BY_CATEGORY: dict[str, frozenset[str]] = {
    "beanie": frozenset({"front", "crown_top", "stitch_macro"}),
    "stitch_swatch": frozenset({"swatch_full", "swatch_front_macro", "swatch_edge"}),
}


def _now() -> datetime:
    """Naive UTC timestamp.

    SQLite (the pilot's database) does not preserve timezone info across a
    round-trip even for a ``DateTime(timezone=True)`` column, so storing
    timezone-aware values here would compare unequal/incomparable to values
    just read back from the DB. The whole portal therefore standardises on
    naive datetimes that are UTC *by convention* — never compare one of
    these to a timezone-aware value.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def log_audit(
    db: Session,
    *,
    actor: str,
    event_type: str,
    project: CrochetProject | None = None,
    contributor: Contributor | None = None,
    detail: str | None = None,
) -> AuditEvent:
    """Record an audit event. ``detail`` must never contain image content."""
    event = AuditEvent(
        project_id=project.id if project else None,
        contributor_id=contributor.id if contributor else None,
        actor=actor,
        event_type=event_type,
        detail=detail,
        created_at=_now(),
    )
    db.add(event)
    db.commit()
    return event


# --- Invitations -------------------------------------------------------


def create_invitation(
    db: Session, *, label: str, expiry_days: int, max_uses: int = 1
) -> tuple[Invitation, str]:
    """Returns the ``Invitation`` row and the plaintext token (shown once,
    never persisted)."""
    token = generate_invitation_token()
    invitation = Invitation(
        token_hash=hash_token(token),
        label=label,
        max_uses=max_uses,
        used_count=0,
        created_at=_now(),
        expires_at=_now() + timedelta(days=expiry_days),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    log_audit(db, actor="admin", event_type="invitation_created", detail=f"label={label!r}")
    return invitation, token


def revoke_invitation(db: Session, invitation: Invitation) -> None:
    invitation.revoked_at = _now()
    db.commit()
    log_audit(
        db, actor="admin", event_type="invitation_revoked", detail=f"invitation_id={invitation.id}"
    )


def get_valid_invitation(db: Session, token: str) -> Invitation:
    """Look up an invitation by token and check it is usable. Does not
    consume a use — call ``redeem_invitation`` for that."""
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if invitation is None:
        raise InvitationInvalidError("this invitation link is not recognised")
    if invitation.revoked_at is not None:
        raise InvitationRevokedError("this invitation link has been revoked")
    if invitation.expires_at < _now():
        raise InvitationExpiredError("this invitation link has expired")
    if invitation.used_count >= invitation.max_uses:
        raise InvitationExhaustedError("this invitation link has already been used")
    return invitation


def redeem_invitation(
    db: Session, token: str, *, display_identifier: str, contact_email: str | None
) -> Contributor:
    invitation = get_valid_invitation(db, token)
    invitation.used_count += 1
    contributor = Contributor(
        invitation_id=invitation.id,
        display_identifier=display_identifier,
        contact_email=contact_email,
        created_at=_now(),
    )
    db.add(contributor)
    db.commit()
    db.refresh(contributor)
    log_audit(
        db,
        actor="contributor",
        event_type="invitation_redeemed",
        contributor=contributor,
        detail=f"invitation_id={invitation.id}",
    )
    return contributor


# --- Projects ------------------------------------------------------------


def create_draft_project(db: Session, contributor: Contributor) -> CrochetProject:
    project = CrochetProject(
        contributor_id=contributor.id,
        submission_reference=generate_submission_reference(),
        status=ProjectStatus.DRAFT,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    log_audit(
        db,
        actor="contributor",
        event_type="project_created",
        project=project,
        contributor=contributor,
    )
    return project


def _assert_editable(project: CrochetProject) -> None:
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.CHANGES_REQUESTED):
        raise ProjectNotEditableError(
            f"project is {project.status.value!r} and can no longer be edited by the contributor"
        )


def update_project_details(db: Session, project: CrochetProject, **fields: Any) -> CrochetProject:
    _assert_editable(project)
    for key, value in fields.items():
        setattr(project, key, value)
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project


def upsert_project_metadata(db: Session, project: CrochetProject, **fields: Any) -> ProjectMetadata:
    _assert_editable(project)
    metadata = project.metadata_
    if metadata is None:
        # Assigning through the relationship (rather than constructing with
        # a raw project_id FK) keeps project.metadata_ correct in-memory for
        # the rest of this session — sessions use expire_on_commit=False, so
        # a raw-FK insert would leave the cached relationship stale for any
        # later call sharing this same session (see services test suite).
        metadata = ProjectMetadata()
        project.metadata_ = metadata
    for key, value in fields.items():
        setattr(metadata, key, value)
    project.updated_at = _now()
    db.commit()
    db.refresh(metadata)
    return metadata


def record_consent(
    db: Session,
    project: CrochetProject,
    *,
    contributor_provided_identifier: str,
    owns_photographs: bool,
    research_evaluation_use: bool,
    product_development_use: bool,
    model_training_use: bool,
    public_demonstration_use: bool,
    contact_for_missing_details: bool,
    privacy_notice_accepted: bool,
    attribution_preference: str,
    attribution_text: str | None,
) -> ConsentRecord:
    _assert_editable(project)
    consent = project.consent
    if consent is None:
        # See the equivalent note in upsert_project_metadata: relationship
        # assignment, not a raw project_id FK, keeps project.consent fresh
        # for later calls sharing this session.
        consent = ConsentRecord()
        project.consent = consent
    consent.contributor_provided_identifier = contributor_provided_identifier
    consent.consent_version = CONSENT_VERSION
    consent.consented_at = _now()
    consent.owns_photographs = owns_photographs
    consent.research_evaluation_use = research_evaluation_use
    consent.product_development_use = product_development_use
    consent.model_training_use = model_training_use
    consent.public_demonstration_use = public_demonstration_use
    consent.contact_for_missing_details = contact_for_missing_details
    consent.privacy_notice_accepted = privacy_notice_accepted
    consent.attribution_preference = attribution_preference  # type: ignore[assignment]
    consent.attribution_text = attribution_text
    project.updated_at = _now()
    db.commit()
    db.refresh(consent)
    return consent


def _missing_submission_requirements(project: CrochetProject) -> list[str]:
    missing: list[str] = []
    consent = project.consent
    if consent is None or not consent.privacy_notice_accepted:
        missing.append("acceptance of the privacy notice")
    if consent is None or not consent.owns_photographs:
        missing.append("confirmation that you own or control the photographs")

    required_types = _REQUIRED_IMAGE_TYPES_BY_CATEGORY.get(
        project.project_category.value, frozenset()
    )
    present_types = {image.image_type.value for image in project.images}
    for required in sorted(required_types - present_types):
        missing.append(f"a {required.replace('_', ' ')} photo")

    return missing


def missing_submission_requirements(project: CrochetProject) -> list[str]:
    """Public wrapper so pages (e.g. the review step) can show a contributor
    what's still needed before they can submit."""
    return _missing_submission_requirements(project)


def submit_project(db: Session, project: CrochetProject) -> CrochetProject:
    missing = _missing_submission_requirements(project)
    if missing:
        raise SubmissionValidationError(missing)

    assert_valid_transition(project.status, ProjectStatus.SUBMITTED)
    project.status = ProjectStatus.SUBMITTED
    project.submitted_at = _now()
    project.updated_at = _now()
    db.commit()
    log_audit(db, actor="contributor", event_type="project_submitted", project=project)
    return project


# --- Images ----------------------------------------------------------------


def add_project_image(
    db: Session,
    storage: StorageBackend,
    project: CrochetProject,
    *,
    image_type: str,
    raw_bytes: bytes,
    original_filename: str,
    max_upload_bytes: int,
    min_image_dimension_px: int,
    max_images_per_project: int,
) -> ProjectImage:
    _assert_editable(project)
    if len(project.images) >= max_images_per_project:
        raise ImageLimitExceededError(
            f"this project already has the maximum of {max_images_per_project} images"
        )

    processed: ProcessedImage = _validate_image(
        raw_bytes, max_upload_bytes=max_upload_bytes, min_dimension_px=min_image_dimension_px
    )

    duplicate = db.scalar(
        select(ProjectImage)
        .where(ProjectImage.sha256 == processed.sha256)
        .order_by(ProjectImage.id)
    )

    storage.save_original(
        project.submission_reference, processed.stored_filename, processed.original_bytes
    )
    storage.save_preview(
        project.submission_reference, processed.stored_filename, processed.preview_bytes
    )

    image = ProjectImage(
        image_type=image_type,
        original_filename=sanitize_original_filename(original_filename),
        stored_filename=processed.stored_filename,
        width=processed.width,
        height=processed.height,
        image_format=processed.image_format,
        byte_size=processed.byte_size,
        sha256=processed.sha256,
        duplicate_of_image_id=duplicate.id if duplicate else None,
        exif_stripped=True,
        created_at=_now(),
    )
    # Relationship append (not a raw project_id FK) keeps project.images
    # correct in-memory for any later call sharing this session — see the
    # equivalent note in upsert_project_metadata.
    project.images.append(image)
    project.updated_at = _now()
    db.commit()
    db.refresh(image)

    log_audit(
        db,
        actor="contributor",
        event_type="image_uploaded",
        project=project,
        detail=(
            f"type={image_type} format={processed.image_format} "
            f"{processed.width}x{processed.height} bytes={processed.byte_size} "
            f"duplicate_of={image.duplicate_of_image_id}"
        ),
    )
    return image


# --- Admin review ------------------------------------------------------


def admin_start_review(db: Session, project: CrochetProject, admin_actor: str) -> CrochetProject:
    assert_valid_transition(project.status, ProjectStatus.UNDER_REVIEW)
    project.status = ProjectStatus.UNDER_REVIEW
    project.updated_at = _now()
    db.commit()
    log_audit(db, actor=admin_actor, event_type="review_started", project=project)
    return project


@dataclass(frozen=True, slots=True)
class ReviewDecisionInput:
    decision: ReviewDecisionType
    reason: str | None = None
    verified_craft_type: str | None = None
    verified_project_category: str | None = None
    verified_stitch_labels: list[str] | None = None
    data_quality_status: str | None = None
    exclusion_reason: str | None = None


_DECISION_TARGET_STATUS = {
    ReviewDecisionType.APPROVE: ProjectStatus.APPROVED,
    ReviewDecisionType.REJECT: ProjectStatus.REJECTED,
    ReviewDecisionType.CHANGES_REQUESTED: ProjectStatus.CHANGES_REQUESTED,
}


def record_review_decision(
    db: Session,
    project: CrochetProject,
    admin_id: int,
    admin_actor: str,
    decision_input: ReviewDecisionInput,
) -> ReviewDecision:
    target_status = _DECISION_TARGET_STATUS.get(decision_input.decision)
    if target_status is not None:
        assert_valid_transition(project.status, target_status)

    allowed_uses = None
    if decision_input.decision is ReviewDecisionType.APPROVE and project.consent is not None:
        consent = project.consent
        allowed_uses = {
            "research_evaluation_use": consent.research_evaluation_use,
            "product_development_use": consent.product_development_use,
            "model_training_use": consent.model_training_use,
            "public_demonstration_use": consent.public_demonstration_use,
        }

    decision = ReviewDecision(
        project_id=project.id,
        admin_id=admin_id,
        decision=decision_input.decision,
        reason=decision_input.reason,
        verified_craft_type=decision_input.verified_craft_type,
        verified_project_category=decision_input.verified_project_category,
        verified_stitch_labels=decision_input.verified_stitch_labels,
        allowed_uses=allowed_uses,
        data_quality_status=decision_input.data_quality_status,
        exclusion_reason=decision_input.exclusion_reason,
        created_at=_now(),
    )
    db.add(decision)

    if target_status is not None:
        project.status = target_status
    project.updated_at = _now()
    db.commit()

    log_audit(
        db,
        actor=admin_actor,
        event_type=f"review_decision_{decision_input.decision.value}",
        project=project,
        detail=decision_input.reason,
    )
    db.refresh(decision)
    return decision


# --- Physical-trial linking ----------------------------------------------


def link_physical_trial(
    db: Session,
    project: CrochetProject,
    *,
    trial_id: str,
    pattern_fingerprint: str,
    physical_result_id: str | None,
    admin_actor: str,
) -> PhysicalTrialLink:
    trial = next((t for t in TRIAL_MATRIX if t.trial_id == trial_id), None)
    if trial is None:
        raise TrialLinkValidationError(f"unknown trial_id {trial_id!r}")

    pattern = compile_trial(trial)
    validated = pattern.fingerprint == pattern_fingerprint
    if not validated:
        raise TrialLinkValidationError(
            f"pattern_fingerprint does not match the current fingerprint for {trial_id!r}"
        )

    link = PhysicalTrialLink(
        trial_id=trial_id,
        pattern_fingerprint=pattern_fingerprint,
        physical_result_id=physical_result_id,
        validated=validated,
        created_at=_now(),
    )
    project.trial_links.append(link)
    db.commit()
    db.refresh(link)
    log_audit(
        db,
        actor=admin_actor,
        event_type="trial_linked",
        project=project,
        detail=f"trial_id={trial_id}",
    )
    return link


# --- Withdrawal and deletion ---------------------------------------------


def withdraw_project(
    db: Session, project: CrochetProject, *, actor: str, reason: str | None
) -> CrochetProject:
    if not is_withdrawable(project.status):
        raise ProjectNotEditableError("project is already withdrawn")

    project.status = ProjectStatus.WITHDRAWN
    project.updated_at = _now()
    if project.consent is not None:
        project.consent.withdrawn_at = _now()
    db.commit()
    log_audit(db, actor=actor, event_type="project_withdrawn", project=project, detail=reason)
    return project


def delete_project_data(
    db: Session, storage: StorageBackend, project: CrochetProject, *, actor: str
) -> None:
    """Hard-deletes images and contributor-identifying text, retaining only
    a minimal tombstone (submission_reference, status, audit trail) so the
    audit log can still show that a deletion occurred."""
    storage.delete_project_files(project.submission_reference)

    image_count = len(project.images)
    for image in list(project.images):
        db.delete(image)
    # Deleting via db.delete() does not retroactively update the
    # already-loaded project.images collection in this session (same class
    # of staleness as the append fix above, in reverse) - clear it
    # explicitly so callers in this session see an accurate empty list.
    project.images.clear()

    project.name_or_description = None
    project.component_notes = None
    project.free_text_notes = None
    if project.metadata_ is not None:
        db.delete(project.metadata_)
    if project.consent is not None:
        project.consent.withdrawn_at = project.consent.withdrawn_at or _now()
        project.consent.attribution_text = None

    project.status = ProjectStatus.WITHDRAWN
    project.updated_at = _now()
    db.commit()
    log_audit(
        db,
        actor=actor,
        event_type="project_data_deleted",
        project=project,
        detail=f"deleted {image_count} image(s) and free-text fields",
    )


# --- Dataset export --------------------------------------------------------


def _latest_approval_decision(project: CrochetProject) -> ReviewDecision | None:
    approvals = [d for d in project.review_decisions if d.decision is ReviewDecisionType.APPROVE]
    return max(approvals, key=lambda d: d.created_at) if approvals else None


def export_approved_projects(
    db: Session, storage: StorageBackend, output_dir: Path
) -> dict[str, Any]:
    """Writes an approved-dataset index (JSON) plus preview-image copies to
    ``output_dir``. Only ``status == APPROVED`` and non-withdrawn projects
    are included — a withdrawn project is excluded automatically because
    withdrawal always changes status away from APPROVED.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"

    projects = db.scalars(
        select(CrochetProject).where(CrochetProject.status == ProjectStatus.APPROVED)
    ).all()

    records: list[dict[str, Any]] = []
    for project in projects:
        consent = project.consent
        if consent is None or consent.withdrawn_at is not None:
            continue
        if not (consent.research_evaluation_use or consent.product_development_use):
            continue

        approval = _latest_approval_decision(project)
        project_image_dir = images_dir / project.submission_reference
        project_image_dir.mkdir(parents=True, exist_ok=True)

        image_records = []
        for image in project.images:
            preview_bytes = storage.read_preview(
                project.submission_reference, image.stored_filename
            )
            preview_name = f"{image.image_type.value}_{image.stored_filename.rsplit('.', 1)[0]}.jpg"
            (project_image_dir / preview_name).write_bytes(preview_bytes)
            image_records.append(
                {
                    "image_type": image.image_type.value,
                    "preview_filename": preview_name,
                    "width": image.width,
                    "height": image.height,
                    "format": image.image_format,
                    "sha256": image.sha256,
                    "is_duplicate": image.duplicate_of_image_id is not None,
                }
            )

        records.append(
            {
                "object_id": project.submission_reference,
                "craft_type": (
                    approval.verified_craft_type.value
                    if approval and approval.verified_craft_type
                    else project.craft_type.value
                ),
                "project_category": (
                    approval.verified_project_category.value
                    if approval and approval.verified_project_category
                    else project.project_category.value
                ),
                "verified_stitch_labels": approval.verified_stitch_labels if approval else None,
                "allowed_uses": approval.allowed_uses if approval else None,
                "data_quality_status": approval.data_quality_status.value
                if approval and approval.data_quality_status
                else None,
                "consent_version": consent.consent_version,
                "attribution_preference": consent.attribution_preference.value,
                "attribution_text": consent.attribution_text,
                "split": None,
                "images": image_records,
                "trial_links": [
                    {
                        "trial_id": link.trial_id,
                        "pattern_fingerprint": link.pattern_fingerprint,
                        "physical_result_id": link.physical_result_id,
                        "validated": link.validated,
                    }
                    for link in project.trial_links
                ],
            }
        )

    index_path = output_dir / "approved_dataset.json"
    index_path.write_text(
        json.dumps({"records": records}, indent=2, sort_keys=True), encoding="utf-8"
    )

    log_audit(db, actor="admin", event_type="dataset_exported", detail=f"{len(records)} project(s)")
    return {"output_dir": str(output_dir), "project_count": len(records)}
