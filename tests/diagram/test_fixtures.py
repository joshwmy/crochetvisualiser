"""Runs the committed synthetic SVG fixture corpus (tests/diagram/fixtures/svg/)
through the real analyse/compile pipeline and asserts the documented
expected behaviour for each — this is the "one file per scenario" corpus
required by the brief (magic ring, increases, explicit <use>, metadata,
nested transforms, security cases, etc).
"""

from __future__ import annotations

from crochet_reconstruction.diagram.corrections import DiagramCorrectionSet, SymbolOverride
from crochet_reconstruction.diagram.diagnostics import DiagramDiagnosticCode
from crochet_reconstruction.diagram.pipeline import analyse_svg_diagram, compile_svg_diagram
from crochet_reconstruction.geometry.layout import build_geometry
from crochet_reconstruction.graph.validation import validate_graph
from crochet_reconstruction.parsing.written.semantic import DEFAULT_WRITTEN_PATTERN_GAUGE


def _compile_ok(svg: str):
    analysis = analyse_svg_diagram(svg)
    assert analysis.document is not None, analysis.diagnostics
    result = compile_svg_diagram(analysis.document, DiagramCorrectionSet())
    assert result.compiled is not None, result.diagnostics
    validate_graph(result.compiled.graph)
    build_geometry(result.compiled.components, DEFAULT_WRITTEN_PATTERN_GAUGE, result.compiled.graph)
    return analysis, result


def test_magic_ring_6sc(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("magic_ring_6sc.svg"))
    assert analysis.summary.round_count == 1
    assert len(result.compiled.graph.nodes) == 6


def test_increase_round_6_to_12(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("increase_round_6_to_12.svg"))
    assert analysis.summary.round_count == 2
    assert sum(1 for n in result.compiled.graph.nodes if n.is_increase) == 12


def test_flat_circle_3_rounds(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("flat_circle_3_rounds.svg"))
    assert analysis.summary.round_count == 3
    counts = [sum(1 for n in result.compiled.graph.nodes if n.round_number == r) for r in (1, 2, 3)]
    assert counts == [6, 12, 18]


def test_sphere_like(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("sphere_like.svg"))
    assert analysis.summary.round_count == 4
    counts = [
        sum(1 for n in result.compiled.graph.nodes if n.round_number == r) for r in (1, 2, 3, 4)
    ]
    assert counts == [6, 12, 12, 6]
    assert any(n.is_decrease for n in result.compiled.graph.nodes)
    assert any(n.is_increase for n in result.compiled.graph.nodes)


def test_chain_ring_6sc(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("chain_ring_6sc.svg"))
    assert all(n.into_ring for n in result.compiled.graph.nodes)


def test_explicit_use_symbols(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("explicit_use_symbols.svg"))
    assert len(result.compiled.graph.nodes) == 6
    methods = {s.classification_method.value for s in analysis.document.symbols}
    assert "use_reference" in methods or "data_attribute" in methods


def test_metadata_labelled(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("metadata_labelled.svg"))
    assert len(result.compiled.graph.nodes) == 6
    methods = {s.classification_method.value for s in analysis.document.symbols}
    assert "css_class" in methods or "element_id" in methods


def test_nested_transform(fixture_svg):
    _compile_ok(fixture_svg("nested_transform.svg"))


def test_rotated_symbols(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("rotated_symbols.svg"))
    assert len(result.compiled.graph.nodes) == 6


def test_explicit_connectors(fixture_svg):
    analysis, result = _compile_ok(fixture_svg("explicit_connectors.svg"))
    centre_rels = [
        r
        for r in analysis.document.relationships
        if r.relationship_type in ("centre_attachment", "parent_attachment")
    ]
    assert all(r.inference_method == "explicit_connector" for r in centre_rels)


