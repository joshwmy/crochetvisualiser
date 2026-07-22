import time

from crochet_reconstruction.portal.security import (
    SlidingWindowRateLimiter,
    generate_invitation_token,
    generate_submission_reference,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_password_round_trip() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hash_password_produces_different_salts() -> None:
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("anything", "not-a-valid-hash-format")


def test_invitation_token_is_url_safe_and_long() -> None:
    token = generate_invitation_token()
    assert len(token) >= 32
    assert all(c.isalnum() or c in "-_" for c in token)


def test_hash_token_is_deterministic() -> None:
    token = generate_invitation_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token


def test_submission_reference_format_and_uniqueness() -> None:
    references = {generate_submission_reference() for _ in range(200)}
    assert len(references) == 200
    for ref in references:
        assert ref.startswith("CR-")
        assert "0" not in ref.split("-", 1)[1]
        assert "O" not in ref
        assert "1" not in ref.split("-", 1)[1]
        assert "I" not in ref


def test_rate_limiter_allows_up_to_max_attempts() -> None:
    limiter = SlidingWindowRateLimiter(max_attempts=3, window_seconds=60)
    assert limiter.allow("key") is True
    assert limiter.allow("key") is True
    assert limiter.allow("key") is True
    assert limiter.allow("key") is False


def test_rate_limiter_tracks_keys_independently() -> None:
    limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False


def test_rate_limiter_resets_after_window(monkeypatch: object) -> None:
    limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=0.05)
    assert limiter.allow("key") is True
    assert limiter.allow("key") is False
    time.sleep(0.1)
    assert limiter.allow("key") is True
