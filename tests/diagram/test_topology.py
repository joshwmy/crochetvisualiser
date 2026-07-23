"""Circular topology inference: centre detection, round clustering,
direction/ordering, parent attachment, and increase/decrease grouping.
"""

from __future__ import annotations

import math

from crochet_reconstruction.diagram.diagnostics import DiagramDiagnosticCode
from crochet_reconstruction.diagram.ir import ConstructionMode, DiagramConstruction
from crochet_reconstruction.diagram.pipeline import analyse_svg_diagram
from crochet_reconstruction.diagram.security import DEFAULT_LIMITS
from crochet_reconstruction.diagram.topology import infer_topology


def _ring_svg(counts: list[int], radii: list[float], cx=200.0, cy=200.0) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">',
        f'<g id="ring" data-stitch-type="magic_ring" transform="translate({cx},{cy})">'
        f'<circle r="8"/></g>',
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


def test_centre_detected_from_explicit_magic_ring_symbol():
    a = analyse_svg_diagram(_ring_svg([6], [30]))
    assert a.document.construction.centre == (200.0, 200.0)
    assert a.document.construction.centre_method == "explicit_symbol"


def test_centre_geometric_estimate_when_no_foundation_symbol():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
        '<g data-stitch-type="single_crochet" transform="translate(40,50)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(60,50)"></g>'
        "</svg>"
    )
    a = analyse_svg_diagram(svg)
    assert a.document.construction.centre_method == "geometric_estimate"
    assert a.document.construction.centre == (50.0, 50.0)


def test_missing_centre_with_no_worked_stitches():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"><rect width="5" height="5"/></svg>'
    a = analyse_svg_diagram(svg)
    assert a.document is not None
    codes = [d.code for d in a.diagnostics]
    assert DiagramDiagnosticCode.MISSING_CENTRE in codes
    assert a.document.rounds == []


def test_round_clustering_groups_by_radius():
    a = analyse_svg_diagram(_ring_svg([6, 12], [30, 60]))
    assert a.summary.round_count == 2
    assert len(a.document.rounds[0].symbol_ids) == 6
    assert len(a.document.rounds[1].symbol_ids) == 12


def test_explicit_round_metadata_overrides_geometric_clustering():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        '<g id="ring" data-stitch-type="magic_ring" transform="translate(100,100)"><circle r="5"/></g>'
        '<g data-stitch-type="single_crochet" data-round="1" transform="translate(120,100)"></g>'
        '<g data-stitch-type="single_crochet" data-round="1" transform="translate(80,100)"></g>'
        "</svg>"
    )
    a = analyse_svg_diagram(svg)
    assert a.summary.round_count == 1
    assert a.document.symbols[1].round_index == 1
    assert a.document.symbols[2].round_index == 1


def test_deterministic_tie_breaking_for_equal_angle():
    """Two symbols at the exact same angle from centre must still produce a
    deterministic (not arbitrary/unstable) order."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        '<g id="ring" data-stitch-type="magic_ring" transform="translate(100,100)"><circle r="5"/></g>'
        '<g id="a" data-stitch-type="single_crochet" transform="translate(120,100)"></g>'
        '<g id="b" data-stitch-type="single_crochet" transform="translate(140,100)"></g>'
        "</svg>"
    )
    first = analyse_svg_diagram(svg).document.rounds[0].symbol_ids
    second = analyse_svg_diagram(svg).document.rounds[0].symbol_ids
    assert first == second


def test_direction_reversal_changes_stitch_order():
    svg = _ring_svg([6], [30])
    default_order = analyse_svg_diagram(svg).document.rounds[0].symbol_ids

    doc = analyse_svg_diagram(svg).document
    construction = DiagramConstruction(
        mode=ConstructionMode.CIRCULAR,
        centre=doc.construction.centre,
        centre_method=doc.construction.centre_method,
        direction="counterclockwise",
    )
    from crochet_reconstruction.diagram.topology import infer_topology as infer

    reversed_result = infer(doc.symbols, [], construction, DEFAULT_LIMITS)
    assert reversed_result.rounds[0].symbol_ids != default_order


def test_increase_round_shares_one_parent_across_children():
    a = analyse_svg_diagram(_ring_svg([6, 12], [30, 60]))
    parent_rels = [
        r for r in a.document.relationships if r.relationship_type == "parent_attachment"
    ]
    assert len(parent_rels) == 12
    parents_used = [r.target_symbol_ids[0] for r in parent_rels]
    # 12 children over 6 parents -> each parent referenced exactly twice.
    from collections import Counter

    counts = Counter(parents_used)
    assert set(counts.values()) == {2}


def test_decrease_round_consumes_contiguous_parent_block():
    a = analyse_svg_diagram(_ring_svg([12, 6], [60, 100]))
    parent_rels = [
        r for r in a.document.relationships if r.relationship_type == "parent_attachment"
    ]
    assert len(parent_rels) == 6
    for rel in parent_rels:
        assert len(rel.target_symbol_ids) == 2


def test_explicit_connector_overrides_radial_projection():
    pts6 = [
        (200 + 30 * math.cos(2 * math.pi * i / 6), 200 + 30 * math.sin(2 * math.pi * i / 6))
        for i in range(6)
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">',
        '<g id="ring" data-stitch-type="magic_ring" transform="translate(200,200)"><circle r="8"/></g>',
    ]
    for i, (x, y) in enumerate(pts6):
        parts.append(
            f'<g id="s{i}" data-stitch-type="single_crochet" transform="translate({x:.4f},{y:.4f})"></g>'
        )
    # Explicit connector from the ring straight to s3 (normally s0's
    # radial-projection default) — must win.
    parts.append(
        f'<line class="connector" x1="200" y1="200" x2="{pts6[3][0]:.4f}" y2="{pts6[3][1]:.4f}"/>'
    )
    parts.append("</svg>")
    a = analyse_svg_diagram("".join(parts))
    rels = {
        r.source_symbol_ids[0]: r
        for r in a.document.relationships
        if r.relationship_type in ("centre_attachment", "parent_attachment")
    }
    s3_symbol_id = [s.symbol_id for s in a.document.symbols if s.source_element_id == "s3"][0]
    assert rels[s3_symbol_id].inference_method == "explicit_connector"
    assert rels[s3_symbol_id].confidence == 1.0


def test_round_clustering_tolerance_absorbs_minor_coordinate_noise():
    """Regression: hand-authored (not exactly circular) coordinates within
    ~0.1% of the true radius must not split into a spurious extra round."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">'
        '<g id="ring" data-stitch-type="magic_ring" transform="translate(200,200)"><circle r="8"/></g>'
        '<g data-stitch-type="single_crochet" transform="translate(230,200)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(215,226)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(185,226)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(170,200)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(185,174)"></g>'
        '<g data-stitch-type="single_crochet" transform="translate(215,174)"></g>'
        "</svg>"
    )
    a = analyse_svg_diagram(svg)
    assert a.summary.round_count == 1


def test_construction_mode_row_is_rejected_this_slice():

    construction = DiagramConstruction(mode=ConstructionMode.ROW)
    result = infer_topology([], [], construction, DEFAULT_LIMITS)
    assert result.rounds == []
    codes = [d.code for d in result.diagnostics]
    assert DiagramDiagnosticCode.UNSUPPORTED_CHART_CONSTRUCTION in codes
