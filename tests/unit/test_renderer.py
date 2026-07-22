import pytest

from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.rendering.text_renderer import PatternNotRenderableError, render_text
from tests.conftest import make_project_input


def test_render_text_contains_expected_sections() -> None:
    pattern = compile_pattern(make_project_input())
    text = render_text(pattern)

    assert "## Materials and assumptions" in text
    assert "## Gauge" in text
    assert "## Finished measurements" in text
    assert "## Abbreviations" in text
    assert "## Crown" in text
    assert "## Body" in text
    assert "## Brim" in text
    assert "## Validation status" in text
    assert f"Pattern fingerprint: {pattern.fingerprint}" in text


def test_render_text_shows_stitch_total_every_round() -> None:
    pattern = compile_pattern(make_project_input())
    text = render_text(pattern)
    for component in pattern.components:
        for round_ in component.rounds:
            assert f"({round_.stated_total})" in text


def test_render_text_never_alters_stated_totals() -> None:
    pattern = compile_pattern(make_project_input())
    text = render_text(pattern)
    last_crown_total = pattern.components[0].rounds[-1].stated_total
    assert str(last_crown_total) in text


def test_render_refuses_unvalidated_pattern() -> None:
    pattern = compile_pattern(make_project_input())
    unvalidated = pattern.model_copy(update={"validation": None})
    with pytest.raises(PatternNotRenderableError):
        render_text(unvalidated)


def test_render_refuses_pattern_with_fatal_results() -> None:
    pattern = compile_pattern(make_project_input(head_circumference_cm="40.0"))
    assert pattern.validation.has_fatal  # type: ignore[union-attr]
    with pytest.raises(PatternNotRenderableError):
        render_text(pattern)
