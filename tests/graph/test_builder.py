from __future__ import annotations

from decimal import Decimal

import pytest

from crochet_reconstruction.domain.enums import ComponentKind
from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.graph.builder import build_stitch_graph
from crochet_reconstruction.graph.errors import GraphValidationError
from crochet_reconstruction.graph.fingerprint import compute_graph_fingerprint
from crochet_reconstruction.graph.validation import validate_graph
from tests.conftest import make_project_input


@pytest.fixture
def small_pattern():
    # Small circumference/height keeps the fixture's node count in the tens,
    # not the thousands, for fast and readable assertions.
    project_input = make_project_input(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("10.0"),
        brim_height_cm=Decimal("2.0"),
    )
    return compile_pattern(project_input)


def test_graph_has_one_node_per_stated_stitch(small_pattern):
    graph = build_stitch_graph(small_pattern)
    expected_total = sum(
        round_.stated_total for c in small_pattern.components for round_ in c.rounds
    )
    assert len(graph.nodes) == expected_total


def test_sequence_indices_are_contiguous(small_pattern):
    graph = build_stitch_graph(small_pattern)
    indices = sorted(n.sequence_index for n in graph.nodes)
    assert indices == list(range(len(graph.nodes)))


def test_first_round_stitches_are_into_ring(small_pattern):
    graph = build_stitch_graph(small_pattern)
    first_round = [
        n for n in graph.nodes if n.component_kind is ComponentKind.CROWN and n.round_number == 1
    ]
    assert first_round
    assert all(n.into_ring for n in first_round)
    assert all(n.parent_stitch_ids == [] for n in first_round)


def test_increase_children_share_one_parent(small_pattern):
    graph = build_stitch_graph(small_pattern)
    increase_nodes = [n for n in graph.nodes if n.is_increase]
    assert increase_nodes
    by_group: dict[str, list] = {}
    for node in increase_nodes:
        by_group.setdefault(node.increase_group_id, []).append(node)
    for group_id, members in by_group.items():
        parent_sets = {tuple(m.parent_stitch_ids) for m in members}
        assert len(parent_sets) == 1, f"increase group {group_id} has inconsistent parents"
        assert len(members) >= 2


def test_horizontal_neighbor_edges_form_closed_ring(small_pattern):
    graph = build_stitch_graph(small_pattern)
    round1 = [
        n.stitch_id
        for n in graph.nodes
        if n.component_kind is ComponentKind.CROWN and n.round_number == 1
    ]
    neighbor_edges = {
        (e.source_id, e.target_id) for e in graph.edges if e.edge_type == "horizontal_neighbor"
    }
    for i, stitch_id in enumerate(round1):
        nxt = round1[(i + 1) % len(round1)]
        assert (stitch_id, nxt) in neighbor_edges


def test_round_totals_match_compiled_pattern(small_pattern):
    graph = build_stitch_graph(small_pattern)
    for component in small_pattern.components:
        for round_ in component.rounds:
            count = sum(
                1
                for n in graph.nodes
                if n.component_kind == component.kind and n.round_number == round_.number
            )
            assert count == round_.stated_total


def test_graph_passes_validation(small_pattern):
    graph = build_stitch_graph(small_pattern)
    validate_graph(graph)  # must not raise


def test_identical_input_produces_identical_graph(small_pattern):
    graph_a = build_stitch_graph(small_pattern)
    graph_b = build_stitch_graph(small_pattern)
    assert graph_a.fingerprint == graph_b.fingerprint
    assert compute_graph_fingerprint(graph_a) == graph_a.fingerprint


def test_invalid_graph_rejected_by_validation(small_pattern):
    graph = build_stitch_graph(small_pattern)
    duplicate_id = graph.nodes[0].stitch_id
    tampered = graph.model_copy(
        update={"nodes": [n.model_copy(update={"stitch_id": duplicate_id}) for n in graph.nodes]}
    )
    with pytest.raises(GraphValidationError):
        validate_graph(tampered)


def test_dangling_insertion_target_rejected():
    graph = build_stitch_graph(compile_pattern(make_project_input()))
    bad_node = graph.nodes[5].model_copy(update={"parent_stitch_ids": ["does-not-exist"]})
    nodes = list(graph.nodes)
    nodes[5] = bad_node
    tampered = graph.model_copy(update={"nodes": nodes})
    with pytest.raises(GraphValidationError):
        validate_graph(tampered)
