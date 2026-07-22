"""Golden tests: reviewed example inputs must keep producing identical output.

Expected outputs under ``tests/golden/expected/`` are engine-generated
reference text pending human crochet-expert sign-off (Phase 1 has no expert
review loop yet — this is flagged explicitly in README.md and
docs/product-boundary.md). They exist so any change to the engine's output
is a deliberate, reviewed diff rather than a silent drift.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crochet_reconstruction.domain.pattern import ProjectInput
from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.rendering.text_renderer import render_text

_GOLDEN_DIR = Path(__file__).parent
_INPUTS_DIR = _GOLDEN_DIR / "inputs"
_EXPECTED_DIR = _GOLDEN_DIR / "expected"

_CASES = sorted(p.stem for p in _INPUTS_DIR.glob("*.json"))


@pytest.mark.parametrize("case_name", _CASES)
def test_golden_pattern_matches_reference_text(case_name: str) -> None:
    raw = json.loads((_INPUTS_DIR / f"{case_name}.json").read_text(encoding="utf-8"))
    project_input = ProjectInput.model_validate(raw)
    pattern = compile_pattern(project_input)

    assert pattern.validation is not None
    assert not pattern.validation.has_fatal, pattern.validation.results

    actual_text = render_text(pattern)
    expected_path = _EXPECTED_DIR / f"{case_name}.txt"
    expected_text = expected_path.read_text(encoding="utf-8")

    assert actual_text == expected_text


@pytest.mark.parametrize("case_name", _CASES)
def test_golden_pattern_structural_invariants(case_name: str) -> None:
    raw = json.loads((_INPUTS_DIR / f"{case_name}.json").read_text(encoding="utf-8"))
    project_input = ProjectInput.model_validate(raw)
    pattern = compile_pattern(project_input)

    kinds = [c.kind.value for c in pattern.components]
    assert kinds[0] == "crown"
    assert kinds[1] == "body"
    if project_input.brim_type.value != "none":
        assert "brim" in kinds
    else:
        assert "brim" not in kinds

    crown = pattern.components[0]
    body = pattern.components[1]
    assert (
        crown.rounds[-1].stated_total
        == body.rounds[0].stated_total
        == pattern.calculated.body_stitch_count
    )

    all_numbers = [r.number for c in pattern.components for r in c.rounds]
    assert all_numbers == list(range(1, len(all_numbers) + 1))


def test_all_six_required_golden_categories_are_present() -> None:
    required_substrings = [
        "_sc",
        "_hdc",
        "small_circumference",
        "large_circumference",
        "no_brim",
        "simple_brim",
    ]
    for substring in required_substrings:
        assert any(substring in case for case in _CASES), (
            f"missing golden case covering {substring!r}"
        )
