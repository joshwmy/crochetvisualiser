import json
from pathlib import Path

import pytest

from crochet_reconstruction.physical_validation.errors import (
    FingerprintMismatchError,
    UnknownTrialError,
)
from crochet_reconstruction.physical_validation.ingestion import (
    ingest_results_dir,
    load_result,
    verify_against_trial_matrix,
)
from crochet_reconstruction.physical_validation.trial_matrix import TRIAL_MATRIX, compile_trial
from tests.physical_validation.conftest import make_synthetic_result


def _real_fingerprint(trial_id: str = "BV-001") -> str:
    trial = next(t for t in TRIAL_MATRIX if t.trial_id == trial_id)
    pattern = compile_trial(trial)
    assert pattern.fingerprint is not None
    return pattern.fingerprint


def test_verify_accepts_correct_trial_id_and_fingerprint() -> None:
    result = make_synthetic_result(
        trial_id="BV-001", pattern_fingerprint=_real_fingerprint("BV-001")
    )
    verify_against_trial_matrix(result)  # must not raise


def test_verify_rejects_unknown_trial_id() -> None:
    result = make_synthetic_result(trial_id="BV-999", pattern_fingerprint="whatever")
    with pytest.raises(UnknownTrialError):
        verify_against_trial_matrix(result)


def test_verify_rejects_fingerprint_mismatch() -> None:
    result = make_synthetic_result(trial_id="BV-001", pattern_fingerprint="not-the-real-one")
    with pytest.raises(FingerprintMismatchError):
        verify_against_trial_matrix(result)


def _write_result_file(directory: Path, name: str, payload: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_payload() -> dict:
    result = make_synthetic_result(
        trial_id="BV-001", pattern_fingerprint=_real_fingerprint("BV-001")
    )
    return result.model_dump(mode="json")


def test_ingest_results_dir_accepts_valid_file(tmp_path: Path) -> None:
    _write_result_file(tmp_path, "good.json", _valid_payload())

    successes, failures = ingest_results_dir(tmp_path)

    assert len(successes) == 1
    assert failures == []


def test_ingest_results_dir_rejects_unknown_trial(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["trial_id"] = "BV-999"
    _write_result_file(tmp_path, "bad.json", payload)

    successes, failures = ingest_results_dir(tmp_path)

    assert successes == []
    assert len(failures) == 1
    assert "UnknownTrialError" in failures[0].error


def test_ingest_results_dir_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["pattern_fingerprint"] = "stale-fingerprint"
    _write_result_file(tmp_path, "bad.json", payload)

    successes, failures = ingest_results_dir(tmp_path)

    assert successes == []
    assert len(failures) == 1
    assert "FingerprintMismatchError" in failures[0].error


def test_ingest_results_dir_handles_missing_required_measurement(tmp_path: Path) -> None:
    payload = _valid_payload()
    del payload["finished_measurements"]["total_height_cm"]
    _write_result_file(tmp_path, "incomplete.json", payload)

    successes, failures = ingest_results_dir(tmp_path)

    assert successes == []
    assert len(failures) == 1
    assert "ValidationError" in failures[0].error


def test_ingest_results_dir_handles_malformed_json(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    successes, failures = ingest_results_dir(tmp_path)

    assert successes == []
    assert len(failures) == 1


def test_ingest_results_dir_supports_multiple_testers_same_trial(tmp_path: Path) -> None:
    fingerprint = _real_fingerprint("BV-001")
    payload_a = make_synthetic_result(
        trial_id="BV-001", pattern_fingerprint=fingerprint, tester_id="SYN-1"
    ).model_dump(mode="json")
    payload_b = make_synthetic_result(
        trial_id="BV-001", pattern_fingerprint=fingerprint, tester_id="SYN-2"
    ).model_dump(mode="json")
    _write_result_file(tmp_path, "a.json", payload_a)
    _write_result_file(tmp_path, "b.json", payload_b)

    successes, failures = ingest_results_dir(tmp_path)

    assert failures == []
    assert len(successes) == 2
    assert {r.tester.tester_id for r in successes} == {"SYN-1", "SYN-2"}
    # No averaging: both raw results are present independently.
    assert successes[0].trial_id == successes[1].trial_id


def test_load_result_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_result(tmp_path / "does_not_exist.json")
