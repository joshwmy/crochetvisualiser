"""Deliberately invalid structured patterns: the validator must reject all of them.

Each case starts from a known-valid compiled pattern, applies one targeted
mutation, round-trips it through JSON (proving it is still schema-shaped —
only semantically wrong), and asserts the specific rule ID and severity the
validator is expected to report. A pattern with any of these defects must
never reach ``status: valid``.
"""

from __future__ import annotations

from decimal import Decimal

from crochet_reconstruction.domain.enums import ClosureKind, Severity, StitchFamily
from crochet_reconstruction.domain.operations import DecreaseOp, RepeatOp
from crochet_reconstruction.domain.pattern import Pattern
from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.templates.top_down_beanie import TOP_DOWN_BASIC
from crochet_reconstruction.validation.validator import validate
from tests.conftest import make_project_input


def _baseline() -> Pattern:
    return compile_pattern(make_project_input())


def _roundtrip(pattern: Pattern) -> Pattern:
    """Serialise to JSON and back, proving the mutation is still valid shape."""
    return Pattern.model_validate_json(pattern.model_dump_json())


def test_wrong_round_total() -> None:
    pattern = _baseline()
    body = pattern.components[1]
    bad_round = body.rounds[0].model_copy(update={"stated_total": body.rounds[0].stated_total + 1})
    bad_body = body.model_copy(update={"rounds": [bad_round, *body.rounds[1:]]})
    mutated = _roundtrip(
        pattern.model_copy(
            update={"components": [pattern.components[0], bad_body, pattern.components[2]]}
        )
    )

    report = validate(mutated, TOP_DOWN_BASIC)
    fatal_rules = {r.rule_id for r in report.results if r.severity is Severity.FATAL}
    assert "V-COUNT-001" in fatal_rules


def test_broken_repeat_count() -> None:
    pattern = _baseline()
    crown = pattern.components[0]
    increase_round = crown.rounds[1]  # round 2: repeat(times=8) { increase }
    original_repeat = increase_round.operations[0]
    assert isinstance(original_repeat, RepeatOp)
    broken_repeat = original_repeat.model_copy(update={"times": original_repeat.times - 1})
    bad_round = increase_round.model_copy(update={"operations": [broken_repeat]})
    bad_crown = crown.model_copy(update={"rounds": [crown.rounds[0], bad_round, *crown.rounds[2:]]})
    mutated = _roundtrip(
        pattern.model_copy(update={"components": [bad_crown, *pattern.components[1:]]})
    )

    report = validate(mutated, TOP_DOWN_BASIC)
    fatal_rules = {r.rule_id for r in report.results if r.severity is Severity.FATAL}
    assert "V-COUNT-001" in fatal_rules


def test_excessive_decrease() -> None:
    pattern = _baseline()
    crown, body = pattern.components[0], pattern.components[1]
    crown_final_total = crown.rounds[-1].stated_total
    stitch_family = body.rounds[0].operations[0].stitch  # type: ignore[union-attr]

    excessive_decrease = DecreaseOp(stitch=stitch_family, input=crown_final_total + 10, output=1)
    bad_round = body.rounds[0].model_copy(
        update={"operations": [excessive_decrease], "stated_total": 1}
    )
    bad_body = body.model_copy(update={"rounds": [bad_round, *body.rounds[1:]]})
    mutated = _roundtrip(
        pattern.model_copy(update={"components": [crown, bad_body, pattern.components[2]]})
    )

    report = validate(mutated, TOP_DOWN_BASIC)
    fatal_rules = {r.rule_id for r in report.results if r.severity is Severity.FATAL}
    assert "V-CONSUME-001" in fatal_rules


def test_missing_closure_metadata() -> None:
    # Phase 1 supports only continuous (spiral) rounds, which must never
    # carry closure metadata. A round claiming a slip-stitch join without
    # the (unsupported) joined-round machinery behind it is exactly the
    # "missing/invalid closure" failure mode in this schema.
    pattern = _baseline()
    crown = pattern.components[0]
    joined_round = crown.rounds[-1].model_copy(update={"closure": ClosureKind.SLIP_STITCH_JOIN})
    bad_crown = crown.model_copy(update={"rounds": [*crown.rounds[:-1], joined_round]})
    mutated = _roundtrip(
        pattern.model_copy(update={"components": [bad_crown, *pattern.components[1:]]})
    )

    report = validate(mutated, TOP_DOWN_BASIC)
    fatal_rules = {r.rule_id for r in report.results if r.severity is Severity.FATAL}
    assert "V-JOIN-001" in fatal_rules


def test_unsupported_stitch_operation() -> None:
    pattern = _baseline()  # uses hdc (see conftest.make_project_input default)
    mutated = _roundtrip(pattern)
    restricted_template = TOP_DOWN_BASIC.model_copy(
        update={"supported_stitch_families": [StitchFamily.SC]}
    )

    report = validate(mutated, restricted_template)
    fatal_rules = {r.rule_id for r in report.results if r.severity is Severity.FATAL}
    assert "V-OP-001" in fatal_rules


def test_contradictory_gauge_and_dimension() -> None:
    pattern = _baseline()
    blown_up_deviation = pattern.calculated.target_circumference_cm * Decimal("0.5")
    bad_calculated = pattern.calculated.model_copy(
        update={"circumference_deviation_cm": blown_up_deviation}
    )
    mutated = _roundtrip(pattern.model_copy(update={"calculated": bad_calculated}))

    report = validate(mutated, TOP_DOWN_BASIC)
    fatal_rules = {r.rule_id for r in report.results if r.severity is Severity.FATAL}
    assert "V-DIM-001" in fatal_rules


def test_crown_body_mismatch() -> None:
    pattern = _baseline()
    crown, body = pattern.components[0], pattern.components[1]
    detached_last_round = crown.rounds[-1].model_copy(
        update={
            "stated_total": crown.rounds[-1].stated_total - 8,
            "operations": crown.rounds[-2].operations,
        }
    )
    bad_crown = crown.model_copy(update={"rounds": [*crown.rounds[:-1], detached_last_round]})
    mutated = _roundtrip(
        pattern.model_copy(update={"components": [bad_crown, body, pattern.components[2]]})
    )

    report = validate(mutated, TOP_DOWN_BASIC)
    fatal_rules = {r.rule_id for r in report.results if r.severity is Severity.FATAL}
    assert "V-CROWN-001" in fatal_rules
