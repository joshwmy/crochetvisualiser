"""Per-stitch-family row-height scaling.

The behaviour under test is deliberately conservative: a pattern worked
entirely in the gauge's own stitch family must lay out *exactly* as it did
before this scaling existed, and only a genuinely mixed-family pattern may
differ. Several tests below assert that "nothing changed" half explicitly,
because it is the property that keeps every existing fixture, golden file,
and geometry fingerprint valid.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

import pytest

from crochet_reconstruction.domain.enums import ComponentKind, Construction, StitchFamily
from crochet_reconstruction.domain.gauge import Gauge
from crochet_reconstruction.domain.operations import IncreaseOp, MagicRingOp, RepeatOp, StitchOp
from crochet_reconstruction.domain.rounds import Component, Round
from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.geometry.layout import build_geometry
from crochet_reconstruction.geometry.stitch_heights import (
    dominant_stitch_family,
    row_height_scale,
    scaled_row_heights,
    stitch_height_warnings,
)
from crochet_reconstruction.graph.builder import build_stitch_graph
from crochet_reconstruction.parsing.written import parse_written_pattern
from tests.conftest import make_project_input

SC_GAUGE = Gauge(
    stitch_family=StitchFamily.SC,
    stitches_per_10cm=Decimal("16.0"),
    rounds_per_10cm=Decimal("16.0"),
)

MIXED_SC_DC_PATTERN = """\
Round 1: 6 sc in magic ring [6]
Round 2: sc around [6]
Round 3: dc around [6]
Round 4: sc around [6]
"""

SINGLE_FAMILY_PATTERN = """\
Round 1: 6 sc in magic ring [6]
Round 2: sc around [6]
Round 3: sc around [6]
"""


def _round(number: int, *operations, total: int) -> Round:
    return Round(number=number, operations=list(operations), stated_total=total)


def _piece(*rounds: Round) -> Component:
    return Component(
        kind=ComponentKind.PIECE, construction=Construction.CONTINUOUS, rounds=list(rounds)
    )


def _build_from_written(source: str, gauge: Gauge = SC_GAUGE):
    components, diagnostics = parse_written_pattern(source)
    assert components is not None, diagnostics
    graph = build_stitch_graph(components)
    return components, build_geometry(components, gauge, graph)


def _round_z_values(geometry) -> list[float]:
    """One representative z per round, ordered by round index."""
    by_round: dict[int, float] = {}
    for stitch in geometry.stitches:
        by_round[stitch.round_index] = stitch.position[2]
    return [by_round[key] for key in sorted(by_round)]


class TestDominantStitchFamily:
    def test_single_family_round_returns_that_family(self):
        round_ = _round(1, StitchOp(stitch=StitchFamily.HDC, count=12), total=12)
        assert dominant_stitch_family(round_) is StitchFamily.HDC

    def test_most_produced_family_wins(self):
        round_ = _round(
            1,
            StitchOp(stitch=StitchFamily.SC, count=2),
            StitchOp(stitch=StitchFamily.DC, count=9),
            total=11,
        )
        assert dominant_stitch_family(round_) is StitchFamily.DC

    def test_tie_breaks_toward_first_appearance(self):
        round_ = _round(
            1,
            StitchOp(stitch=StitchFamily.DC, count=5),
            StitchOp(stitch=StitchFamily.SC, count=5),
            total=10,
        )
        assert dominant_stitch_family(round_) is StitchFamily.DC

    def test_repeat_multiplies_its_body(self):
        # 1 dc outside the repeat vs. 2 sc x 4 repeats = 8 sc: sc must win.
        round_ = _round(
            1,
            StitchOp(stitch=StitchFamily.DC, count=1),
            RepeatOp(times=4, body=[StitchOp(stitch=StitchFamily.SC, count=2)]),
            total=9,
        )
        assert dominant_stitch_family(round_) is StitchFamily.SC

    def test_increase_output_counts_not_input(self):
        round_ = _round(
            1,
            StitchOp(stitch=StitchFamily.SC, count=3),
            IncreaseOp(stitch=StitchFamily.DC, input=2, output=4),
            total=7,
        )
        assert dominant_stitch_family(round_) is StitchFamily.DC

    def test_magic_ring_round_is_attributed_to_its_stitch(self):
        round_ = _round(1, MagicRingOp(stitch=StitchFamily.HDC, output=6), total=6)
        assert dominant_stitch_family(round_) is StitchFamily.HDC


class TestRowHeightScale:
    def test_gauge_family_scales_by_exactly_one(self):
        for family in StitchFamily:
            assert row_height_scale(family, family) == 1.0

    def test_taller_stitch_scales_above_one(self):
        assert row_height_scale(StitchFamily.DC, StitchFamily.SC) > 1.0

    def test_shorter_stitch_scales_below_one(self):
        assert row_height_scale(StitchFamily.SC, StitchFamily.DC) < 1.0

    def test_scale_is_reciprocal_between_families(self):
        forward = row_height_scale(StitchFamily.DC, StitchFamily.HDC)
        backward = row_height_scale(StitchFamily.HDC, StitchFamily.DC)
        assert forward * backward == pytest.approx(1.0)

    def test_only_the_ratio_matters_not_the_anchor(self):
        # hdc-gauge dc and sc-gauge (dc relative to sc, halved) agree.
        assert row_height_scale(StitchFamily.DC, StitchFamily.HDC) == pytest.approx(
            row_height_scale(StitchFamily.DC, StitchFamily.SC)
            / row_height_scale(StitchFamily.HDC, StitchFamily.SC)
        )

    def test_scaled_row_heights_covers_every_round(self):
        components = [
            _piece(
                _round(1, MagicRingOp(stitch=StitchFamily.SC, output=6), total=6),
                _round(2, StitchOp(stitch=StitchFamily.DC, count=6), total=6),
            )
        ]
        heights = scaled_row_heights(components, StitchFamily.SC, 2.0)
        assert heights[("piece", 1)] == 2.0
        assert heights[("piece", 2)] > 2.0


class TestWarnings:
    def test_single_family_pattern_warns_nothing(self):
        components = [
            _piece(
                _round(1, MagicRingOp(stitch=StitchFamily.SC, output=6), total=6),
                _round(2, StitchOp(stitch=StitchFamily.SC, count=6), total=6),
            )
        ]
        assert stitch_height_warnings(components, StitchFamily.SC) == []

    def test_off_gauge_round_produces_one_warning_naming_the_family(self):
        components = [
            _piece(
                _round(1, MagicRingOp(stitch=StitchFamily.SC, output=6), total=6),
                _round(2, StitchOp(stitch=StitchFamily.DC, count=6), total=6),
            )
        ]
        warnings = stitch_height_warnings(components, StitchFamily.SC)
        assert len(warnings) == 1
        assert "dc" in warnings[0]
        assert "provisional" in warnings[0]

    def test_warning_reaches_the_geometry_document(self):
        _, geometry = _build_from_written(MIXED_SC_DC_PATTERN)
        assert any("turning-chain" in w for w in geometry.warnings)

    def test_no_new_warning_for_a_single_family_document(self):
        _, geometry = _build_from_written(SINGLE_FAMILY_PATTERN)
        assert not any("turning-chain" in w for w in geometry.warnings)


class TestLayoutIntegration:
    def test_dc_round_is_spaced_further_than_sc_rounds(self):
        _, geometry = _build_from_written(MIXED_SC_DC_PATTERN)
        z_values = _round_z_values(geometry)
        sc_gap = abs(z_values[1] - z_values[0])
        dc_gap = abs(z_values[2] - z_values[1])
        next_sc_gap = abs(z_values[3] - z_values[2])
        assert dc_gap > sc_gap
        assert next_sc_gap == pytest.approx(sc_gap)
        assert dc_gap == pytest.approx(sc_gap * row_height_scale(StitchFamily.DC, StitchFamily.SC))

    def test_single_family_spacing_is_exactly_one_round_gauge_unit(self):
        _, geometry = _build_from_written(SINGLE_FAMILY_PATTERN)
        z_values = _round_z_values(geometry)
        expected = 1.0 / float(SC_GAUGE.rounds_per_cm)
        for earlier, later in pairwise(z_values):
            assert abs(later - earlier) == pytest.approx(expected)

    def test_beanie_body_spacing_is_unchanged_by_scaling(self):
        """The hdc beanie is worked entirely in its gauge family — no drift."""
        pattern = compile_pattern(make_project_input())
        graph = build_stitch_graph(pattern.components, pattern_fingerprint=pattern.fingerprint)
        geometry = build_geometry(pattern.components, pattern.input.gauge, graph)
        expected = 1.0 / float(pattern.input.gauge.rounds_per_cm)

        body_z: dict[int, float] = {
            s.round_index: s.position[2] for s in geometry.stitches if s.component_id == "body"
        }
        ordered = [body_z[key] for key in sorted(body_z)]
        assert len(ordered) > 1
        for earlier, later in pairwise(ordered):
            assert abs(later - earlier) == pytest.approx(expected)

    def test_gauge_family_choice_changes_relative_spacing(self):
        """The same mixed pattern spaces differently under a different gauge stitch."""
        hdc_gauge = SC_GAUGE.model_copy(update={"stitch_family": StitchFamily.HDC})
        _, sc_geometry = _build_from_written(MIXED_SC_DC_PATTERN)
        _, hdc_geometry = _build_from_written(MIXED_SC_DC_PATTERN, hdc_gauge)
        assert sc_geometry.measurements.overall_height_cm != pytest.approx(
            hdc_geometry.measurements.overall_height_cm
        )
