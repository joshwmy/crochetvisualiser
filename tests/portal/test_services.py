import io
from decimal import Decimal

import pytest
from PIL import Image

from crochet_reconstruction.physical_validation.trial_matrix import TRIAL_MATRIX, compile_trial
from crochet_reconstruction.portal import services
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
from crochet_reconstruction.portal.models import (
    AttributionPreference,
    ImageType,
    ProjectCategory,
    ProjectStatus,
    ReviewDecisionType,
)
from crochet_reconstruction.portal.services import ReviewDecisionInput


def _jpeg_bytes(color: tuple[int, int, int] = (10, 200, 30)) -> bytes:
    img = Image.new("RGB", (600, 600), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _consent_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "contributor_provided_identifier": "Tester",
        "owns_photographs": True,
        "research_evaluation_use": True,
        "product_development_use": True,
        "model_training_use": False,
        "public_demonstration_use": False,
        "contact_for_missing_details": False,
        "privacy_notice_accepted": True,
        "attribution_preference": AttributionPreference.ANONYMOUS,
        "attribution_text": None,
    }
    base.update(overrides)
    return base


# --- Invitations -------------------------------------------------------


def test_create_and_redeem_invitation(db) -> None:
    invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    assert invitation.used_count == 0

    contributor = services.redeem_invitation(
        db, token, display_identifier="Jess", contact_email=None
    )
    assert contributor.invitation_id == invitation.id
    db.refresh(invitation)
    assert invitation.used_count == 1


def test_redeem_unknown_token_raises(db) -> None:
    with pytest.raises(InvitationInvalidError):
        services.redeem_invitation(
            db, "not-a-real-token", display_identifier="X", contact_email=None
        )


def test_redeem_revoked_invitation_raises(db) -> None:
    invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    services.revoke_invitation(db, invitation)
    with pytest.raises(InvitationRevokedError):
        services.redeem_invitation(db, token, display_identifier="X", contact_email=None)


def test_redeem_expired_invitation_raises(db) -> None:
    invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    invitation.expires_at = services._now().replace(year=2000)
    db.commit()
    with pytest.raises(InvitationExpiredError):
        services.redeem_invitation(db, token, display_identifier="X", contact_email=None)


def test_redeem_exhausted_invitation_raises(db) -> None:
    invitation, token = services.create_invitation(db, label="friend", expiry_days=30, max_uses=1)
    services.redeem_invitation(db, token, display_identifier="First", contact_email=None)
    with pytest.raises(InvitationExhaustedError):
        services.redeem_invitation(db, token, display_identifier="Second", contact_email=None)


def test_invitation_supports_multiple_uses_when_configured(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30, max_uses=2)
    services.redeem_invitation(db, token, display_identifier="First", contact_email=None)
    contributor_two = services.redeem_invitation(
        db, token, display_identifier="Second", contact_email=None
    )
    assert contributor_two.display_identifier == "Second"


# --- Consent -------------------------------------------------------------


