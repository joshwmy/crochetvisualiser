"""Shared fixtures for portal tests.

Every test gets its own temp DATA_DIR and SQLite database — nothing here
touches a developer's real ``portal_data/``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crochet_reconstruction.portal import db as db_module
from crochet_reconstruction.portal.config import Settings, reset_settings_cache
from crochet_reconstruction.portal.dependencies import reset_rate_limiters
from crochet_reconstruction.portal.models import AdminUser
from crochet_reconstruction.portal.security import hash_password
from crochet_reconstruction.portal.services import create_invitation
from crochet_reconstruction.portal.storage import LocalFileStorage, StorageBackend


@pytest.fixture
def portal_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="development",
        secret_key="test-secret-key-not-for-production",
        data_dir=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'portal.db'}",
        max_upload_bytes=10_000_000,
        max_images_per_project=12,
        min_image_dimension_px=400,
        invitation_default_expiry_days=30,
        session_cookie_name="portal_session",
        session_max_age_seconds=3600,
        rate_limit_max_attempts=5,
        rate_limit_window_seconds=60,
        contact_email_collection_enabled=True,
    )


@pytest.fixture
def storage(portal_settings: Settings) -> StorageBackend:
    portal_settings.ensure_data_directories()
    return LocalFileStorage(
        portal_settings.originals_dir,
        portal_settings.previews_dir,
        portal_settings.exports_dir,
        portal_settings.backups_dir,
    )


@pytest.fixture
def session_factory(portal_settings: Settings) -> Iterator[sessionmaker[Session]]:
    from crochet_reconstruction.portal.db import Base, create_engine_for_settings

    portal_settings.ensure_data_directories()
    engine = create_engine_for_settings(portal_settings)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def admin_user(db: Session) -> AdminUser:
    admin = AdminUser(
        username="admin",
        password_hash=hash_password("correct-horse-battery-staple"),
        is_active=True,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def invitation_token(db: Session) -> str:
    _invitation, token = create_invitation(db, label="test invitation", expiry_days=30, max_uses=1)
    return token


@pytest.fixture
def app_client(
    portal_settings: Settings,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """A TestClient wired to the same temp DB/settings as the other fixtures."""
    reset_settings_cache()
    reset_rate_limiters()
    monkeypatch.setattr(db_module, "_engine", session_factory.kw["bind"])
    monkeypatch.setattr(db_module, "_session_factory", session_factory)

    from crochet_reconstruction.portal.app import create_app

    app = create_app(settings=portal_settings)
    with TestClient(app, follow_redirects=True) as client:
        yield client

    reset_settings_cache()
    reset_rate_limiters()


def extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "no csrf_token field found in page"
    return match.group(1)
