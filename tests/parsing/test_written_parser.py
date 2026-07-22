"""Parser unit tests: source text -> list[Component] + diagnostics.

See docs/written-pattern-grammar.md for the supported syntax this exercises.
"""

from __future__ import annotations

from crochet_reconstruction.domain.enums import ComponentKind
from crochet_reconstruction.parsing.written import parse_written_pattern
from crochet_reconstruction.parsing.written.diagnostics import DiagnosticCode

AMIGURUMI_EXAMPLE = """\
Round 1: 6 sc in magic ring [6]
Round 2: inc in each stitch around [12]
Round 3: (sc, inc) repeat 6 times [18]
Rounds 4-6: sc around [18]
Round 7: (sc, dec) repeat 6 times [12]
Round 8: dec around [6]
"""


def _ok(source: str):
    components, diagnostics = parse_written_pattern(source)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert components is not None, f"expected success, got errors: {errors}"
    return components, diagnostics


def _fails_with(source: str, code: DiagnosticCode):
    components, diagnostics = parse_written_pattern(source)
    assert components is None, "expected failure"
    codes = [d.code for d in diagnostics if d.severity == "error"]
    assert code in codes, f"expected {code} in {codes}"
    return diagnostics


def test_full_amigurumi_example_compiles():
    components, _ = _ok(AMIGURUMI_EXAMPLE)
    assert len(components) == 1
    assert components[0].kind is ComponentKind.PIECE
    totals = [r.stated_total for r in components[0].rounds]
    assert totals == [6, 12, 18, 18, 18, 18, 12, 6]


def test_round_range_expands_to_three_identical_rounds():
    components, _ = _ok(AMIGURUMI_EXAMPLE)
    r4, r5, r6 = components[0].rounds[3:6]
    assert (r4.number, r5.number, r6.number) == (4, 5, 6)
    assert r4.stated_total == r5.stated_total == r6.stated_total == 18


def test_deterministic_output():
    components_a, _ = _ok(AMIGURUMI_EXAMPLE)
    components_b, _ = _ok(AMIGURUMI_EXAMPLE)
    assert [c.model_dump() for c in components_a] == [c.model_dump() for c in components_b]


# --- Abbreviations -----------------------------------------------------


def test_sc_abbreviation():
    _ok("Round 1: 6 sc in magic ring [6]\n")


def test_single_crochet_full_name():
    _ok("Round 1: 6 single crochet in magic ring [6]\n")


def test_hdc_abbreviation():
    _ok("Round 1: 6 hdc in magic ring [6]\n")


def test_half_double_crochet_full_name():
    _ok("Round 1: 6 half double crochet in magic ring [6]\n")


def test_dc_abbreviation():
    _ok("Round 1: 6 dc in magic ring [6]\n")


def test_double_crochet_full_name():
    _ok("Round 1: 6 double crochet in magic ring [6]\n")


def test_inc_abbreviation():
    _ok("Round 1: 6 sc in magic ring [6]\nRound 2: inc around [12]\n")


def test_increase_full_word():
    _ok("Round 1: 6 sc in magic ring [6]\nRound 2: increase around [12]\n")


def test_dec_abbreviation():
    _ok("Round 1: 12 sc in magic ring [12]\nRound 2: dec around [6]\n")


def test_decrease_full_word():
    _ok("Round 1: 12 sc in magic ring [12]\nRound 2: decrease around [6]\n")


def test_magic_ring():
    _ok("Round 1: 6 sc in magic ring [6]\n")


def test_magic_circle_synonym():
    _ok("Round 1: 6 sc in magic circle [6]\n")


def test_chain_recognized_but_unsupported():
    _fails_with("Round 1: 10 ch [10]\n", DiagnosticCode.UNSUPPORTED_SYNTAX)


def test_chain_full_word_recognized_but_unsupported():
    _fails_with("Round 1: 10 chain [10]\n", DiagnosticCode.UNSUPPORTED_SYNTAX)


def test_slip_stitch_abbreviation_recognized_but_unsupported():
    _fails_with(
        "Round 1: 6 sc in magic ring [6]\nRound 2: sl st around [6]\n",
        DiagnosticCode.UNSUPPORTED_SYNTAX,
    )


def test_slip_stitch_full_name_recognized_but_unsupported():
    _fails_with(
        "Round 1: 6 sc in magic ring [6]\nRound 2: slip stitch around [6]\n",
        DiagnosticCode.UNSUPPORTED_SYNTAX,
    )


def test_row_keyword_accepted():
    _ok("Row 1: 6 sc in magic ring [6]\n")


def test_rnd_and_rnds_synonyms():
    _ok("Rnd 1: 6 sc in magic ring [6]\nRnds 2-3: sc around [6]\n")


