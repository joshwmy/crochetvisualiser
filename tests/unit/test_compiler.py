from decimal import Decimal

import pytest

from crochet_reconstruction.domain.enums import BrimType, Construction, PatternStatus, StitchFamily
from crochet_reconstruction.domain.errors import UnsupportedConstructionError
from crochet_reconstruction.engine.compiler import canonical_json, compile_pattern
from tests.conftest import make_project_input


def test_compile_pattern_valid_hdc_beanie() -> None:
    pattern = compile_pattern(make_project_input())
    assert pattern.validation is not None
    assert pattern.validation.status is PatternStatus.VALID
    assert not pattern.validation.has_fatal
    assert pattern.fingerprint is not None
    assert len(pattern.components) == 3  # crown, body, brim


def test_compile_pattern_no_brim_omits_brim_component() -> None:
    pattern = compile_pattern(make_project_input(brim_type=BrimType.NONE, brim_height_cm=None))
    kinds = [c.kind.value for c in pattern.components]
    assert kinds == ["crown", "body"]


def test_compile_pattern_sc_beanie() -> None:
    pattern = compile_pattern(
        make_project_input(
            stitch_family=StitchFamily.SC,
            stitches_per_10cm=Decimal("18.0"),
            rounds_per_10cm=Decimal("18.0"),
        )
    )
    assert not pattern.validation.has_fatal  # type: ignore[union-attr]


def test_compile_pattern_rejects_joined_construction() -> None:
    with pytest.raises(UnsupportedConstructionError, match="joined_rounds"):
        compile_pattern(make_project_input(construction=Construction.JOINED))


def test_compile_pattern_out_of_template_range_yields_fatal_validation_not_exception() -> None:
    # 40cm head circumference is below the template's 42cm minimum: this
    # should compile and be flagged fatal by the validator, not raise.
    pattern = compile_pattern(make_project_input(head_circumference_cm=Decimal("40.0")))
    assert pattern.validation is not None
    assert pattern.validation.has_fatal
    assert any(r.rule_id == "V-RANGE-001" for r in pattern.validation.results)


def test_identical_inputs_produce_identical_fingerprints() -> None:
    input_a = make_project_input()
    input_b = make_project_input()
    pattern_a = compile_pattern(input_a)
    pattern_b = compile_pattern(input_b)
    assert pattern_a.fingerprint == pattern_b.fingerprint
    assert pattern_a.fingerprint is not None


def test_different_inputs_produce_different_fingerprints() -> None:
    pattern_a = compile_pattern(make_project_input())
    pattern_b = compile_pattern(make_project_input(head_circumference_cm=Decimal("58.0")))
    assert pattern_a.fingerprint != pattern_b.fingerprint


def test_canonical_json_excludes_fingerprint_field() -> None:
    pattern = compile_pattern(make_project_input())
    assert '"fingerprint"' not in canonical_json(pattern)


def test_crown_final_round_matches_body_first_round() -> None:
    pattern = compile_pattern(make_project_input())
    crown = next(c for c in pattern.components if c.kind.value == "crown")
    body = next(c for c in pattern.components if c.kind.value == "body")
    assert crown.rounds[-1].stated_total == body.rounds[0].stated_total
    assert crown.rounds[-1].stated_total == pattern.calculated.body_stitch_count
