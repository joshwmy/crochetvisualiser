"""Text-label association (classification priority #7).

Most of these test the association rules directly, because the interesting
behaviour is what the rules *refuse* to do: every rejection must fall through
to the next classification method rather than producing a guess.
"""

from __future__ import annotations

import pytest

from crochet_reconstruction.diagram.ontology import ClassificationMethod, DiagramStitchType
from crochet_reconstruction.diagram.pipeline import analyse_svg_diagram
from crochet_reconstruction.diagram.security import SafetyLimits
from crochet_reconstruction.diagram.svg_parser import parse_svg
from crochet_reconstruction.diagram.text_labels import (
    AMBIGUITY_SEPARATION_RATIO,
    MAX_DISTANCE_BBOX_DIAGONALS,
    LabelCandidate,
    TextLabel,
    associate_text_labels,
    collect_text_labels,
)
from tests.diagram.conftest import load_fixture


def _label(stitch_type: DiagramStitchType, position: tuple[float, float]) -> TextLabel:
    return TextLabel(
        stitch_type=stitch_type,
        raw_text=stitch_type.value,
        position=position,
        element_path="/svg/text",
    )


def _candidate(anchor: tuple[float, float], size: float = 10.0) -> LabelCandidate:
    half = size / 2
    return LabelCandidate(
        anchor=anchor,
        bbox=(anchor[0] - half, anchor[1] - half, anchor[0] + half, anchor[1] + half),
    )


class TestCollectTextLabels:
    def _labels_of(self, svg: str) -> list[TextLabel]:
        document, diagnostics = parse_svg(svg, SafetyLimits())
        assert document is not None, diagnostics
        return collect_text_labels(document.root)

    def test_collects_a_text_naming_a_stitch_type(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<text x="10" y="20">dc</text></svg>'
        )
        labels = self._labels_of(svg)
        assert len(labels) == 1
        assert labels[0].stitch_type is DiagramStitchType.DOUBLE_CROCHET

    def test_accepts_aliases_and_is_case_insensitive(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<text x="10" y="20">HDC</text></svg>'
        )
        assert self._labels_of(svg)[0].stitch_type is DiagramStitchType.HALF_DOUBLE_CROCHET

    @pytest.mark.parametrize("content", ["3", "18 sts", "Round 4", "Chart A", ""])
    def test_ignores_text_that_names_no_stitch_type(self, content):
        """Round numbers, stitch counts and titles are not labels. They are
        dropped here rather than parsed — seeding round numbering from a
        chart's own printed labels is a separate, unimplemented gap."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            f'<text x="10" y="20">{content}</text></svg>'
        )
        assert self._labels_of(svg) == []

    def test_position_is_the_composed_transform_not_the_raw_attribute(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<g transform="translate(50,60)"><text x="10" y="20">sc</text></g></svg>'
        )
        assert self._labels_of(svg)[0].position == pytest.approx((60.0, 80.0))


class TestAssociationRules:
    def test_associates_a_single_nearby_label(self):
        candidates = [_candidate((0, 0))]
        labels = [_label(DiagramStitchType.DOUBLE_CROCHET, (5, 0))]
        assert associate_text_labels(candidates, labels) == {0: labels[0]}

    def test_rejects_a_label_beyond_the_range_limit(self):
        candidates = [_candidate((0, 0), size=10.0)]
        diagonal = (10.0**2 + 10.0**2) ** 0.5
        just_too_far = diagonal * MAX_DISTANCE_BBOX_DIAGONALS + 1
        assert (
            associate_text_labels(candidates, [_label(DiagramStitchType.CHAIN, (just_too_far, 0))])
            == {}
        )

    def test_range_limit_scales_with_the_symbol(self):
        """A big symbol reaches further, so the same layout works at any chart
        scale — the limit is in multiples of the symbol's own diagonal."""
        # 25 units away: beyond a 10-unit symbol's reach (diagonal 14.1 x 1.5
        # = 21.2) but well inside a 40-unit symbol's (56.6 x 1.5 = 84.9).
        far_label = [_label(DiagramStitchType.CHAIN, (25, 0))]
        assert associate_text_labels([_candidate((0, 0), size=10.0)], far_label) == {}
        assert associate_text_labels([_candidate((0, 0), size=40.0)], far_label) != {}

    def test_a_label_between_two_symbols_classifies_neither(self):
        """The mutual-nearest guard: an equidistant label is evidence for
        nothing, so both symbols fall through rather than both claiming it."""
        candidates = [_candidate((-5, 0)), _candidate((5, 0))]
        labels = [_label(DiagramStitchType.SINGLE_CROCHET, (0, 0))]
        assert associate_text_labels(candidates, labels) == {}

    def test_two_labels_equidistant_from_one_symbol_classify_nothing(self):
        candidates = [_candidate((0, 0))]
        labels = [
            _label(DiagramStitchType.SINGLE_CROCHET, (-5, 0)),
            _label(DiagramStitchType.DOUBLE_CROCHET, (5, 0)),
        ]
        assert associate_text_labels(candidates, labels) == {}

    def test_a_clear_winner_still_associates_when_a_runner_up_exists(self):
        candidates = [_candidate((0, 0))]
        labels = [
            _label(DiagramStitchType.DOUBLE_CROCHET, (2, 0)),
            _label(
                DiagramStitchType.SINGLE_CROCHET,
                (2 * AMBIGUITY_SEPARATION_RATIO + 1, 0),
            ),
        ]
        assert associate_text_labels(candidates, labels) == {0: labels[0]}

    def test_a_zero_area_symbol_can_never_be_labelled(self):
        """No size means no meaningful search radius, so no association —
        rather than falling back to an absolute distance the chart's scale
        would make arbitrary."""
        degenerate = [LabelCandidate(anchor=(0, 0), bbox=(0, 0, 0, 0))]
        assert associate_text_labels(degenerate, [_label(DiagramStitchType.CHAIN, (0, 0))]) == {}

    def test_empty_inputs_are_handled(self):
        assert associate_text_labels([], [_label(DiagramStitchType.CHAIN, (0, 0))]) == {}
        assert associate_text_labels([_candidate((0, 0))], []) == {}


