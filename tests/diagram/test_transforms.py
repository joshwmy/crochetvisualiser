"""Transform composition and viewBox normalisation: equivalent SVGs must
produce equivalent normalised coordinates, per the brief's transform-test
list (nested translate/rotate/scale/matrix, `<use>` offsets, negative
coordinates, non-zero viewBox origin).
"""

from __future__ import annotations

import math

import pytest

from crochet_reconstruction.diagram.security import DEFAULT_LIMITS
from crochet_reconstruction.diagram.svg_parser import parse_svg
from crochet_reconstruction.diagram.transforms import (
    Matrix2D,
    parse_transform_list,
    parse_viewbox,
    rotate,
    scale,
    translate,
    viewbox_normalisation_matrix,
)


def test_translate_matrix():
    m = translate(3, 4)
    assert m.apply(0, 0) == pytest.approx((3, 4))


def test_scale_matrix():
    m = scale(2, 3)
    assert m.apply(1, 1) == pytest.approx((2, 3))


def test_rotate_90_degrees():
    m = rotate(90)
    x, y = m.apply(1, 0)
    assert x == pytest.approx(0, abs=1e-9)
    assert y == pytest.approx(1, abs=1e-9)


def test_compose_order_translate_then_rotate():
    # "translate(10,0) rotate(90)" — SVG semantics: point (1,0) in local
    # coords rotates first (-> (0,1)) then translates (-> (10,1)).
    m = parse_transform_list("translate(10,0) rotate(90)", max_functions=10)
    x, y = m.apply(1, 0)
    assert x == pytest.approx(10, abs=1e-9)
    assert y == pytest.approx(1, abs=1e-9)


def test_matrix_function_direct():
    m = parse_transform_list("matrix(1,0,0,1,5,6)", max_functions=10)
    assert m.apply(0, 0) == pytest.approx((5, 6))


def test_nested_group_composition_equals_flattened_single_transform():
    """<g translate><g rotate><g scale>point</g></g></g> must equal one
    matrix built by composing the same three functions in the same order."""
    parent = translate(10, 20)
    child = rotate(45)
    grandchild = scale(2)
    composed = parent.compose(child).compose(grandchild)

    combined = parse_transform_list("translate(10,20) rotate(45) scale(2)", max_functions=10)
    assert composed.apply(3, 4) == pytest.approx(combined.apply(3, 4))


def test_negative_coordinates_transform_correctly():
    m = translate(-5, -5).compose(scale(2))
    assert m.apply(-1, -1) == pytest.approx((-7, -7))


def test_viewbox_with_nonzero_origin():
    vb = parse_viewbox("100 100 200 200")
    m = viewbox_normalisation_matrix(vb, 200, 200)
    # The viewBox's own origin (100,100) must map to normalised (0,0).
    assert m.apply(100, 100) == pytest.approx((0, 0), abs=1e-9)


def test_equivalent_svgs_produce_equivalent_normalised_coordinates():
    """A <use> with x/y offset and an equivalent inline <g translate> must
    place the same local point at the same normalised position."""
    svg_use = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
        '<defs><circle id="s" cx="0" cy="0" r="3"/></defs>'
        '<use href="#s" x="40" y="50"/>'
        "</svg>"
    )
    svg_inline = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
        '<g transform="translate(40,50)"><circle cx="0" cy="0" r="3"/></g>'
        "</svg>"
    )
    from crochet_reconstruction.diagram.extraction import extract_symbols

    doc_use, diags_use = parse_svg(svg_use, DEFAULT_LIMITS)
    doc_inline, diags_inline = parse_svg(svg_inline, DEFAULT_LIMITS)
    assert diags_use == []
    assert diags_inline == []

    # <defs>/<symbol> content is deliberately excluded from candidacy (see
    # extraction.py) — only the instantiated <use> copy is a real symbol,
    # so comparing extracted symbol positions (not raw geometry points,
    # which would also see the untransformed <defs> original) is the
    # correct equivalence check here.
    position_use = extract_symbols(doc_use.root, DEFAULT_LIMITS).symbols[0].position
    position_inline = extract_symbols(doc_inline.root, DEFAULT_LIMITS).symbols[0].position
    assert position_use == pytest.approx(position_inline)


def test_use_with_local_offset_and_symbol_definition():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
        '<symbol id="stitch"><circle cx="0" cy="0" r="2"/></symbol>'
        '<use href="#stitch" x="10" y="20"/>'
        "</svg>"
    )
    doc, diags = parse_svg(svg, DEFAULT_LIMITS)
    assert diags == []
    from crochet_reconstruction.diagram.extraction import _geometry_points

    points = _geometry_points(doc.root)
    assert any(math.isclose(x, 10, abs_tol=3) and math.isclose(y, 20, abs_tol=3) for x, y in points)


def test_combined_transform_matches_manual_composition():
    m = parse_transform_list(
        "translate(5,5) rotate(30) scale(1.5) translate(-2,0)", max_functions=10
    )
    expected = translate(5, 5).compose(rotate(30)).compose(scale(1.5)).compose(translate(-2, 0))
    assert m.apply(1, 1) == pytest.approx(expected.apply(1, 1))


def test_identity_uniform_scale_is_one():
    assert Matrix2D().uniform_scale == pytest.approx(1.0)


def test_skew_transforms_parse():
    m = parse_transform_list("skewX(30)", max_functions=10)
    x, y = m.apply(0, 1)
    assert x == pytest.approx(math.tan(math.radians(30)), abs=1e-6)
