"""Secure SVG parsing: disallowed content, external references, and every
numeric safety limit — each must fail with a structured diagnostic, never
raise or hang.
"""

from __future__ import annotations

from dataclasses import replace

from crochet_reconstruction.diagram.diagnostics import DiagramDiagnosticCode
from crochet_reconstruction.diagram.security import DEFAULT_LIMITS
from crochet_reconstruction.diagram.svg_parser import parse_svg


def _wrap(body: str, **attrs: str) -> str:
    width = attrs.get("width", "100")
    height = attrs.get("height", "100")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">{body}</svg>'
    )


def test_rejects_script_tag():
    doc, diags = parse_svg(_wrap("<script>alert(1)</script>"), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_foreign_object():
    doc, diags = parse_svg(_wrap("<foreignObject><p>hi</p></foreignObject>"), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_inline_event_handler():
    doc, diags = parse_svg(_wrap('<circle r="5" onclick="alert(1)"/>'), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_javascript_url():
    doc, diags = parse_svg(
        _wrap('<a href="javascript:alert(1)"><circle r="5"/></a>'), DEFAULT_LIMITS
    )
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_css_url_reference():
    doc, diags = parse_svg(
        _wrap('<circle r="5" style="fill:url(http://evil.example/x.png)"/>'), DEFAULT_LIMITS
    )
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_external_use_reference():
    doc, diags = parse_svg(
        _wrap('<use href="http://evil.example/symbols.svg#sc"/>'), DEFAULT_LIMITS
    )
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSUPPORTED_EXTERNAL_REFERENCE


def test_rejects_remote_image():
    doc, diags = parse_svg(_wrap('<image href="http://evil.example/x.png"/>'), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_external_stylesheet_link():
    doc, diags = parse_svg(_wrap('<link href="http://evil.example/x.css"/>'), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_dtd_declaration():
    malicious = (
        '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        "<title>&xxe;</title></svg>"
    )
    doc, diags = parse_svg(malicious, DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_animation_elements():
    doc, diags = parse_svg(
        _wrap('<circle r="5"><animate attributeName="r" to="10"/></circle>'), DEFAULT_LIMITS
    )
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_rejects_malformed_xml():
    doc, diags = parse_svg("<svg><circle r=5></svg>", DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.INVALID_SVG


def test_rejects_non_svg_root():
    doc, diags = parse_svg("<html><body>hi</body></html>", DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.INVALID_SVG


def test_rejects_missing_viewbox_and_dimensions():
    doc, diags = parse_svg("<svg xmlns='http://www.w3.org/2000/svg'></svg>", DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.INVALID_SVG


def test_accepts_clean_minimal_svg():
    doc, diags = parse_svg(_wrap('<circle cx="5" cy="5" r="2"/>'), DEFAULT_LIMITS)
    assert doc is not None
    assert diags == []


def test_source_byte_limit():
    limits = replace(DEFAULT_LIMITS, max_source_bytes=50)
    doc, diags = parse_svg(_wrap('<circle cx="5" cy="5" r="2"/>'), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.SOURCE_TOO_LARGE


def test_element_count_limit():
    limits = replace(DEFAULT_LIMITS, max_element_count=5)
    doc, diags = parse_svg(_wrap("<g></g>" * 10), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.TOO_MANY_ELEMENTS


def test_nesting_depth_limit():
    limits = replace(DEFAULT_LIMITS, max_nesting_depth=3)
    nested = "<g>" * 10 + "</g>" * 10
    doc, diags = parse_svg(_wrap(nested), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE


def test_deep_nesting_fails_cleanly_not_recursion_error():
    """Regression: `_index_ids` used to recurse without any bound and crash
    with a Python ``RecursionError`` (an unhandled crash, not a
    diagnostic) before the element-count/depth walk ever got a chance to
    reject the document. See svg_parser.py's `_index_ids` docstring."""
    nested = "<g>" * 3000 + "</g>" * 3000
    doc, diags = parse_svg(_wrap(nested), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code in (
        DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE,
        DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
    )


def test_path_command_limit():
    limits = replace(DEFAULT_LIMITS, max_path_commands_per_element=3)
    doc, diags = parse_svg(_wrap('<path d="M0,0 L1,1 L2,2 L3,3 L4,4"/>'), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE


def test_text_node_size_limit():
    limits = replace(DEFAULT_LIMITS, max_text_node_chars=5)
    doc, diags = parse_svg(_wrap("<g><title>this is way too long</title></g>"), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE


def test_use_reference_count_limit():
    limits = replace(DEFAULT_LIMITS, max_use_references=2)
    body = '<defs><circle id="s" r="1"/></defs>' + '<use href="#s"/>' * 5
    doc, diags = parse_svg(_wrap(body), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.TOO_MANY_ELEMENTS


def test_transform_function_count_limit():
    limits = replace(DEFAULT_LIMITS, max_transform_nesting=2)
    body = '<circle r="1" transform="translate(1,1) rotate(1) scale(1) translate(2,2)"/>'
    doc, diags = parse_svg(_wrap(body), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.TRANSFORM_FAILURE


def test_coordinate_magnitude_limit():
    limits = replace(DEFAULT_LIMITS, max_coordinate_magnitude=1000)
    doc, diags = parse_svg(_wrap('<circle cx="999999999" cy="0" r="1"/>'), limits)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE


def test_viewbox_dimension_limit():
    limits = replace(DEFAULT_LIMITS, max_viewbox_dimension=100)
    doc, diags = parse_svg(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" '
        'viewBox="0 0 999999 999999"><circle r="1"/></svg>',
        limits,
    )
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.INVALID_SVG


def test_use_referencing_unknown_id_is_rejected():
    doc, diags = parse_svg(_wrap('<use href="#nope"/>'), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.INVALID_SVG


def test_cyclic_use_reference_is_rejected():
    body = (
        '<defs><g id="a"><use href="#b"/></g><g id="b"><use href="#a"/></g></defs><use href="#a"/>'
    )
    doc, diags = parse_svg(_wrap(body), DEFAULT_LIMITS)
    assert doc is None
    assert diags[0].code == DiagramDiagnosticCode.TRANSFORM_FAILURE


def test_duplicate_element_id_is_rejected_downstream():
    from crochet_reconstruction.diagram.extraction import extract_symbols

    body = (
        '<g id="dup" data-stitch-type="single_crochet"></g>'
        '<g id="dup" data-stitch-type="single_crochet"></g>'
    )
    doc, diags = parse_svg(_wrap(body), DEFAULT_LIMITS)
    assert doc is not None
    result = extract_symbols(doc.root, DEFAULT_LIMITS)
    codes = [d.code for d in result.diagnostics]
    assert DiagramDiagnosticCode.DUPLICATE_SYMBOL_ID in codes
