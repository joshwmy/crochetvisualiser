"""Semantic conversion tests: parsed written pattern -> existing graph/geometry pipeline.

Confirms the written-pattern parser's output is consumable by the *existing*
graph builder and geometry layer with zero special-casing — the whole point
of producing plain ``list[Component]`` instead of a competing IR.
"""

from __future__ import annotations

from decimal import Decimal

from crochet_reconstruction.domain.enums import ComponentKind, StitchFamily
from crochet_reconstruction.domain.gauge import Gauge
from crochet_reconstruction.geometry.layout import build_geometry
from crochet_reconstruction.graph.builder import build_stitch_graph
from crochet_reconstruction.graph.validation import validate_graph
from crochet_reconstruction.parsing.written import parse_written_pattern

AMIGURUMI_EXAMPLE = """\
Round 1: 6 sc in magic ring [6]
Round 2: inc in each stitch around [12]
Round 3: (sc, inc) repeat 6 times [18]
Rounds 4-6: sc around [18]
Round 7: (sc, dec) repeat 6 times [12]
Round 8: dec around [6]
"""

DEFAULT_TEST_GAUGE = Gauge(
    stitch_family=StitchFamily.SC,
    stitches_per_10cm=Decimal("16.0"),
    rounds_per_10cm=Decimal("16.0"),
)


def _compile(source: str):
    components, diagnostics = parse_written_pattern(source)
    assert components is not None, diagnostics
    graph = build_stitch_graph(components)
    validate_graph(graph)
    geometry = build_geometry(components, DEFAULT_TEST_GAUGE, graph)
    return components, graph, geometry


def test_graph_builder_accepts_parser_output_unmodified():
    _, graph, _ = _compile(AMIGURUMI_EXAMPLE)
    assert len(graph.nodes) == 6 + 12 + 18 + 18 + 18 + 18 + 12 + 6


def test_stitch_ids_are_stable_across_recompiles():
    _, graph_a, _ = _compile(AMIGURUMI_EXAMPLE)
    _, graph_b, _ = _compile(AMIGURUMI_EXAMPLE)
    ids_a = [n.stitch_id for n in graph_a.nodes]
    ids_b = [n.stitch_id for n in graph_b.nodes]
    assert ids_a == ids_b
    assert graph_a.fingerprint == graph_b.fingerprint


def test_component_kind_is_piece_not_beanie_kind():
    components, _, _ = _compile(AMIGURUMI_EXAMPLE)
    assert components[0].kind is ComponentKind.PIECE


def test_foundation_round_has_no_parents():
    _, graph, _ = _compile(AMIGURUMI_EXAMPLE)
    round_1_nodes = [n for n in graph.nodes if n.round_number == 1]
    assert len(round_1_nodes) == 6
    assert all(n.into_ring for n in round_1_nodes)
    assert all(n.parent_stitch_ids == [] for n in round_1_nodes)


def test_increase_relationships_are_correct():
    _, graph, _ = _compile(AMIGURUMI_EXAMPLE)
    round_2_nodes = [n for n in graph.nodes if n.round_number == 2]
    assert len(round_2_nodes) == 12
    assert all(n.is_increase for n in round_2_nodes)
    # Each pair of increase children shares exactly one parent (round 1 had 6 stitches).
    parent_ids = {tuple(n.parent_stitch_ids) for n in round_2_nodes}
    assert len(parent_ids) == 6


def test_decrease_relationships_are_correct():
    _, graph, _ = _compile(AMIGURUMI_EXAMPLE)
    round_8_nodes = [n for n in graph.nodes if n.round_number == 8]
    assert len(round_8_nodes) == 6
    assert all(n.is_decrease for n in round_8_nodes)
    for node in round_8_nodes:
        assert len(node.parent_stitch_ids) == 2


def test_range_expansion_produces_three_independent_rounds():
    _, graph, _ = _compile(AMIGURUMI_EXAMPLE)
    for round_number in (4, 5, 6):
        nodes = [n for n in graph.nodes if n.round_number == round_number]
        assert len(nodes) == 18


def test_geometry_generation_succeeds_with_finite_positions():
    import math

    _, _, geometry = _compile(AMIGURUMI_EXAMPLE)
    assert len(geometry.stitches) == 108
    for stitch in geometry.stitches:
        assert all(math.isfinite(c) for c in stitch.position)


def test_expected_totals_match_declared_counts():
    components, _, _ = _compile(AMIGURUMI_EXAMPLE)
    totals = [r.stated_total for r in components[0].rounds]
    assert totals == [6, 12, 18, 18, 18, 18, 12, 6]