# --- Case, punctuation, whitespace, comments ----------------------------


def test_uppercase_input():
    _ok("ROUND 1: 6 SC IN MAGIC RING [6]\n")


def test_mixed_case_input():
    _ok("RoUnD 1: 6 Sc In Magic Ring [6]\n")


def test_blank_lines_are_skipped():
    _ok("\n\nRound 1: 6 sc in magic ring [6]\n\n\n")


def test_comment_lines_are_skipped():
    _ok("# a comment\nRound 1: 6 sc in magic ring [6]\n// another comment\n")


def test_trailing_period_is_tolerated():
    _ok("Round 1: 6 sc in magic ring [6].\n")


def test_extra_whitespace_is_tolerated():
    _ok("Round   1  :   6   sc   in   magic   ring   [6]\n")


# --- Groups, repeats, around ---------------------------------------------


def test_parenthesised_repeat_group():
    _ok("Round 1: 12 sc in magic ring [12]\nRound 2: (sc, inc) repeat 6 times [18]\n")


def test_around_keyword():
    _ok("Round 1: 6 sc in magic ring [6]\nRound 2: sc around [6]\n")


def test_in_each_stitch_around_phrase():
    _ok("Round 1: 6 sc in magic ring [6]\nRound 2: inc in each stitch around [12]\n")


def test_round_range_syntax():
    _ok("Round 1: 6 sc in magic ring [6]\nRounds 2-4: sc around [6]\n")


# --- Declared counts ------------------------------------------------------


def test_declared_count_brackets():
    components, _ = _ok("Round 1: 6 sc in magic ring [6]\n")
    assert components[0].rounds[0].stated_total == 6


def test_declared_count_parens():
    components, _ = _ok("Round 1: 6 sc in magic ring (6)\n")
    assert components[0].rounds[0].stated_total == 6


def test_declared_count_sts_word():
    components, _ = _ok("Round 1: 6 sc in magic ring 6 sts\n")
    assert components[0].rounds[0].stated_total == 6


def test_missing_declared_count_is_allowed_when_computable():
    # No bracket/paren/sts count at all — still compiles, since the round's
    # total is fully determined by its own instructions.
    _ok("Round 1: 6 sc in magic ring\n")


# --- Errors ----------------------------------------------------------------


def test_stitch_count_mismatch():
    _fails_with(
        "Round 1: 6 sc in magic ring [6]\nRound 2: inc around [999]\n",
        DiagnosticCode.STITCH_COUNT_MISMATCH,
    )


def test_invalid_range_backwards():
    _fails_with("Round 5-1: sc around [6]\n", DiagnosticCode.INVALID_RANGE)


def test_invalid_range_gap_in_numbering():
    _fails_with(
        "Round 1: 6 sc in magic ring [6]\nRound 3: sc around [6]\n",
        DiagnosticCode.INVALID_RANGE,
    )


def test_unsupported_abbreviation_rejected_as_invalid_syntax():
    _fails_with("Round 1: 6 xyz in magic ring [6]\n", DiagnosticCode.INVALID_SYNTAX)


def test_incomplete_repeat_syntax():
    _fails_with(
        "Round 1: 6 sc in magic ring [6]\nRound 2: (sc, inc) repeat [12]\n",
        DiagnosticCode.INVALID_SYNTAX,
    )


def test_empty_input():
    _fails_with("", DiagnosticCode.EMPTY_INPUT)


def test_whitespace_only_input():
    _fails_with("   \n\n  ", DiagnosticCode.EMPTY_INPUT)


def test_missing_foundation():
    _fails_with("Round 1: sc around [6]\n", DiagnosticCode.MISSING_FOUNDATION)


def test_insufficient_parent_stitches():
    # Round 2 needs 3*2=6 previous-round stitches but round 1 only has 3.
    _fails_with(
        "Round 1: 3 sc in magic ring [3]\nRound 2: (sc, inc) repeat 3 times [9]\n",
        DiagnosticCode.INSUFFICIENT_PARENT_STITCHES,
    )


def test_around_not_evenly_divisible_is_invalid_repeat():
    _fails_with(
        "Round 1: 5 sc in magic ring [5]\nRound 2: dec around [2]\n",
        DiagnosticCode.INVALID_REPEAT,
    )


def test_line_and_source_text_are_attached_to_diagnostics():
    diagnostics = _fails_with(
        "Round 1: 6 sc in magic ring [6]\nRound 2: xyz around [1]\n",
        DiagnosticCode.INVALID_SYNTAX,
    )
    error = next(d for d in diagnostics if d.severity == "error")
    assert error.line == 2
    assert "xyz" in (error.source_text or "")
