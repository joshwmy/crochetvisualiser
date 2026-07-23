"""Diagram-to-StitchGraph conversion: reuse of the existing graph model,
existing validation, deterministic IDs/fingerprints, and geometry reuse.
"""

from __future__ import annotations

import math

from crochet_reconstruction.diagram.corrections import DiagramCorrectionSet
from crochet_reconstruction.diagram.pipeline import analyse_svg_diagram, compile_svg_diagram
from crochet_reconstruction.geometry.layout import build_geometry
from crochet_reconstruction.graph.validation import validate_graph
from crochet_reconstruction.parsing.written.semantic import DEFAULT_WRITTEN_PATTERN_GAUGE


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


def _compile(svg: str):
    document = analyse_svg_diagram(svg).document
    return compile_svg_diagram(document, DiagramCorrectionSet())


def test_compiled_graph_passes_existing_validation():
    result = _compile(_ring_svg([6], [30]))
    validate_graph(result.compiled.graph)  # raises on failure


def test_stitch_ids_are_deterministic_not_random():
    result_a = _compile(_ring_svg([6], [30]))
    result_b = _compile(_ring_svg([6], [30]))
    ids_a = [n.stitch_id for n in result_a.compiled.graph.nodes]
    ids_b = [n.stitch_id for n in result_b.compiled.graph.nodes]
    assert ids_a == ids_b
    assert all(sid.startswith("piece-r") for sid in ids_a)


def test_fingerprints_are_deterministic_for_same_input():
    result_a = _compile(_ring_svg([6], [30]))
    result_b = _compile(_ring_svg([6], [30]))
    assert result_a.compiled.graph.fingerprint == result_b.compiled.graph.fingerprint
    assert result_a.compiled.graph.fingerprint is not None


def test_fingerprint_changes_when_topology_changes():
    result_a = _compile(_ring_svg([6], [30]))
    result_b = _compile(_ring_svg([8], [30]))
    assert result_a.compiled.graph.fingerprint != result_b.compiled.graph.fingerprint


def test_diagram_symbol_reference_and_target_rule_are_set():
    result = _compile(_ring_svg([6], [30]))
    for node in result.compiled.graph.nodes:
        assert node.diagram_symbol_reference is not None
        assert node.target_rule == "explicit"


def test_into_ring_only_true_for_first_round():
    result = _compile(_ring_svg([6, 12], [30, 55]))
    round1 = [n for n in result.compiled.graph.nodes if n.round_number == 1]
    round2 = [n for n in result.compiled.graph.nodes if n.round_number == 2]
    assert all(n.into_ring for n in round1)
    assert not any(n.into_ring for n in round2)


def test_existing_geometry_pipeline_reused_unmodified():
    result = _compile(_ring_svg([6, 12], [30, 55]))
    geometry = build_geometry(
        result.compiled.components, DEFAULT_WRITTEN_PATTERN_GAUGE, result.compiled.graph
    )
    assert len(geometry.stitches) == len(result.compiled.graph.nodes)
    assert geometry.geometry_fingerprint is not None


def test_two_unrelated_motifs_trigger_ambiguous_centre_not_a_crash():
    """This slice's topology model assumes one primary connected component
    (documented scope boundary) — two separate rings/motifs don't produce a
    second component, they trigger AMBIGUOUS_CENTRE (deterministically
    picking the first ring) since centre detection has no concept of
    multiple charts. See docs/known-limitations.md."""
    from crochet_reconstruction.diagram.diagnostics import DiagramDiagnosticCode

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">'
        '<g id="a-ring" data-stitch-type="magic_ring" transform="translate(100,100)"><circle r="6"/></g>'
        + "".join(
            f'<g data-stitch-type="single_crochet" transform="translate({100 + 20 * math.cos(2 * math.pi * i / 6):.4f},{100 + 20 * math.sin(2 * math.pi * i / 6):.4f})"></g>'
            for i in range(6)
        )
        + '<g id="b-ring" data-stitch-type="magic_ring" transform="translate(350,350)"><circle r="6"/></g>'
        + "".join(
            f'<g data-stitch-type="single_crochet" transform="translate({350 + 20 * math.cos(2 * math.pi * i / 6):.4f},{350 + 20 * math.sin(2 * math.pi * i / 6):.4f})"></g>'
            for i in range(6)
        )
        + "</svg>"
    )
    analysis = analyse_svg_diagram(svg)
    assert analysis.document is not None
    codes = [d.code for d in analysis.diagnostics]
    assert DiagramDiagnosticCode.AMBIGUOUS_CENTRE in codes


def test_find_unreachable_detects_orphaned_parent_chain():
    """Direct unit test of the DISCONNECTED_COMPONENT defensive check
    (compiler._find_unreachable): this slice's own proportional-projection
    algorithm always guarantees reachability by construction, so the only
    realistic trigger is a manual correction creating an orphan reference —
    exercised here directly rather than contrived through the full
    pipeline."""
    from crochet_reconstruction.diagram.compiler import _find_unreachable
    from crochet_reconstruction.domain.enums import ComponentKind, LoopPlacement, StitchFamily
    from crochet_reconstruction.graph.models import StitchNode, stitch_height_category

    def node(stitch_id, round_number, parent_ids, into_ring=False):
        return StitchNode(
            stitch_id=stitch_id,
            component_kind=ComponentKind.PIECE,
            round_number=round_number,
            position_in_round=0,
            sequence_index=0,
            stitch_type=StitchFamily.SC,
            stitch_height_category=stitch_height_category(StitchFamily.SC),
            loop_placement=LoopPlacement.BOTH,
            parent_stitch_ids=parent_ids,
            into_ring=into_ring,
            source_reference="test",
        )

    ring_node = node("r1", 1, [], into_ring=True)
    orphan_a = node("orphan-a", 2, ["orphan-b"])
    orphan_b = node("orphan-b", 2, ["orphan-a"])  # cycle, never reaches into_ring
    connected = node("r2", 2, ["r1"])

    unreachable = _find_unreachable([ring_node, orphan_a, orphan_b, connected])
    assert set(unreachable) == {"orphan-a", "orphan-b"}


def test_stated_total_matches_actual_round_stitch_count():
    result = _compile(_ring_svg([6, 12], [30, 55]))
    for component in result.compiled.components:
        for round_ in component.rounds:
            actual = sum(1 for n in result.compiled.graph.nodes if n.round_number == round_.number)
            assert round_.stated_total == actual