def test_ambiguous_symbol_blocks_until_corrected(fixture_svg):
    svg = fixture_svg("ambiguous_symbol.svg")
    analysis = analyse_svg_diagram(svg)
    assert analysis.document is not None
    assert analysis.summary.ready_to_compile is False
    ambiguous = next(s for s in analysis.document.symbols if s.ambiguous)

    blocked = compile_svg_diagram(analysis.document, DiagramCorrectionSet())
    assert blocked.compiled is None

    corrections = DiagramCorrectionSet(
        symbol_overrides={ambiguous.symbol_id: SymbolOverride(stitch_type="single_crochet")}
    )
    unblocked = compile_svg_diagram(analysis.document, corrections)
    assert unblocked.compiled is not None


def test_unclassified_symbol_blocks_until_corrected(fixture_svg):
    svg = fixture_svg("unclassified_symbol.svg")
    analysis = analyse_svg_diagram(svg)
    assert analysis.document is not None
    mystery = next(s for s in analysis.document.symbols if s.source_element_id == "mystery")
    assert mystery.stitch_type is None

    blocked = compile_svg_diagram(analysis.document, DiagramCorrectionSet())
    assert blocked.compiled is None
    codes = [d.code for d in blocked.diagnostics]
    assert DiagramDiagnosticCode.UNCLASSIFIED_SYMBOL in codes

    corrections = DiagramCorrectionSet(
        symbol_overrides={mystery.symbol_id: SymbolOverride(stitch_type="single_crochet")}
    )
    unblocked = compile_svg_diagram(analysis.document, corrections)
    assert unblocked.compiled is not None


def test_missing_centre(fixture_svg):
    analysis = analyse_svg_diagram(fixture_svg("missing_centre.svg"))
    assert analysis.document is not None
    codes = [d.code for d in analysis.diagnostics]
    assert DiagramDiagnosticCode.MISSING_CENTRE in codes
    assert analysis.summary.ready_to_compile is False


def test_disconnected_chart_produces_ambiguous_centre(fixture_svg):
    analysis = analyse_svg_diagram(fixture_svg("disconnected_chart.svg"))
    assert analysis.document is not None
    codes = [d.code for d in analysis.diagnostics]
    assert DiagramDiagnosticCode.AMBIGUOUS_CENTRE in codes


def test_invalid_decrease_flags_non_adjacent_parents(fixture_svg):
    analysis = analyse_svg_diagram(fixture_svg("invalid_decrease.svg"))
    assert analysis.document is not None
    result = compile_svg_diagram(analysis.document, DiagramCorrectionSet())
    if result.compiled is not None:
        codes = [d.code for d in result.diagnostics]
        assert DiagramDiagnosticCode.NON_ADJACENT_DECREASE_PARENTS in codes


def test_malicious_script_is_rejected(fixture_svg):
    analysis = analyse_svg_diagram(fixture_svg("malicious_script.svg"))
    assert analysis.document is None
    assert analysis.diagnostics[0].code == DiagramDiagnosticCode.UNSAFE_SVG_CONTENT


def test_external_reference_is_rejected(fixture_svg):
    analysis = analyse_svg_diagram(fixture_svg("external_reference.svg"))
    assert analysis.document is None
    assert analysis.diagnostics[0].code == DiagramDiagnosticCode.UNSUPPORTED_EXTERNAL_REFERENCE


def test_excessive_complexity_is_rejected(fixture_svg):
    analysis = analyse_svg_diagram(fixture_svg("excessive_complexity.svg"))
    assert analysis.document is None
    assert analysis.diagnostics[0].code in (
        DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
        DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE,
    )


def test_every_fixture_is_exercised(fixture_svg):
    """Guards against a fixture file being added without a corresponding
    test (or silently going stale) — lists the whole directory and checks
    every .svg file was loaded by at least one test above via a shared
    accounting set populated as a side effect is too fragile; instead this
    just asserts the expected fixture count, which fails loudly if the
    corpus size changes without this file being updated."""
    from pathlib import Path

    svg_dir = Path(__file__).parent / "fixtures" / "svg"
    fixture_files = sorted(p.name for p in svg_dir.glob("*.svg"))
    assert len(fixture_files) == 18
