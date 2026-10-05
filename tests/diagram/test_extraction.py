"""Symbol extraction: classification priority order, confidence, stable
IDs, and the bounded primitive-geometry heuristic.
"""

from __future__ import annotations

from crochet_reconstruction.diagram.extraction import extract_symbols
from crochet_reconstruction.diagram.ontology import ClassificationMethod, DiagramStitchType
from crochet_reconstruction.diagram.security import DEFAULT_LIMITS
from crochet_reconstruction.diagram.svg_parser import parse_svg


def _extract(body: str):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        f"{body}</svg>"
    )
    doc, diags = parse_svg(svg, DEFAULT_LIMITS)
    assert doc is not None, diags
    return extract_symbols(doc.root, DEFAULT_LIMITS)


def test_data_attribute_has_highest_priority_over_conflicting_class():
    result = _extract('<g data-stitch-type="double_crochet" class="single-crochet"></g>')
    assert result.symbols[0].stitch_type == DiagramStitchType.DOUBLE_CROCHET
    assert result.symbols[0].classification_method == ClassificationMethod.DATA_ATTRIBUTE
    assert result.symbols[0].confidence == 1.0


def test_use_reference_beats_own_id_and_class():
    body = (
        '<defs><g id="dc"><path d="M0,-4 L0,4 M-4,-2 L4,-2 M-4,0 L4,0"/></g></defs>'
        '<use href="#dc" id="single-crochet" class="half-double-crochet"/>'
    )
    result = _extract(body)
    assert result.symbols[0].stitch_type == DiagramStitchType.DOUBLE_CROCHET
    assert result.symbols[0].classification_method == ClassificationMethod.USE_REFERENCE


def test_element_id_beats_class():
    result = _extract('<g id="double_crochet" class="single-crochet"></g>')
    assert result.symbols[0].stitch_type == DiagramStitchType.DOUBLE_CROCHET
    assert result.symbols[0].classification_method == ClassificationMethod.ELEMENT_ID


def test_css_class_beats_title():
    result = _extract('<g class="single-crochet"><title>double_crochet</title></g>')
    assert result.symbols[0].stitch_type == DiagramStitchType.SINGLE_CROCHET
    assert result.symbols[0].classification_method == ClassificationMethod.CSS_CLASS


def test_title_beats_aria_label():
    result = _extract('<g aria-label="double_crochet"><title>single_crochet</title></g>')
    assert result.symbols[0].stitch_type == DiagramStitchType.SINGLE_CROCHET
    assert result.symbols[0].classification_method == ClassificationMethod.TITLE


def test_aria_label_beats_geometry_heuristic():
    result = _extract('<path aria-label="double_crochet" d="M0,-4 L0,4"/>')
    assert result.symbols[0].stitch_type == DiagramStitchType.DOUBLE_CROCHET
    assert result.symbols[0].classification_method == ClassificationMethod.ARIA_LABEL


def test_short_alias_tokens_are_accepted():
    result = _extract('<g data-stitch-type="dc"></g>')
    assert result.symbols[0].stitch_type == DiagramStitchType.DOUBLE_CROCHET


def test_geometry_classifies_chain_from_circle():
    result = _extract('<circle cx="10" cy="10" r="4"/>')
    assert result.symbols[0].stitch_type == DiagramStitchType.CHAIN
    assert result.symbols[0].classification_method == ClassificationMethod.PRIMITIVE_GEOMETRY
    assert result.symbols[0].confidence == 0.7


def test_geometry_classifies_slip_stitch_from_short_stroke():
    result = _extract('<path d="M99,99 L101,101"/>')
    assert result.symbols[0].stitch_type == DiagramStitchType.SLIP_STITCH


def test_geometry_classifies_single_crochet_from_centred_cross():
    result = _extract('<path d="M0,-4 L0,4 M-4,0 L4,0"/>')
    assert result.symbols[0].stitch_type == DiagramStitchType.SINGLE_CROCHET


def test_geometry_classifies_half_double_crochet_from_top_biased_t():
    result = _extract('<path d="M0,-4 L0,4 M-3,-3 L3,-3"/>')
    assert result.symbols[0].stitch_type == DiagramStitchType.HALF_DOUBLE_CROCHET


