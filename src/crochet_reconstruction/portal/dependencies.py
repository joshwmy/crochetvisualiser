"""FastAPI dependency providers shared by both routers.

`Depends(get_settings)` is deliberately avoided (ruff B008 / FastAPI's own
recommendation against calling `Depends()` in a default expression is fine
for FastAPI's own params, but chaining `Settings = Depends(get_settings)`
as an inner default triggers the linter and adds no real benefit here since
`get_settings()` is already cached at the module level) — these providers
just call it directly.
"""

from __future__ import annotations

from crochet_reconstruction.portal.config import get_settings
from crochet_reconstruction.portal.security import SlidingWindowRateLimiter
from crochet_reconstruction.portal.storage import LocalFileStorage, StorageBackend


def get_storage() -> StorageBackend:
    settings = get_settings()
    return LocalFileStorage(
        settings.originals_dir, settings.previews_dir, settings.exports_dir, settings.backups_dir
    )


_login_rate_limiter: SlidingWindowRateLimiter | None = None
_upload_rate_limiter: SlidingWindowRateLimiter | None = None


def get_login_rate_limiter() -> SlidingWindowRateLimiter:
    global _login_rate_limiter
    if _login_rate_limiter is None:
        settings = get_settings()
        _login_rate_limiter = SlidingWindowRateLimiter(
            max_attempts=settings.rate_limit_max_attempts,
            window_seconds=settings.rate_limit_window_seconds,
        )
    return _login_rate_limiter


def get_upload_rate_limiter() -> SlidingWindowRateLimiter:
    global _upload_rate_limiter
    if _upload_rate_limiter is None:
        settings = get_settings()
        _upload_rate_limiter = SlidingWindowRateLimiter(
            max_attempts=settings.rate_limit_max_attempts * 3,
            window_seconds=settings.rate_limit_window_seconds,
        )
    return _upload_rate_limiter


def reset_rate_limiters() -> None:
    """Test-only helper."""
    global _login_rate_limiter, _upload_rate_limiter
    _login_rate_limiter = None
    _upload_rate_limiter = None
