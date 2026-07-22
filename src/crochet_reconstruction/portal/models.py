"""SQLAlchemy ORM models for the contributor portal.

Design rules (see docs/portal-architecture.md for the full rationale):

- Contributor-provided data is never overwritten by review. Reviewer
  judgements live only on ``ReviewDecision`` rows.
- ``ProjectImage`` never stores a raw filesystem path — only a UUID
  filename that ``storage.py`` resolves against the configured data
  directory.
- ``AuditEvent.detail`` must never contain uploaded image content.
- Consent is per-project (``ConsentRecord`` is 1:1 with ``CrochetProject``),
  not a single blanket flag — each permission is its own column.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crochet_reconstruction.portal.db import Base


class ProjectStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    APPROVED = "approved"
    WITHDRAWN = "withdrawn"


class CraftType(enum.StrEnum):
    CROCHET = "crochet"
    KNITTING = "knitting"
    UNKNOWN = "unknown"


class ProjectCategory(enum.StrEnum):
    BEANIE = "beanie"
    STITCH_SWATCH = "stitch_swatch"
    OTHER = "other"


class TriState(enum.StrEnum):
    """A yes/no/unknown answer. 'unknown' is a real, storable value —
    contributors must never be forced to guess (see project brief)."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class ConstructionDirection(enum.StrEnum):
    TOP_DOWN = "top_down"
    BOTTOM_UP = "bottom_up"
    UNKNOWN = "unknown"


class WorkedIn(enum.StrEnum):
    ROWS = "rows"
    ROUNDS = "rounds"
    UNKNOWN = "unknown"


class RoundStyle(enum.StrEnum):
    CONTINUOUS = "continuous"
    JOINED = "joined"
    UNKNOWN = "unknown"


class GaugeBlockingState(enum.StrEnum):
    BEFORE_BLOCKING = "before_blocking"
    AFTER_BLOCKING = "after_blocking"
    UNKNOWN = "unknown"


class AttributionPreference(enum.StrEnum):
    FULL_NAME = "full_name"
    HANDLE_OR_FIRST_NAME = "handle_or_first_name"
    ANONYMOUS = "anonymous"


class ImageType(enum.StrEnum):
    FRONT = "front"
    CROWN_TOP = "crown_top"
    STITCH_MACRO = "stitch_macro"
    SIDE = "side"
    INTERIOR = "interior"
    BRIM = "brim"
    SEAM_JOIN = "seam_join"
    SCALE_REFERENCE = "scale_reference"
    SWATCH_FULL = "swatch_full"
    SWATCH_FRONT_MACRO = "swatch_front_macro"
    SWATCH_EDGE = "swatch_edge"
    OTHER = "other"


class ReviewDecisionType(enum.StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    CHANGES_REQUESTED = "changes_requested"
    NOTE = "note"
    """Records verified labels / trial-link notes without changing status."""


class DataQualityStatus(enum.StrEnum):
    OK = "ok"
    NEEDS_REVIEW = "needs_review"
    EXCLUDED = "excluded"


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(200))
    max_uses: Mapped[int] = mapped_column(default=1)
    used_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    contributors: Mapped[list[Contributor]] = relationship(back_populates="invitation")


class Contributor(Base):
    __tablename__ = "contributors"

    id: Mapped[int] = mapped_column(primary_key=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey("invitations.id"))
    display_identifier: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    invitation: Mapped[Invitation] = relationship(back_populates="contributors")
    projects: Mapped[list[CrochetProject]] = relationship(back_populates="contributor")


