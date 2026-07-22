from __future__ import annotations

import math
from decimal import Decimal

import pytest

from crochet_reconstruction.engine.compiler import compile_pattern
from crochet_reconstruction.geometry.frames import dot, normalize
from crochet_reconstruction.geometry.layout import build_geometry, compute_geometry_fingerprint
from crochet_reconstruction.graph.builder import build_stitch_graph
from tests.conftest import make_project_input


def _build(**overrides):
    pattern = compile_pattern(make_project_input(**overrides))
    graph = build_stitch_graph(pattern.components, pattern_fingerprint=pattern.fingerprint)
    geometry = build_geometry(
        pattern.components, pattern.input.gauge, graph, pattern_fingerprint=pattern.fingerprint
    )
    return pattern, graph, geometry


@pytest.fixture
def small_geometry():
    _, _, geometry = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("10.0"),
        brim_height_cm=Decimal("2.0"),
    )
    return geometry


def test_all_positions_are_finite(small_geometry):
    for stitch in small_geometry.stitches:
        assert all(math.isfinite(c) for c in stitch.position)
        assert all(math.isfinite(c) for c in stitch.orientation)


def test_quaternions_are_unit_length(small_geometry):
    for stitch in small_geometry.stitches:
        norm = math.sqrt(sum(c * c for c in stitch.orientation))
        assert norm == pytest.approx(1.0, abs=1e-9)


def test_frames_are_orthonormal(small_geometry):
    for stitch in small_geometry.stitches:
        t, n, b = stitch.tangent, stitch.normal, stitch.binormal
        assert math.sqrt(sum(c * c for c in t)) == pytest.approx(1.0, abs=1e-9)
        assert math.sqrt(sum(c * c for c in n)) == pytest.approx(1.0, abs=1e-9)
        assert math.sqrt(sum(c * c for c in b)) == pytest.approx(1.0, abs=1e-9)
        assert dot(t, n) == pytest.approx(0.0, abs=1e-9)
        assert dot(t, b) == pytest.approx(0.0, abs=1e-9)
        assert dot(n, b) == pytest.approx(0.0, abs=1e-9)


def test_radius_grows_with_stitch_count():
    _, _, geometry = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("10.0"),
        brim_height_cm=Decimal("2.0"),
    )
    by_round: dict[tuple, list[float]] = {}
    for stitch in geometry.stitches:
        key = (stitch.component_id, stitch.round_index)
        by_round.setdefault(key, []).append(math.hypot(*stitch.position[:2]))
    crown_rounds = sorted(k[1] for k in by_round if k[0] == "crown")
    radii = [max(by_round[("crown", r)]) for r in crown_rounds]
    assert radii == sorted(radii)
    assert radii[-1] > radii[0]


def test_gauge_affects_scale():
    _, _, loose = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("10.0"),
        brim_height_cm=Decimal("2.0"),
        stitches_per_10cm=Decimal("10.0"),
    )
    _, _, tight = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("10.0"),
        brim_height_cm=Decimal("2.0"),
        stitches_per_10cm=Decimal("20.0"),
    )
    assert tight.measurements.max_radius_cm < loose.measurements.max_radius_cm


def test_body_rounds_increase_overall_height():
    _, _, short = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("8.0"),
        brim_height_cm=Decimal("1.0"),
    )
    _, _, tall = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("14.0"),
        brim_height_cm=Decimal("1.0"),
    )
    assert tall.measurements.overall_height_cm > short.measurements.overall_height_cm


def test_bounds_contain_all_stitch_positions(small_geometry):
    for stitch in small_geometry.stitches:
        for axis in range(3):
            assert small_geometry.bounds.min[axis] - 1e-9 <= stitch.position[axis]
            assert stitch.position[axis] <= small_geometry.bounds.max[axis] + 1e-9


def test_geometry_fingerprint_is_deterministic(small_geometry):
    assert compute_geometry_fingerprint(small_geometry) == small_geometry.geometry_fingerprint
    _, _, geometry_again = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("10.0"),
        brim_height_cm=Decimal("2.0"),
    )
    assert geometry_again.geometry_fingerprint == small_geometry.geometry_fingerprint


def test_increase_children_stay_near_parent_angle():
    _, graph, geometry = _build(
        head_circumference_cm=Decimal("30.0"),
        target_height_cm=Decimal("10.0"),
        brim_height_cm=Decimal("2.0"),
    )
    by_id = {s.stitch_id: s for s in geometry.stitches}
    increase_nodes = [n for n in graph.nodes if n.is_increase]
    assert increase_nodes
    for node in increase_nodes:
        child_pos = by_id[node.stitch_id].position
        for parent_id in node.parent_stitch_ids:
            parent_pos = by_id[parent_id].position
            child_angle = math.atan2(child_pos[1], child_pos[0])
            parent_angle = math.atan2(parent_pos[1], parent_pos[0])
            raw_delta = child_angle - parent_angle
            delta = abs(math.atan2(math.sin(raw_delta), math.cos(raw_delta)))
            assert delta < 0.5  # well under a quarter turn


def test_frame_normalize_rejects_zero_vector():
    with pytest.raises(ValueError, match="zero-length"):
        normalize((0.0, 0.0, 0.0))
