from crochet_reconstruction.domain.enums import BrimType, PatternStatus, StitchFamily
from crochet_reconstruction.physical_validation.trial_matrix import (
    MINIMUM_TRIAL_SET,
    RECOMMENDED_EXTENDED_MINIMUM_SET,
    TRIAL_MATRIX,
    build_trial_matrix_rows,
    compile_trial,
)


def test_trial_matrix_has_between_eight_and_twelve_trials() -> None:
    assert 8 <= len(TRIAL_MATRIX) <= 12


def test_trial_ids_are_unique_and_deterministic() -> None:
    ids_first = [t.trial_id for t in TRIAL_MATRIX]
    ids_second = [t.trial_id for t in TRIAL_MATRIX]
    assert ids_first == ids_second
    assert len(ids_first) == len(set(ids_first))


def test_trial_matrix_covers_both_stitch_families() -> None:
    families = {t.stitch_family for t in TRIAL_MATRIX}
    assert families == {StitchFamily.SC, StitchFamily.HDC}


def test_trial_matrix_covers_both_brim_types() -> None:
    brims = {t.brim_type for t in TRIAL_MATRIX}
    assert brims == {BrimType.NONE, BrimType.BLO_IN_ROUND}


def test_trial_matrix_covers_at_least_two_ease_values() -> None:
    ease_values = {t.negative_ease_pct for t in TRIAL_MATRIX}
    assert len(ease_values) >= 2


def test_trial_matrix_covers_at_least_two_round_gauges() -> None:
    round_gauges = {t.rounds_per_10cm for t in TRIAL_MATRIX}
    assert len(round_gauges) >= 2


def test_every_trial_compiles_without_error_and_is_not_fatal() -> None:
    for trial in TRIAL_MATRIX:
        pattern = compile_trial(trial)
        assert pattern.validation is not None
        assert pattern.validation.status is PatternStatus.VALID, (
            f"{trial.trial_id} is not valid: {pattern.validation.results}"
        )


def test_compile_trial_is_fingerprint_deterministic() -> None:
    trial = TRIAL_MATRIX[0]
    first = compile_trial(trial)
    second = compile_trial(trial)
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint is not None


def test_minimum_trial_set_is_subset_of_matrix() -> None:
    ids = {t.trial_id for t in TRIAL_MATRIX}
    assert set(MINIMUM_TRIAL_SET).issubset(ids)
    assert set(RECOMMENDED_EXTENDED_MINIMUM_SET).issubset(ids)
    assert set(MINIMUM_TRIAL_SET).issubset(set(RECOMMENDED_EXTENDED_MINIMUM_SET))


def test_minimum_trial_set_covers_both_stitches_and_both_brims() -> None:
    minimum_trials = [t for t in TRIAL_MATRIX if t.trial_id in MINIMUM_TRIAL_SET]
    assert {t.stitch_family for t in minimum_trials} == {StitchFamily.SC, StitchFamily.HDC}


def test_build_trial_matrix_rows_matches_trial_count() -> None:
    triples = build_trial_matrix_rows()
    assert len(triples) == len(TRIAL_MATRIX)
    for trial, pattern, row in triples:
        assert row.trial_id == trial.trial_id
        assert row.pattern_fingerprint == pattern.fingerprint
        assert row.final_body_stitch_count == pattern.calculated.body_stitch_count
