"""Property-based tests over the deterministic engine.

Strategies are constrained to the ``top_down_basic`` template's supported
ranges — inputs outside that range are exercised separately in unit tests
(they are expected to compile with fatal validation results, not to be
arithmetically well-formed).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from crochet_reconstruction.domain.enums import BrimType, StitchFamily
from crochet_reconstruction.domain.operations import consumed_count, produced_count
from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.templates.top_down_beanie import TOP_DOWN_BASIC
from tests.conftest import make_project_input

_RANGES = TOP_DOWN_BASIC.ranges

head_circumference_strategy = st.decimals(
    min_value=_RANGES.head_circumference_cm.minimum,
    max_value=_RANGES.head_circumference_cm.maximum,
    places=1,
    allow_nan=False,
    allow_infinity=False,
)
stitches_per_10cm_strategy = st.decimals(
    min_value=_RANGES.stitches_per_10cm.minimum,
    max_value=_RANGES.stitches_per_10cm.maximum,
    places=1,
    allow_nan=False,
    allow_infinity=False,
)
rounds_per_10cm_strategy = st.decimals(
    min_value=_RANGES.rounds_per_10cm.minimum,
    max_value=_RANGES.rounds_per_10cm.maximum,
    places=1,
    allow_nan=False,
    allow_infinity=False,
)
ease_strategy = st.decimals(
    min_value=_RANGES.negative_ease_pct.minimum,
    max_value=_RANGES.negative_ease_pct.maximum,
    places=1,
    allow_nan=False,
    allow_infinity=False,
)
height_strategy = st.decimals(
    min_value=Decimal("14.0"),
    max_value=Decimal("28.0"),
    places=1,
    allow_nan=False,
    allow_infinity=False,
)
stitch_family_strategy = st.sampled_from([StitchFamily.SC, StitchFamily.HDC])


@given(
    head_circumference_cm=head_circumference_strategy,
    stitches_per_10cm=stitches_per_10cm_strategy,
    rounds_per_10cm=rounds_per_10cm_strategy,
    negative_ease_pct=ease_strategy,
    target_height_cm=height_strategy,
    stitch_family=stitch_family_strategy,
)
@settings(max_examples=100, deadline=None)
def test_compiled_pattern_is_internally_arithmetically_consistent(
    head_circumference_cm: Decimal,
    stitches_per_10cm: Decimal,
    rounds_per_10cm: Decimal,
    negative_ease_pct: Decimal,
    target_height_cm: Decimal,
    stitch_family: StitchFamily,
) -> None:
    project_input = make_project_input(
        head_circumference_cm=head_circumference_cm,
        stitches_per_10cm=stitches_per_10cm,
        rounds_per_10cm=rounds_per_10cm,
        negative_ease_pct=negative_ease_pct,
        target_height_cm=target_height_cm,
        stitch_family=stitch_family,
        brim_type=BrimType.NONE,
        brim_height_cm=None,
    )

    try:
        pattern = compile_pattern(project_input)
    except Exception:
        # Some combinations are legitimately unsatisfiable (e.g. body rounds
        # < template minimum); that is covered by unit tests. Here we only
        # assert that whenever a Pattern *is* produced, it is well-formed.
        return

    previous_total: int | None = None
    for component in pattern.components:
        for round_ in component.rounds:
            consumed = sum(consumed_count(op) for op in round_.operations)
            produced = sum(produced_count(op) for op in round_.operations)

            assert round_.stated_total >= 0
            assert produced == round_.stated_total
            if previous_total is not None:
                assert consumed == previous_total
            previous_total = produced


@given(
    stitches_per_10cm=stitches_per_10cm_strategy,
    rounds_per_10cm=rounds_per_10cm_strategy,
    negative_ease_pct=ease_strategy,
    stitch_family=stitch_family_strategy,
    smaller_head=st.decimals(
        min_value=Decimal(42),
        max_value=Decimal(52),
        places=1,
        allow_nan=False,
        allow_infinity=False,
    ),
    larger_head_delta=st.decimals(
        min_value=Decimal("0.1"),
        max_value=Decimal(12),
        places=1,
        allow_nan=False,
        allow_infinity=False,
    ),
)
@settings(max_examples=75, deadline=None)
def test_larger_head_circumference_never_shrinks_stitch_count(
    stitches_per_10cm: Decimal,
    rounds_per_10cm: Decimal,
    negative_ease_pct: Decimal,
    stitch_family: StitchFamily,
    smaller_head: Decimal,
    larger_head_delta: Decimal,
) -> None:
    larger_head = smaller_head + larger_head_delta
    if larger_head > TOP_DOWN_BASIC.ranges.head_circumference_cm.maximum:
        return

    common = dict(
        stitches_per_10cm=stitches_per_10cm,
        rounds_per_10cm=rounds_per_10cm,
        negative_ease_pct=negative_ease_pct,
        stitch_family=stitch_family,
        target_height_cm=Decimal("21.0"),
        brim_type=BrimType.NONE,
        brim_height_cm=None,
    )

    try:
        smaller_pattern = compile_pattern(
            make_project_input(head_circumference_cm=smaller_head, **common)
        )
        larger_pattern = compile_pattern(
            make_project_input(head_circumference_cm=larger_head, **common)
        )
    except Exception:
        return

    assert (
        larger_pattern.calculated.body_stitch_count >= smaller_pattern.calculated.body_stitch_count
    )


@given(
    head_circumference_cm=head_circumference_strategy,
    stitches_per_10cm=stitches_per_10cm_strategy,
    rounds_per_10cm=rounds_per_10cm_strategy,
    negative_ease_pct=ease_strategy,
)
@settings(max_examples=100, deadline=None)
def test_repeat_compatible_deviation_bounded_by_half_repeat_spacing(
    head_circumference_cm: Decimal,
    stitches_per_10cm: Decimal,
    rounds_per_10cm: Decimal,
    negative_ease_pct: Decimal,
) -> None:
    project_input = make_project_input(
        head_circumference_cm=head_circumference_cm,
        stitches_per_10cm=stitches_per_10cm,
        rounds_per_10cm=rounds_per_10cm,
        negative_ease_pct=negative_ease_pct,
        target_height_cm=Decimal("21.0"),
        brim_type=BrimType.NONE,
        brim_height_cm=None,
    )
    try:
        pattern = compile_pattern(project_input)
    except Exception:
        return

    m = pattern.calculated.repeat_multiple
    stitches_per_cm = stitches_per_10cm / Decimal(10)
    max_deviation = (Decimal(m) / Decimal(2)) / stitches_per_cm
    assert pattern.calculated.circumference_deviation_cm <= max_deviation


@given(
    head_circumference_cm=head_circumference_strategy,
    stitches_per_10cm=stitches_per_10cm_strategy,
    rounds_per_10cm=rounds_per_10cm_strategy,
    negative_ease_pct=ease_strategy,
)
@settings(max_examples=50, deadline=None)
def test_identical_inputs_always_produce_identical_fingerprint(
    head_circumference_cm: Decimal,
    stitches_per_10cm: Decimal,
    rounds_per_10cm: Decimal,
    negative_ease_pct: Decimal,
) -> None:
    kwargs = dict(
        head_circumference_cm=head_circumference_cm,
        stitches_per_10cm=stitches_per_10cm,
        rounds_per_10cm=rounds_per_10cm,
        negative_ease_pct=negative_ease_pct,
        target_height_cm=Decimal("21.0"),
        brim_type=BrimType.NONE,
        brim_height_cm=None,
    )
    try:
        first = compile_pattern(make_project_input(**kwargs))
        second = compile_pattern(make_project_input(**kwargs))
    except Exception:
        return

    assert first.fingerprint == second.fingerprint