class TestPipelineIntegration:
    @pytest.fixture
    def analysis(self):
        return analyse_svg_diagram(load_fixture("text_labelled.svg"))

    def test_text_label_overrides_the_geometry_heuristic(self, analysis):
        """Every symbol in the fixture is a centred cross, which the geometry
        heuristic reads as single_crochet — the "dc" labels must win."""
        labelled = [
            s
            for s in analysis.document.symbols
            if s.classification_method is ClassificationMethod.TEXT_LABEL
        ]
        assert len(labelled) == 6
        assert all(s.stitch_type is DiagramStitchType.DOUBLE_CROCHET for s in labelled)

    def test_declared_metadata_still_outranks_a_text_label(self, analysis):
        centre = analysis.document.symbols[0]
        assert centre.classification_method is ClassificationMethod.ELEMENT_ID
        assert centre.stitch_type is DiagramStitchType.MAGIC_RING

    def test_labelled_chart_analyses_as_ready_to_compile(self, analysis):
        assert analysis.summary.ready_to_compile is True

    def test_no_unclassified_or_ambiguous_diagnostics(self, analysis):
        blocking = [d for d in analysis.diagnostics if d.severity == "error"]
        assert blocking == []

    def test_symbol_ids_stay_in_document_order(self, analysis):
        """The two-phase extraction must not renumber symbols."""
        ids = [s.symbol_id for s in analysis.document.symbols]
        assert ids == [f"svg-symbol-{i}" for i in range(len(ids))]

    def test_association_is_deterministic_across_runs(self):
        svg = load_fixture("text_labelled.svg")
        first = analyse_svg_diagram(svg).document
        second = analyse_svg_diagram(svg).document
        assert [s.stitch_type for s in first.symbols] == [s.stitch_type for s in second.symbols]