def test_geometry_classifies_double_crochet_from_two_crossbars():
    result = _extract('<path d="M0,-4 L0,4 M-3,-2 L3,-2 M-3,1 L3,1"/>')
    assert result.symbols[0].stitch_type == DiagramStitchType.DOUBLE_CROCHET


def test_geometry_never_overrides_explicit_metadata():
    """A symbol shaped like a cross but explicitly labelled dc must stay dc
    — the brief's "never let a low-confidence heuristic override explicit
    metadata" invariant."""
    result = _extract('<path data-stitch-type="double_crochet" d="M0,-4 L0,4 M-4,0 L4,0"/>')
    assert result.symbols[0].stitch_type == DiagramStitchType.DOUBLE_CROCHET
    assert result.symbols[0].classification_method == ClassificationMethod.DATA_ATTRIBUTE


def test_ambiguous_shape_reports_multiple_candidates():
    # Off-axis two-stroke crossing that lands near neither stroke's own
    # midpoint (not a centred cross) and has no axis-aligned stroke (not a
    # clean top-biased T either).
    result = _extract('<path d="M-4,-4 L4,-1 M-4,2 L4,-4"/>')
    symbol = result.symbols[0]
    assert symbol.stitch_type is None
    assert symbol.ambiguous is True
    assert len(symbol.candidate_stitch_types) >= 2


def test_unrecognisable_shape_is_unclassified():
    result = _extract('<rect x="10" y="10" width="40" height="40"/>')
    symbol = result.symbols[0]
    assert symbol.stitch_type is None
    assert symbol.ambiguous is False
    assert symbol.unsupported is False


def test_reserved_future_symbol_is_unsupported_not_silently_mapped():
    result = _extract('<g data-stitch-type="treble_crochet"></g>')
    symbol = result.symbols[0]
    assert symbol.stitch_type is None
    assert symbol.unsupported is True


def test_unknown_data_stitch_type_token_is_unclassified():
    result = _extract('<g data-stitch-type="star-stitch-deluxe"></g>')
    symbol = result.symbols[0]
    assert symbol.stitch_type is None
    assert symbol.unsupported is False


def test_symbol_ids_are_stable_and_deterministic_across_reanalysis():
    body = '<g data-stitch-type="single_crochet"></g><g data-stitch-type="double_crochet"></g>'
    first = _extract(body)
    second = _extract(body)
    assert [s.symbol_id for s in first.symbols] == [s.symbol_id for s in second.symbols]
    assert first.symbols[0].symbol_id != first.symbols[1].symbol_id


def test_defs_content_is_not_double_counted_as_a_symbol():
    body = (
        '<defs><g id="symbol-sc" data-stitch-type="single_crochet"></g></defs>'
        '<use href="#symbol-sc"/>'
    )
    result = _extract(body)
    assert len(result.symbols) == 1


def test_connector_element_is_not_treated_as_a_symbol():
    body = '<line class="connector" x1="0" y1="0" x2="10" y2="10"/>'
    result = _extract(body)
    assert result.symbols == []
    assert len(result.connectors) == 1


def test_data_round_metadata_is_captured():
    result = _extract('<g data-stitch-type="single_crochet" data-round="3"></g>')
    assert result.symbols[0].source_metadata.get("data-round") == "3"


def test_symbol_candidate_limit_is_enforced():
    from dataclasses import replace

    limits = replace(DEFAULT_LIMITS, max_symbol_candidates=2)
    body = "".join(f'<g data-stitch-type="single_crochet" id="s{i}"></g>' for i in range(5))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">{body}</svg>'
    doc, diags = parse_svg(svg, limits)
    assert doc is not None
    result = extract_symbols(doc.root, limits)
    assert len(result.symbols) == 2
    from crochet_reconstruction.diagram.diagnostics import DiagramDiagnosticCode

    assert any(d.code == DiagramDiagnosticCode.TOO_MANY_ELEMENTS for d in result.diagnostics)