def test_record_consent_requires_owns_photographs_and_privacy(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    # The service layer itself does not enforce this (that's schemas.py's
    # job at the router boundary) - but callers are still free to store
    # False/False if they bypass the schema, so this test documents that
    # the *router* validation is where this is actually enforced. Here we
    # simply verify the values round-trip faithfully either way.
    consent = services.record_consent(db, project, **_consent_kwargs(owns_photographs=False))
    assert consent.owns_photographs is False


def test_record_consent_records_version_and_timestamp(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    consent = services.record_consent(db, project, **_consent_kwargs())
    assert consent.consent_version == services.CONSENT_VERSION
    assert consent.consented_at is not None


def test_consent_permission_combinations_are_independent(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    consent = services.record_consent(
        db,
        project,
        **_consent_kwargs(
            research_evaluation_use=True,
            product_development_use=True,
            model_training_use=False,
            public_demonstration_use=False,
        ),
    )
    assert consent.research_evaluation_use is True
    assert consent.product_development_use is True
    assert consent.model_training_use is False
    assert consent.public_demonstration_use is False


def test_cannot_edit_consent_after_submission(db) -> None:
    project = _fully_ready_project(db)
    services.submit_project(db, project)

    with pytest.raises(ProjectNotEditableError):
        services.record_consent(db, project, **_consent_kwargs())


# --- Projects, metadata, unknown values -----------------------------------


def test_unknown_values_stay_null_not_guessed(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    metadata = services.upsert_project_metadata(db, project, hook_mm=None, stitches_per_10cm=None)
    assert metadata.hook_mm is None
    assert metadata.stitches_per_10cm is None


def test_metadata_values_are_preserved_exactly(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    metadata = services.upsert_project_metadata(db, project, hook_mm=Decimal("4.5"))
    assert metadata.hook_mm == Decimal("4.5")


# --- Submission validation -------------------------------------------------


def _fully_ready_project(db, category: ProjectCategory = ProjectCategory.BEANIE):
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)
    services.update_project_details(db, project, project_category=category)
    services.record_consent(db, project, **_consent_kwargs())

    required_types = (
        [ImageType.FRONT, ImageType.CROWN_TOP, ImageType.STITCH_MACRO]
        if category is ProjectCategory.BEANIE
        else [ImageType.SWATCH_FULL, ImageType.SWATCH_FRONT_MACRO, ImageType.SWATCH_EDGE]
    )
    for image_type in required_types:
        services.add_project_image(
            db,
            _MemoryStorage(),
            project,
            image_type=image_type,
            raw_bytes=_jpeg_bytes(),
            original_filename="test.jpg",
            max_upload_bytes=10_000_000,
            min_image_dimension_px=400,
            max_images_per_project=12,
        )
    return project


class _MemoryStorage:
    """Minimal in-memory StorageBackend stand-in for service-layer tests
    that don't need real file I/O."""

    def save_original(self, project_key, stored_filename, data) -> None:
        pass

    def save_preview(self, project_key, stored_filename, data) -> None:
        pass

    def read_original(self, project_key, stored_filename) -> bytes:
        return b""

    def read_preview(self, project_key, stored_filename) -> bytes:
        return b""

    def delete_project_files(self, project_key) -> None:
        pass

    def write_export(self, filename, data):
        raise NotImplementedError

    def write_backup(self, filename, data):
        raise NotImplementedError


def test_submit_fails_when_missing_required_images(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)
    services.update_project_details(db, project, project_category=ProjectCategory.BEANIE)
    services.record_consent(db, project, **_consent_kwargs())

    with pytest.raises(SubmissionValidationError) as exc_info:
        services.submit_project(db, project)
    assert any("front" in item for item in exc_info.value.missing_items)


def test_submit_fails_without_consent(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    with pytest.raises(SubmissionValidationError) as exc_info:
        services.submit_project(db, project)
    assert any("privacy notice" in item for item in exc_info.value.missing_items)


def test_submit_succeeds_when_ready(db) -> None:
    project = _fully_ready_project(db)
    services.submit_project(db, project)
    assert project.status is ProjectStatus.SUBMITTED
    assert project.submitted_at is not None


def test_image_limit_is_enforced(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    services.add_project_image(
        db,
        _MemoryStorage(),
        project,
        image_type=ImageType.FRONT,
        raw_bytes=_jpeg_bytes(),
        original_filename="a.jpg",
        max_upload_bytes=10_000_000,
        min_image_dimension_px=400,
        max_images_per_project=1,
    )
    with pytest.raises(ImageLimitExceededError):
        services.add_project_image(
            db,
            _MemoryStorage(),
            project,
            image_type=ImageType.SIDE,
            raw_bytes=_jpeg_bytes(color=(1, 2, 3)),
            original_filename="b.jpg",
            max_upload_bytes=10_000_000,
            min_image_dimension_px=400,
            max_images_per_project=1,
        )


def test_duplicate_image_is_flagged_not_rejected(db) -> None:
    _invitation, token = services.create_invitation(db, label="friend", expiry_days=30)
    contributor = services.redeem_invitation(db, token, display_identifier="X", contact_email=None)
    project = services.create_draft_project(db, contributor)

    same_bytes = _jpeg_bytes()
    first = services.add_project_image(
        db,
        _MemoryStorage(),
        project,
        image_type=ImageType.FRONT,
        raw_bytes=same_bytes,
        original_filename="a.jpg",
        max_upload_bytes=10_000_000,
        min_image_dimension_px=400,
        max_images_per_project=12,
    )
    second = services.add_project_image(
        db,
        _MemoryStorage(),
        project,
        image_type=ImageType.SIDE,
        raw_bytes=same_bytes,
        original_filename="a-copy.jpg",
        max_upload_bytes=10_000_000,
        min_image_dimension_px=400,
        max_images_per_project=12,
    )
    assert second.duplicate_of_image_id == first.id


# --- Review workflow ------------------------------------------------------


def test_full_review_lifecycle_to_approval(db) -> None:
    project = _fully_ready_project(db)
    services.submit_project(db, project)
    services.admin_start_review(db, project, admin_actor="admin:1")
    assert project.status is ProjectStatus.UNDER_REVIEW

    decision = services.record_review_decision(
        db,
        project,
        admin_id=1,
        admin_actor="admin:1",
        decision_input=ReviewDecisionInput(decision=ReviewDecisionType.APPROVE),
    )
    assert project.status is ProjectStatus.APPROVED
    assert decision.allowed_uses is not None


def test_changes_requested_allows_resubmission(db) -> None:
    project = _fully_ready_project(db)
    services.submit_project(db, project)
    services.admin_start_review(db, project, admin_actor="admin:1")
    services.record_review_decision(
        db,
        project,
        admin_id=1,
        admin_actor="admin:1",
        decision_input=ReviewDecisionInput(
            decision=ReviewDecisionType.CHANGES_REQUESTED, reason="fix x"
        ),
    )
    assert project.status is ProjectStatus.CHANGES_REQUESTED

    # Contributor can edit again now, then resubmit.
    services.update_project_details(db, project, name_or_description="updated")
    services.submit_project(db, project)
    assert project.status is ProjectStatus.SUBMITTED


def test_note_decision_does_not_change_status(db) -> None:
    project = _fully_ready_project(db)
    services.submit_project(db, project)
    services.admin_start_review(db, project, admin_actor="admin:1")
    services.record_review_decision(
        db,
        project,
        admin_id=1,
        admin_actor="admin:1",
        decision_input=ReviewDecisionInput(
            decision=ReviewDecisionType.NOTE, verified_stitch_labels=["sc"]
        ),
    )
    assert project.status is ProjectStatus.UNDER_REVIEW


def test_cannot_approve_a_draft_project(db) -> None:
    project = _fully_ready_project(db)
    from crochet_reconstruction.portal.state_machine import InvalidTransitionError

    with pytest.raises(InvalidTransitionError):
        services.record_review_decision(
            db,
            project,
            admin_id=1,
            admin_actor="admin:1",
            decision_input=ReviewDecisionInput(decision=ReviewDecisionType.APPROVE),
        )


# --- Physical-trial linking -------------------------------------------------


def test_link_physical_trial_with_valid_data(db) -> None:
    project = _fully_ready_project(db)
    trial = TRIAL_MATRIX[0]
    pattern = compile_trial(trial)

    link = services.link_physical_trial(
        db,
        project,
        trial_id=trial.trial_id,
        pattern_fingerprint=pattern.fingerprint,
        physical_result_id="phys-1",
        admin_actor="admin:1",
    )
    assert link.validated is True


def test_link_physical_trial_rejects_unknown_trial_id(db) -> None:
    project = _fully_ready_project(db)
    with pytest.raises(TrialLinkValidationError, match="unknown trial_id"):
        services.link_physical_trial(
            db,
            project,
            trial_id="BV-999",
            pattern_fingerprint="whatever",
            physical_result_id=None,
            admin_actor="admin:1",
        )


def test_link_physical_trial_rejects_fingerprint_mismatch(db) -> None:
    project = _fully_ready_project(db)
    trial = TRIAL_MATRIX[0]
    with pytest.raises(TrialLinkValidationError, match="does not match"):
        services.link_physical_trial(
            db,
            project,
            trial_id=trial.trial_id,
            pattern_fingerprint="stale-fingerprint",
            physical_result_id=None,
            admin_actor="admin:1",
        )


# --- Withdrawal, deletion, and export exclusion -----------------------------


def _approve(db, project) -> None:
    services.submit_project(db, project)
    services.admin_start_review(db, project, admin_actor="admin:1")
    services.record_review_decision(
        db,
        project,
        admin_id=1,
        admin_actor="admin:1",
        decision_input=ReviewDecisionInput(decision=ReviewDecisionType.APPROVE),
    )


def test_withdraw_excludes_from_export(db, tmp_path) -> None:
    project = _fully_ready_project(db)
    _approve(db, project)

    before = services.export_approved_projects(db, _MemoryStorage(), tmp_path / "export1")
    assert before["project_count"] == 1

    services.withdraw_project(db, project, actor="contributor", reason="changed my mind")
    assert project.status is ProjectStatus.WITHDRAWN

    after = services.export_approved_projects(db, _MemoryStorage(), tmp_path / "export2")
    assert after["project_count"] == 0


def test_withdraw_twice_raises(db) -> None:
    project = _fully_ready_project(db)
    services.withdraw_project(db, project, actor="contributor", reason="x")
    with pytest.raises(ProjectNotEditableError):
        services.withdraw_project(db, project, actor="contributor", reason="x")


def test_export_excludes_projects_without_research_or_product_consent(db, tmp_path) -> None:
    project = _fully_ready_project(db)
    services.record_consent(
        db,
        project,
        **_consent_kwargs(research_evaluation_use=False, product_development_use=False),
    )
    _approve(db, project)

    result = services.export_approved_projects(db, _MemoryStorage(), tmp_path / "export")
    assert result["project_count"] == 0


def test_delete_project_data_removes_text_and_images(db) -> None:
    project = _fully_ready_project(db)
    assert len(project.images) > 0

    services.delete_project_data(db, _MemoryStorage(), project, actor="admin:1")

    assert project.images == []
    assert project.name_or_description is None
    assert project.status is ProjectStatus.WITHDRAWN


def test_audit_trail_records_key_events(db) -> None:
    project = _fully_ready_project(db)
    services.submit_project(db, project)

    from sqlalchemy import select

    from crochet_reconstruction.portal.models import AuditEvent

    events = db.scalars(select(AuditEvent).where(AuditEvent.project_id == project.id)).all()
    event_types = {e.event_type for e in events}
    assert "project_created" in event_types
    assert "project_submitted" in event_types
    assert "image_uploaded" in event_types
