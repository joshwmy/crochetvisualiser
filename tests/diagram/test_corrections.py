"""Manual corrections: symbol/relationship/construction overrides, their
documented application order, conflict diagnostics, and determinism.
"""

from __future__ import annotations

import math

from crochet_reconstruction.diagram.corrections import (
    ConstructionOverrides,
    DiagramCorrectionSet,
    RelationshipOverride,
    RelationshipOverrideAction,
    SymbolOverride,
)
from crochet_reconstruction.diagram.diagnostics import DiagramDiagnosticCode
from crochet_reconstruction.diagram.pipeline import analyse_svg_diagram, compile_svg_diagram


def _ring_svg(counts: list[int], radii: list[float], cx=200.0, cy=200.0) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">',
        f'<g id="ring" data-stitch-type="magic_ring" transform="translate({cx},{cy})"><circle r="8"/></g>',
    ]
    for count, radius in zip(counts, radii, strict=True):
        for i in range(count):
            angle = 2 * math.pi * i / count
            x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
            parts.append(
                f'<g data-stitch-type="single_crochet" transform="translate({x:.4f},{y:.4f})"></g>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _unclassified_document():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        '<g id="ring" data-stitch-type="magic_ring" transform="translate(100,100)"><circle r="5"/></g>'
        '<rect id="mystery" x="115" y="95" width="10" height="10"/>'
        '<g data-stitch-type="single_crochet" transform="translate(115,130)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(85,130)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(70,100)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(85,70)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(115,70)"></g>'
        "</svg>"
    )
    return analyse_svg_diagram(svg).document


def test_compile_blocked_by_unresolved_symbol():
    document = _unclassified_document()
    result = compile_svg_diagram(document, DiagramCorrectionSet())
    assert result.compiled is None
    codes = [d.code for d in result.diagnostics]
    assert DiagramDiagnosticCode.UNCLASSIFIED_SYMBOL in codes


def test_symbol_type_correction_unblocks_compile():
    document = _unclassified_document()
    mystery_id = [s.symbol_id for s in document.symbols if s.source_element_id == "mystery"][0]
    corrections = DiagramCorrectionSet(
        symbol_overrides={mystery_id: SymbolOverride(stitch_type="single_crochet")}
    )
    result = compile_svg_diagram(document, corrections)
    assert result.compiled is not None
    assert len(result.compiled.graph.nodes) == 6
    corrected_symbol = next(s for s in result.document.symbols if s.symbol_id == mystery_id)
    assert corrected_symbol.user_override is True
    assert corrected_symbol.confidence_band == "manual"


def test_ignored_symbol_is_excluded_from_compiled_graph():
    document = _unclassified_document()
    mystery_id = [s.symbol_id for s in document.symbols if s.source_element_id == "mystery"][0]
    corrections = DiagramCorrectionSet(symbol_overrides={mystery_id: SymbolOverride(ignored=True)})
    result = compile_svg_diagram(document, corrections)
    assert result.compiled is not None
    assert len(result.compiled.graph.nodes) == 5


def test_symbol_override_referencing_unknown_id_is_a_conflict():
    document = _unclassified_document()
    corrections = DiagramCorrectionSet(
        symbol_overrides={"svg-symbol-999": SymbolOverride(stitch_type="single_crochet")}
    )
    result = compile_svg_diagram(document, corrections)
    codes = [d.code for d in result.diagnostics]
    assert DiagramDiagnosticCode.MANUAL_CORRECTION_CONFLICT in codes


def test_relationship_set_parent_override():
    """Force a round-2 stitch onto a *different* round-1 parent than
    radial-projection would naturally pick, and confirm the compiled graph
    reflects the override, not the automatic result."""
    document = analyse_svg_diagram(_ring_svg([6, 6], [30, 55])).document
    round1_ids = document.rounds[0].symbol_ids
    round2_ids = document.rounds[1].symbol_ids
    target_child = round2_ids[0]

    automatic_parent = next(
        r.target_symbol_ids[0]
        for r in document.relationships
        if r.relationship_type == "parent_attachment" and r.source_symbol_ids == [target_child]
    )
    forced_parent = next(sid for sid in round1_ids if sid != automatic_parent)

    corrections = DiagramCorrectionSet(
        relationship_overrides=[
            RelationshipOverride(
                symbol_id=target_child,
                action=RelationshipOverrideAction.SET_PARENT,
                parent_symbol_ids=[forced_parent],
            )
        ]
    )
    result = compile_svg_diagram(document, corrections)
    assert result.compiled is not None
    node = next(
        n for n in result.compiled.graph.nodes if n.diagram_symbol_reference == target_child
    )
    expected_stitch_id = next(
        n.stitch_id
        for n in result.compiled.graph.nodes
        if n.diagram_symbol_reference == forced_parent
    )
    assert node.parent_stitch_ids == [expected_stitch_id]


def test_construction_centre_override_changes_topology():
    document = _unclassified_document()
    mystery_id = [s.symbol_id for s in document.symbols if s.source_element_id == "mystery"][0]
    corrections = DiagramCorrectionSet(
        symbol_overrides={mystery_id: SymbolOverride(stitch_type="single_crochet")},
        construction_overrides=ConstructionOverrides(centre=(50.0, 50.0)),
    )
    result = compile_svg_diagram(document, corrections)
    assert result.document.construction.centre == (50.0, 50.0)
    assert result.document.construction.centre_method == "user_specified"


def test_corrections_are_deterministic_and_serialisable():
    document = _unclassified_document()
    mystery_id = [s.symbol_id for s in document.symbols if s.source_element_id == "mystery"][0]
    corrections = DiagramCorrectionSet(
        symbol_overrides={mystery_id: SymbolOverride(stitch_type="single_crochet")}
    )
    payload = corrections.model_dump_json()
    restored = DiagramCorrectionSet.model_validate_json(payload)
    assert restored == corrections

    result_a = compile_svg_diagram(document, corrections)
    result_b = compile_svg_diagram(document, restored)
    assert result_a.compiled.graph.fingerprint == result_b.compiled.graph.fingerprint


def test_reset_all_corrections_reproduces_automatic_result():
    document = _unclassified_document()
    result_with_none = compile_svg_diagram(document, DiagramCorrectionSet())
    result_with_empty = compile_svg_diagram(document, DiagramCorrectionSet())
    # Both unresolved (mystery symbol never corrected) -> both blocked identically.
    assert result_with_none.compiled is None
    assert result_with_empty.compiled is None
    assert [d.code for d in result_with_none.diagnostics] == [
        d.code for d in result_with_empty.diagnostics
    ]
