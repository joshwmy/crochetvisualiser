"""Load and validate submitted physical-trial result files.

Each result file is checked against the *current* trial matrix: an unknown
``trial_id`` or a ``pattern_fingerprint`` that no longer matches what the
engine produces for that trial is rejected outright, not warned about and
kept. A single bad file does not abort the whole batch — failures are
collected alongside successes so a report can list exactly what needs
attention (see :mod:`crochet_reconstruction.physical_validation.evaluation_report`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from crochet_reconstruction.physical_validation.errors import (
    FingerprintMismatchError,
    UnknownTrialError,
)
from crochet_reconstruction.physical_validation.result_schema import PhysicalTrialResult
from crochet_reconstruction.physical_validation.trial_matrix import TRIAL_MATRIX, compile_trial


@dataclass(frozen=True, slots=True)
class IngestionFailure:
    path: Path
    error: str


def load_result(path: Path) -> PhysicalTrialResult:
    """Parse and schema-validate one result file. Raises on malformed/missing data."""
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return PhysicalTrialResult.model_validate(raw)


def verify_against_trial_matrix(result: PhysicalTrialResult) -> None:
    """Raise if ``result`` does not correspond to a real, current trial.

    Recompiles the referenced trial through the live engine rather than
    trusting any cached fingerprint, so a result can never be silently
    accepted against a trial definition or engine version that has since
    changed.
    """
    trial = next((t for t in TRIAL_MATRIX if t.trial_id == result.trial_id), None)
    if trial is None:
        known = ", ".join(t.trial_id for t in TRIAL_MATRIX)
        raise UnknownTrialError(
            f"unknown trial_id {result.trial_id!r}; not in the current trial "
            f"matrix (known trials: {known})"
        )

    pattern = compile_trial(trial)
    if pattern.fingerprint != result.pattern_fingerprint:
        raise FingerprintMismatchError(
            f"result for {result.trial_id!r} declares pattern_fingerprint "
            f"{result.pattern_fingerprint!r}, but the trial matrix currently "
            f"produces {pattern.fingerprint!r} for that trial — the trial "
            f"matrix or engine has changed since this result was recorded, "
            f"or the result references the wrong trial"
        )


def ingest_results_dir(
    results_dir: Path,
) -> tuple[list[PhysicalTrialResult], list[IngestionFailure]]:
    """Load every ``*.json`` file in ``results_dir``.

    Returns ``(successes, failures)``. Multiple files may validly report on
    the same ``trial_id`` (multiple testers) — no deduplication or
    averaging happens here.
    """
    successes: list[PhysicalTrialResult] = []
    failures: list[IngestionFailure] = []

    for path in sorted(results_dir.glob("*.json")):
        try:
            result = load_result(path)
            verify_against_trial_matrix(result)
        except (
            OSError,
            json.JSONDecodeError,
            PydanticValidationError,
            UnknownTrialError,
            FingerprintMismatchError,
        ) as exc:
            failures.append(IngestionFailure(path=path, error=f"{type(exc).__name__}: {exc}"))
            continue
        successes.append(result)

    return successes, failures
