"""Deterministic compiler: ``ProjectInput`` → validated ``Pattern``.

Orchestrates sizing → crown → body → brim → structured assembly →
validation → canonical fingerprint, per the required pipeline
(decision package §9, FR-09; §14 "Compiler"). Never renders text — that is
:mod:`crochet_reconstruction.rendering.text_renderer`'s job, and only after
this module's caller confirms no fatal validation result exists.
"""

from __future__ import annotations

import hashlib
import json

from crochet_reconstruction.domain.enums import AssumptionSource, ComponentKind, Construction
from crochet_reconstruction.domain.errors import UnsupportedConstructionError
from crochet_reconstruction.domain.pattern import (
    Assumption,
    CalculatedParameters,
    Pattern,
    ProjectInput,
)
from crochet_reconstruction.domain.rounds import Component
from crochet_reconstruction.engine import body as body_engine
from crochet_reconstruction.engine import brim as brim_engine
from crochet_reconstruction.engine import crown as crown_engine
from crochet_reconstruction.engine import sizing
from crochet_reconstruction.templates.base import BeanieTemplate
from crochet_reconstruction.templates.top_down_beanie import get_template
from crochet_reconstruction.validation.validator import validate


def _check_template_support(input: ProjectInput, template: BeanieTemplate) -> None:
    if input.construction not in template.supported_constructions:
        raise UnsupportedConstructionError(
            f"construction {input.construction.value!r} is not supported by "
            f"template {template.id}@{template.version}; supported: "
            f"{[c.value for c in template.supported_constructions]}"
        )
    if input.gauge.stitch_family not in template.supported_stitch_families:
        raise UnsupportedConstructionError(
            f"stitch family {input.gauge.stitch_family.value!r} is not supported "
            f"by template {template.id}@{template.version}"
        )
    if input.brim_type not in template.supported_brim_types:
        raise UnsupportedConstructionError(
            f"brim type {input.brim_type.value!r} is not supported by template "
            f"{template.id}@{template.version}"
        )


def compile_pattern(input: ProjectInput) -> Pattern:
    """Compile validated user input into a fully validated, fingerprinted Pattern.

    Raises a domain error (:mod:`crochet_reconstruction.domain.errors`) if the
    template does not support the requested construction/stitch/brim, or if
    no repeat-compatible sizing exists within the template's dimensional
    bounds. Returns a ``Pattern`` in all other cases — including cases with
    fatal validation results, which the caller must check via
    ``pattern.validation.has_fatal`` before rendering or exporting.
    """
    template = get_template(input.template.id, input.template.version)
    _check_template_support(input, template)

    stitch_family = input.gauge.stitch_family
    stitches_per_cm = input.gauge.stitches_per_cm
    rounds_per_cm = input.gauge.rounds_per_cm

    target_circumference = sizing.target_circumference_cm(
        input.measurements.head_circumference_cm, input.negative_ease_pct
    )
    diameter = crown_engine.crown_diameter_cm(target_circumference)

    increases_per_round = crown_engine.estimate_increases_per_round(
        stitches_per_cm, rounds_per_cm, template
    )

    raw_count = sizing.stitches_from_circumference(target_circumference, stitches_per_cm)
    repeat_result = sizing.repeat_compatible_count(
        raw_count, increases_per_round, stitches_per_cm, target_circumference
    )
    body_stitch_count = repeat_result.chosen

    crown_rounds = crown_engine.build_crown_rounds(
        body_stitch_count, increases_per_round, stitch_family
    )
    crown_round_count = len(crown_rounds)

    total_rounds_for_height = sizing.rounds_from_height(
        input.measurements.target_height_cm, rounds_per_cm
    )
    brim_round_count = brim_engine.brim_round_count(
        input.brim_type, input.measurements.brim_height_cm, rounds_per_cm
    )
    body_round_count = body_engine.body_round_count(
        total_rounds_for_height, crown_round_count, brim_round_count, template
    )

    body_rounds = body_engine.build_body_rounds(
        crown_round_count + 1, body_round_count, body_stitch_count, stitch_family
    )
    brim_rounds = brim_engine.build_brim_rounds(
        crown_round_count + body_round_count + 1,
        brim_round_count,
        body_stitch_count,
        stitch_family,
        input.brim_type,
    )

    components = [
        Component(
            kind=ComponentKind.CROWN, construction=Construction.CONTINUOUS, rounds=crown_rounds
        ),
        Component(
            kind=ComponentKind.BODY, construction=Construction.CONTINUOUS, rounds=body_rounds
        ),
    ]
    if brim_rounds:
        components.append(
            Component(
                kind=ComponentKind.BRIM, construction=Construction.CONTINUOUS, rounds=brim_rounds
            )
        )

    calculated = CalculatedParameters(
        target_circumference_cm=target_circumference,
        crown_diameter_cm=diameter,
        body_stitch_count_raw=raw_count,
        body_stitch_count=body_stitch_count,
        repeat_multiple=increases_per_round,
        circumference_deviation_cm=repeat_result.deviation_cm,
        total_rounds_for_height=total_rounds_for_height,
        crown_round_count=crown_round_count,
        body_round_count=body_round_count,
        brim_round_count=brim_round_count,
        starting_stitch_count=increases_per_round,
    )

    assumptions = [
        Assumption(
            id="a-body-stitch",
            field="gauge.stitch_family",
            value=stitch_family.value,
            source=AssumptionSource.USER_CONFIRMED,
        ),
        Assumption(
            id="a-construction",
            field="construction",
            value=input.construction.value,
            source=AssumptionSource.USER_CONFIRMED,
        ),
        Assumption(
            id="a-negative-ease",
            field="negative_ease_pct",
            value=str(input.negative_ease_pct),
            source=AssumptionSource.USER_CONFIRMED,
        ),
        Assumption(
            id="a-target-circumference",
            field="calculated.target_circumference_cm",
            value=str(target_circumference),
            source=AssumptionSource.DERIVED,
            note="C_t = H * (1 - ease); see docs/mathematical-assumptions.md",
        ),
        Assumption(
            id="a-increases-per-round",
            field="calculated.repeat_multiple",
            value=str(increases_per_round),
            source=AssumptionSource.DERIVED,
            note="Nearest template-approved schedule to k = 2*pi*g_s/g_r",
        ),
    ]

    pattern = Pattern(
        input=input,
        calculated=calculated,
        assumptions=assumptions,
        components=components,
        validation=None,
        fingerprint=None,
    )

    report = validate(pattern, template)
    pattern = pattern.model_copy(update={"validation": report})

    fingerprint = _fingerprint(pattern)
    pattern = pattern.model_copy(update={"fingerprint": fingerprint})
    return pattern


def canonical_json(pattern: Pattern) -> str:
    """Canonical, whitespace-minimal, key-sorted JSON of a pattern (sans fingerprint).

    Used both to compute the fingerprint and as the ``--output`` structured
    export. Identical ``Pattern`` content always produces identical bytes.
    """
    data = pattern.model_dump(mode="json", exclude={"fingerprint"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(pattern: Pattern) -> str:
    digest = hashlib.sha256(canonical_json(pattern).encode("utf-8"))
    return digest.hexdigest()
