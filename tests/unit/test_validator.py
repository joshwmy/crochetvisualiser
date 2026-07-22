from crochet_reconstruction.domain.enums import ClosureKind
from crochet_reconstruction.domain.operations import IncreaseOp
from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.templates.top_down_beanie import TOP_DOWN_BASIC
from crochet_reconstruction.validation.validator import validate
from tests.conftest import make_project_input


def _baseline_components():
    # A validated pattern's components, used as a starting point for mutation.
    pattern = compile_pattern(make_project_input())
    return list(pattern.components), pattern


def test_wrong_stated_total_is_fatal_v_count_001() -> None:
    components, pattern = _baseline_components()
    crown = components[0]
    bad_round = crown.rounds[-1].model_copy(
        update={"stated_total": crown.rounds[-1].stated_total + 1}
    )
    bad_crown = crown.model_copy(update={"rounds": [*crown.rounds[:-1], bad_round]})
    mutated = pattern.model_copy(update={"components": [bad_crown, *components[1:]]})

    report = validate(mutated, TOP_DOWN_BASIC)
    assert report.has_fatal
    assert any(r.rule_id == "V-COUNT-001" for r in report.results)


def test_excessive_consumption_is_fatal_v_consume_001() -> None:
    components, pattern = _baseline_components()
    crown, body = components[0], components[1]
    # Body's first round claims to consume more than the crown produced by
    # adding an extra increase (also produces a wrong stated_total, but the
    # consumption check must independently fire too).
    original_round = body.rounds[0]
    bloated_op = IncreaseOp(stitch=original_round.operations[0].stitch, input=1, output=2)
    bad_round = original_round.model_copy(
        update={
            "operations": [*original_round.operations, bloated_op],
            "stated_total": original_round.stated_total + 2,
        }
    )
    bad_body = body.model_copy(update={"rounds": [bad_round, *body.rounds[1:]]})
    mutated = pattern.model_copy(update={"components": [crown, bad_body, *components[2:]]})

    report = validate(mutated, TOP_DOWN_BASIC)
    assert report.has_fatal
    assert any(r.rule_id == "V-CONSUME-001" for r in report.results)


def test_partial_consumption_is_fatal_v_consume_002() -> None:
    components, pattern = _baseline_components()
    crown, body = components[0], components[1]
    original_round = body.rounds[0]
    reduced_op = original_round.operations[0].model_copy(
        update={"count": original_round.operations[0].count - 1}
    )
    bad_round = original_round.model_copy(
        update={"operations": [reduced_op], "stated_total": original_round.stated_total - 1}
    )
    bad_body = body.model_copy(update={"rounds": [bad_round, *body.rounds[1:]]})
    mutated = pattern.model_copy(update={"components": [crown, bad_body, *components[2:]]})

    report = validate(mutated, TOP_DOWN_BASIC)
    assert report.has_fatal
    assert any(r.rule_id == "V-CONSUME-002" for r in report.results)


def test_crown_body_mismatch_is_fatal_v_crown_001() -> None:
    components, pattern = _baseline_components()
    crown, body = components[0], components[1]
    bad_crown_last = crown.rounds[-1].model_copy(
        update={
            "stated_total": crown.rounds[-1].stated_total - 8,
            "operations": crown.rounds[-2].operations,
        }
    )
    bad_crown = crown.model_copy(update={"rounds": [*crown.rounds[:-1], bad_crown_last]})
    mutated = pattern.model_copy(update={"components": [bad_crown, body, *components[2:]]})

    report = validate(mutated, TOP_DOWN_BASIC)
    assert report.has_fatal
    assert any(r.rule_id == "V-CROWN-001" for r in report.results)


def test_round_numbering_gap_is_fatal_v_round_001() -> None:
    components, pattern = _baseline_components()
    crown = components[0]
    skipped = crown.rounds[-1].model_copy(update={"number": crown.rounds[-1].number + 1})
    bad_crown = crown.model_copy(update={"rounds": [*crown.rounds[:-1], skipped]})
    mutated = pattern.model_copy(update={"components": [bad_crown, *components[1:]]})

    report = validate(mutated, TOP_DOWN_BASIC)
    assert report.has_fatal
    assert any(r.rule_id == "V-ROUND-001" for r in report.results)


def test_closure_on_continuous_round_is_fatal_v_join_001() -> None:
    components, pattern = _baseline_components()
    crown = components[0]
    joined = crown.rounds[-1].model_copy(update={"closure": ClosureKind.SLIP_STITCH_JOIN})
    bad_crown = crown.model_copy(update={"rounds": [*crown.rounds[:-1], joined]})
    mutated = pattern.model_copy(update={"components": [bad_crown, *components[1:]]})

    report = validate(mutated, TOP_DOWN_BASIC)
    assert report.has_fatal
    assert any(r.rule_id == "V-JOIN-001" for r in report.results)


def test_valid_pattern_has_no_fatal_or_confirmation_results() -> None:
    _, pattern = _baseline_components()
    report = validate(pattern, TOP_DOWN_BASIC)
    assert not report.has_fatal
