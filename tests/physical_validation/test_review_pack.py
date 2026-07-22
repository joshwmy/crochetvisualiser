import csv
import json
from pathlib import Path

from crochet_reconstruction.physical_validation.review_pack import generate_expert_review_pack
from crochet_reconstruction.physical_validation.trial_matrix import TRIAL_MATRIX


def test_generate_expert_review_pack_creates_expected_top_level_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "expert_review"
    generate_expert_review_pack(output_dir)

    for name in [
        "index.md",
        "trial-matrix.csv",
        "trial-matrix.json",
        "crocheter-instructions.md",
        "measurement-guide.md",
        "evaluation-rubric.md",
    ]:
        assert (output_dir / name).exists(), f"missing {name}"


def test_generate_expert_review_pack_creates_one_directory_per_trial(tmp_path: Path) -> None:
    output_dir = tmp_path / "expert_review"
    generate_expert_review_pack(output_dir)

    patterns_dir = output_dir / "patterns"
    trial_dirs = sorted(p.name for p in patterns_dir.iterdir())
    expected = sorted(t.trial_id for t in TRIAL_MATRIX)
    assert trial_dirs == expected


def test_each_trial_directory_has_required_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "expert_review"
    generate_expert_review_pack(output_dir)

    for trial in TRIAL_MATRIX:
        trial_dir = output_dir / "patterns" / trial.trial_id
        for name in [
            "input.json",
            "pattern.json",
            "validation.json",
            "pattern.txt",
            "review-form.md",
        ]:
            assert (trial_dir / name).exists(), f"{trial.trial_id} missing {name}"


def test_trial_matrix_csv_has_one_row_per_trial(tmp_path: Path) -> None:
    output_dir = tmp_path / "expert_review"
    generate_expert_review_pack(output_dir)

    with (output_dir / "trial-matrix.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(TRIAL_MATRIX)
    assert {r["trial_id"] for r in rows} == {t.trial_id for t in TRIAL_MATRIX}


def test_trial_matrix_json_fingerprints_match_pattern_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "expert_review"
    generate_expert_review_pack(output_dir)

    rows = json.loads((output_dir / "trial-matrix.json").read_text(encoding="utf-8"))
    for row in rows:
        pattern = json.loads(
            (output_dir / "patterns" / row["trial_id"] / "pattern.json").read_text(encoding="utf-8")
        )
        assert row["pattern_fingerprint"] == pattern["fingerprint"]


def test_review_form_contains_required_sections(tmp_path: Path) -> None:
    output_dir = tmp_path / "expert_review"
    generate_expert_review_pack(output_dir)

    text = (output_dir / "patterns" / "BV-001" / "review-form.md").read_text(encoding="utf-8")
    for heading in [
        "Tester information",
        "Pre-crochet information",
        "During-crochet evaluation",
        "Final measurements",
        "Outcome ratings",
        "Acceptance status",
    ]:
        assert heading in text


def test_generate_expert_review_pack_is_deterministic(tmp_path: Path) -> None:
    output_a = tmp_path / "a"
    output_b = tmp_path / "b"
    generate_expert_review_pack(output_a)
    generate_expert_review_pack(output_b)

    matrix_a = (output_a / "trial-matrix.json").read_text(encoding="utf-8")
    matrix_b = (output_b / "trial-matrix.json").read_text(encoding="utf-8")
    assert matrix_a == matrix_b
