"""Portal configuration, read entirely from environment variables.

No secret has a real default. In development, missing secrets are
generated in-process (with a loud warning) so `uvicorn` can start without
ceremony; in production (`PORTAL_ENVIRONMENT=production`) a missing
required variable raises immediately at startup rather than silently
running insecurely.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


class ConfigurationError(RuntimeError):
    """Raised when required production configuration is missing or unusable."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    secret_key: str
    data_dir: Path
    database_url: str

    max_upload_bytes: int
    max_images_per_project: int
    min_image_dimension_px: int
    invitation_default_expiry_days: int

    session_cookie_name: str
    session_max_age_seconds: int

    rate_limit_max_attempts: int
    rate_limit_window_seconds: int

    contact_email_collection_enabled: bool

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def originals_dir(self) -> Path:
        return self.data_dir / "originals"

    @property
    def previews_dir(self) -> Path:
        return self.data_dir / "previews"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def quarantine_dir(self) -> Path:
        return self.data_dir / "quarantine"

    def ensure_data_directories(self) -> None:
        """Create the data directory tree, failing loudly if not writable."""
        for directory in (
            self.data_dir,
            self.originals_dir,
            self.previews_dir,
            self.exports_dir,
            self.backups_dir,
            self.quarantine_dir,
        ):
            try:
                directory.mkdir(parents=True, exist_ok=True)
                probe = directory / ".write_test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
            except OSError as exc:
                raise ConfigurationError(
                    f"data directory {directory} is not writable: {exc}. "
                    f"Mount a persistent, writable volume at PORTAL_DATA_DIR "
                    f"before starting the portal."
                ) from exc


_WARNED_DEV_SECRET = False


def load_settings() -> Settings:
    environment = os.environ.get("PORTAL_ENVIRONMENT", "development").strip().lower()
    is_production = environment == "production"

    secret_key = os.environ.get("PORTAL_SECRET_KEY")
    if not secret_key:
        if is_production:
            raise ConfigurationError(
                "PORTAL_SECRET_KEY is required when PORTAL_ENVIRONMENT=production. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        global _WARNED_DEV_SECRET
        secret_key = secrets.token_urlsafe(32)
        if not _WARNED_DEV_SECRET:
            print(  # noqa: T201 - intentional startup warning, not a debug leftover
                "WARNING: PORTAL_SECRET_KEY not set; using an ephemeral development "
                "key. Admin sessions will not survive a restart. Never do this in "
                "production."
            )
            _WARNED_DEV_SECRET = True

    data_dir = Path(os.environ.get("PORTAL_DATA_DIR", "./portal_data")).resolve()

    database_url = os.environ.get("PORTAL_DATABASE_URL")
    if not database_url:
        database_url = f"sqlite:///{data_dir / 'portal.db'}"

    if is_production and database_url.startswith("sqlite://") and "memory" in database_url:
        raise ConfigurationError("in-memory SQLite is not valid in production")

    return Settings(
        environment=environment,
        secret_key=secret_key,
        data_dir=data_dir,
        database_url=database_url,
        max_upload_bytes=_env_int("PORTAL_MAX_UPLOAD_BYTES", 15 * 1024 * 1024),
        max_images_per_project=_env_int("PORTAL_MAX_IMAGES_PER_PROJECT", 12),
        min_image_dimension_px=_env_int("PORTAL_MIN_IMAGE_DIMENSION_PX", 400),
        invitation_default_expiry_days=_env_int("PORTAL_INVITATION_EXPIRY_DAYS", 30),
        session_cookie_name=os.environ.get("PORTAL_SESSION_COOKIE_NAME", "portal_admin_session"),
        session_max_age_seconds=_env_int("PORTAL_SESSION_MAX_AGE_SECONDS", 8 * 60 * 60),
        rate_limit_max_attempts=_env_int("PORTAL_RATE_LIMIT_MAX_ATTEMPTS", 10),
        rate_limit_window_seconds=_env_int("PORTAL_RATE_LIMIT_WINDOW_SECONDS", 60),
        contact_email_collection_enabled=_env_bool("PORTAL_CONTACT_EMAIL_COLLECTION_ENABLED", True),
    )


@dataclass
class _SettingsCache:
    value: Settings | None = field(default=None)


_cache = _SettingsCache()


def get_settings() -> Settings:
    """Cached settings accessor. Call ``reset_settings_cache()`` in tests."""
    if _cache.value is None:
        _cache.value = load_settings()
    return _cache.value


def set_settings_cache(settings: Settings) -> None:
    """Pin the process-wide settings singleton to an explicit instance.

    Every dependency provider (`get_storage`, the rate limiters, `db.py`)
    reads settings via `get_settings()`, not via whatever was passed to
    `create_app()` — so a caller that constructs its own `Settings` (tests,
    or an embedding application) must call this to make the whole app
    consistent, or every other component silently falls back to
    environment-derived settings instead of the instance actually intended.
    """
    _cache.value = settings


def reset_settings_cache() -> None:
    _cache.value = None
