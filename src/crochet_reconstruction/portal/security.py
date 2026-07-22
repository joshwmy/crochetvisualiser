"""Password hashing, token generation/hashing, and a small rate limiter.

PBKDF2-HMAC-SHA256 (stdlib `hashlib`) is used for password hashing instead
of bcrypt/argon2 to avoid a new heavy dependency for a small pilot's admin
accounts — documented as a deliberate tradeoff in docs/portal-architecture.md,
not an oversight. Invitation tokens are never stored in plaintext: only
their SHA-256 hash is persisted, so a database leak does not hand out valid
invitation links.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import string
import time
from collections import defaultdict
from dataclasses import dataclass, field

_PBKDF2_ITERATIONS = 600_000
_PBKDF2_ALGORITHM = "sha256"
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGORITHM, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_{_PBKDF2_ALGORITHM}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        algorithm_label, iterations_str, salt_hex, digest_hex = hashed.split("$")
        algorithm = algorithm_label.removeprefix("pbkdf2_")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac(algorithm, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def generate_invitation_token() -> str:
    """Cryptographically secure, URL-safe token. Never stored in plaintext."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_SUBMISSION_REFERENCE_ALPHABET = "".join(
    c for c in (string.ascii_uppercase + string.digits) if c not in "01OI"
)


def generate_submission_reference() -> str:
    """A short, human-readable code shown to contributors (never a DB ID or
    fingerprint). Excludes visually ambiguous characters (0/O, 1/I)."""
    body = "".join(secrets.choice(_SUBMISSION_REFERENCE_ALPHABET) for _ in range(8))
    return f"CR-{body[:4]}-{body[4:]}"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


@dataclass
class SlidingWindowRateLimiter:
    """In-memory sliding-window limiter. Pilot-grade only: it does not
    survive a process restart and does not coordinate across multiple
    worker processes. Documented explicitly as not DDoS-resistant — a
    reverse proxy / hosting-platform rate limit is still recommended for
    anything beyond a small invited pilot (see docs/portal-deployment.md).
    """

    max_attempts: int
    window_seconds: float
    _attempts: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        attempts = self._attempts[key]
        attempts[:] = [t for t in attempts if t >= window_start]
        if len(attempts) >= self.max_attempts:
            return False
        attempts.append(now)
        return True

    def reset(self) -> None:
        self._attempts.clear()