class CrochetProject(Base):
    __tablename__ = "crochet_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    contributor_id: Mapped[int] = mapped_column(ForeignKey("contributors.id"))
    submission_reference: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, native_enum=False, length=30), default=ProjectStatus.DRAFT, index=True
    )

    name_or_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    craft_type: Mapped[CraftType] = mapped_column(
        SAEnum(CraftType, native_enum=False, length=20), default=CraftType.UNKNOWN
    )
    project_category: Mapped[ProjectCategory] = mapped_column(
        SAEnum(ProjectCategory, native_enum=False, length=30), default=ProjectCategory.OTHER
    )
    made_by_contributor: Mapped[TriState] = mapped_column(
        SAEnum(TriState, native_enum=False, length=10), default=TriState.UNKNOWN
    )
    used_existing_pattern: Mapped[TriState] = mapped_column(
        SAEnum(TriState, native_enum=False, length=10), default=TriState.UNKNOWN
    )
    pattern_owned_by_contributor: Mapped[TriState] = mapped_column(
        SAEnum(TriState, native_enum=False, length=10), default=TriState.UNKNOWN
    )
    construction_direction: Mapped[ConstructionDirection] = mapped_column(
        SAEnum(ConstructionDirection, native_enum=False, length=20),
        default=ConstructionDirection.UNKNOWN,
    )
    worked_in: Mapped[WorkedIn] = mapped_column(
        SAEnum(WorkedIn, native_enum=False, length=10), default=WorkedIn.UNKNOWN
    )
    round_style: Mapped[RoundStyle] = mapped_column(
        SAEnum(RoundStyle, native_enum=False, length=10), default=RoundStyle.UNKNOWN
    )
    stitch_families: Mapped[list[str]] = mapped_column(JSON, default=list)
    component_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    free_text_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    contributor: Mapped[Contributor] = relationship(back_populates="projects")
    metadata_: Mapped[ProjectMetadata | None] = relationship(
        back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    consent: Mapped[ConsentRecord | None] = relationship(
        back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    images: Mapped[list[ProjectImage]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    trial_links: Mapped[list[PhysicalTrialLink]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    review_decisions: Mapped[list[ReviewDecision]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMetadata(Base):
    """Contributor-entered materials/gauge/measurements. All nullable —
    'unknown' means leaving the field null, never a guessed value."""

    __tablename__ = "project_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("crochet_projects.id"), unique=True)

    yarn_brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    yarn_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fibre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    yarn_weight: Mapped[str | None] = mapped_column(String(50), nullable=True)
    colour: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hook_mm: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    strands_held: Mapped[int | None] = mapped_column(nullable=True)
    substitutions_made: Mapped[bool | None] = mapped_column(nullable=True)
    materials_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    stitches_per_10cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    rounds_per_10cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    gauge_blocking_state: Mapped[GaugeBlockingState] = mapped_column(
        SAEnum(GaugeBlockingState, native_enum=False, length=20),
        default=GaugeBlockingState.UNKNOWN,
    )
    relaxed_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    stretched_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    total_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    crown_diameter_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    brim_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    swatch_flat_width_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    swatch_flat_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    measurement_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[CrochetProject] = relationship(back_populates="metadata_")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("crochet_projects.id"), unique=True)

    contributor_provided_identifier: Mapped[str] = mapped_column(String(200))
    consent_version: Mapped[str] = mapped_column(String(20))
    consented_at: Mapped[datetime] = mapped_column(DateTime)

    owns_photographs: Mapped[bool] = mapped_column()
    research_evaluation_use: Mapped[bool] = mapped_column(default=False)
    product_development_use: Mapped[bool] = mapped_column(default=False)
    model_training_use: Mapped[bool] = mapped_column(default=False)
    public_demonstration_use: Mapped[bool] = mapped_column(default=False)
    contact_for_missing_details: Mapped[bool] = mapped_column(default=False)
    privacy_notice_accepted: Mapped[bool] = mapped_column()
    attribution_preference: Mapped[AttributionPreference] = mapped_column(
        SAEnum(AttributionPreference, native_enum=False, length=30),
        default=AttributionPreference.ANONYMOUS,
    )
    attribution_text: Mapped[str | None] = mapped_column(String(200), nullable=True)

    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped[CrochetProject] = relationship(back_populates="consent")


class ProjectImage(Base):
    __tablename__ = "project_images"
    __table_args__ = (
        UniqueConstraint("stored_filename", name="uq_project_images_stored_filename"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("crochet_projects.id"))
    image_type: Mapped[ImageType] = mapped_column(SAEnum(ImageType, native_enum=False, length=30))

    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(80))
    width: Mapped[int] = mapped_column()
    height: Mapped[int] = mapped_column()
    image_format: Mapped[str] = mapped_column(String(10))
    byte_size: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    duplicate_of_image_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_images.id"), nullable=True
    )
    exif_stripped: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    project: Mapped[CrochetProject] = relationship(back_populates="images")


class PhysicalTrialLink(Base):
    __tablename__ = "physical_trial_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("crochet_projects.id"))
    trial_id: Mapped[str] = mapped_column(String(20))
    pattern_fingerprint: Mapped[str] = mapped_column(String(64))
    physical_result_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    project: Mapped[CrochetProject] = relationship(back_populates="trial_links")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("crochet_projects.id"))
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    decision: Mapped[ReviewDecisionType] = mapped_column(
        SAEnum(ReviewDecisionType, native_enum=False, length=20)
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified_craft_type: Mapped[CraftType | None] = mapped_column(
        SAEnum(CraftType, native_enum=False, length=20), nullable=True
    )
    verified_project_category: Mapped[ProjectCategory | None] = mapped_column(
        SAEnum(ProjectCategory, native_enum=False, length=30), nullable=True
    )
    verified_stitch_labels: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    allowed_uses: Mapped[dict[str, bool] | None] = mapped_column(JSON, nullable=True)
    data_quality_status: Mapped[DataQualityStatus | None] = mapped_column(
        SAEnum(DataQualityStatus, native_enum=False, length=20), nullable=True
    )
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime)

    project: Mapped[CrochetProject] = relationship(back_populates="review_decisions")


class AuditEvent(Base):
    """Never stores uploaded image content — text metadata only."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("crochet_projects.id"), nullable=True)
    contributor_id: Mapped[int | None] = mapped_column(ForeignKey("contributors.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
