import json
from pathlib import Path

from crochet_reconstruction.cli import main


def _write_input(tmp_path: Path, encoding: str, **overrides: str) -> Path:
    payload = {
        "project": {"project_id": "cli-test", "title": "CLI Test Beanie"},
        "template": {"id": "top_down_basic", "version": "1.0.0"},
        "measurements": {
            "head_circumference_cm": "56.0",
            "target_height_cm": "21.0",
            "brim_height_cm": "4.0",
        },
        "gauge": {"stitch_family": "hdc", "stitches_per_10cm": "16.0", "rounds_per_10cm": "12.0"},
        "negative_ease_pct": "8.0",
        "construction": "continuous_rounds",
        "brim_type": "blo_in_round",
    }
    payload.update(overrides)
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload), encoding=encoding)
    return input_path


def test_cli_generate_succeeds_with_utf8_bom_input(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, encoding="utf-8-sig")
    output_dir = tmp_path / "out"

    exit_code = main(["generate", "--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "pattern.json").exists()
    assert (output_dir / "pattern.txt").exists()


def test_cli_generate_rejects_invalid_input_without_repair(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "project": {"project_id": "cli-test", "title": "CLI Test Beanie"},
                "template": {"id": "top_down_basic", "version": "1.0.0"},
                "measurements": {"head_circumference_cm": "56.0", "target_height_cm": "-5"},
                "gauge": {
                    "stitch_family": "hdc",
                    "stitches_per_10cm": "16.0",
                    "rounds_per_10cm": "12.0",
                },
                "negative_ease_pct": "8.0",
                "construction": "continuous_rounds",
                "brim_type": "none",
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    exit_code = main(["generate", "--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 2
    assert not (output_dir / "pattern.json").exists()


def test_cli_generate_rejects_malformed_json(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text("{not valid json", encoding="utf-8")
    output_dir = tmp_path / "out"

    exit_code = main(["generate", "--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 2


def test_cli_generate_rejects_brim_enabled_without_height_cleanly(tmp_path: Path) -> None:
    """Regression test: this used to raise an uncaught ValueError traceback
    from deep inside the brim engine instead of a clean exit-2 error."""
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "project": {"project_id": "cli-test", "title": "CLI Test Beanie"},
                "template": {"id": "top_down_basic", "version": "1.0.0"},
                "measurements": {"head_circumference_cm": "56.0", "target_height_cm": "21.0"},
                "gauge": {
                    "stitch_family": "hdc",
                    "stitches_per_10cm": "16.0",
                    "rounds_per_10cm": "12.0",
                },
                "negative_ease_pct": "8.0",
                "construction": "continuous_rounds",
                "brim_type": "blo_in_round",
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    exit_code = main(["generate", "--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 2
    assert not output_dir.exists()
