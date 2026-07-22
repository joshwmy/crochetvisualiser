"""Structured exceptions for physical-result ingestion."""

from __future__ import annotations


class PhysicalValidationError(Exception):
    """Base class for Phase 1.5 physical-validation errors."""


class UnknownTrialError(PhysicalValidationError):
    """Raised when a result references a trial ID not in the trial matrix."""


class FingerprintMismatchError(PhysicalValidationError):
    """Raised when a result's ``pattern_fingerprint`` does not match the
    fingerprint the engine currently produces for that trial ID.

    This catches both typos and, more importantly, results submitted against
    a stale pattern after the engine (or the trial matrix itself) changed —
    a physical result is only meaningful if we know exactly which generated
    pattern it was crocheted from.
    """
