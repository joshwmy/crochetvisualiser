"""Assemble a complete :class:`GeometryDocument` from a pattern + stitch graph."""

from __future__ import annotations

import hashlib
import json
import math

from crochet_reconstruction.domain.pattern import Pattern
from crochet_reconstruction.geometry.models import (
    GaugeAssumptions,
    GeometryBounds,
    GeometryDocument,
    GeometryEdge,
    GeometryMeasurements,
    Vec3,
    YarnSegmentGeometry,
)
from crochet_reconstruction.geometry.rotational_rounds import (
    default_yarn_diameter_cm,
    place_stitches,
)
from crochet_reconstruction.graph.models import StitchGraph

ASSUMPTION_WARNINGS = [
    "Radius is derived from stitch count and gauge, treating each round as a "
    "perfect circle; it is not a measurement of a physical object.",
    "Row height is constant per round across crown, body, and brim.",
    "The crown is modelled as a hemispherical cap for visual continuity, not "
    "derived from the increase schedule's actual curvature.",
    "Yarn diameter is a visual default (half a stitch width) unless overridden; "
    "it is not a measured yarn property.",
]


def _bounds(positions: list[Vec3]) -> GeometryBounds:
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    return GeometryBounds(
        min=(min(xs), min(ys), min(zs)),
        max=(max(xs), max(ys), max(zs)),
    )


def _measurements(positions: list[Vec3]) -> GeometryMeasurements:
    zs = [p[2] for p in positions]
    radii = [math.hypot(p[0], p[1]) for p in positions]
    max_radius = max(radii) if radii else 0.0
    return GeometryMeasurements(
        overall_height_cm=(max(zs) - min(zs)) if zs else 0.0,
        max_radius_cm=max_radius,
        max_circumference_cm=2 * math.pi * max_radius,
    )


def _canonical_json(document: GeometryDocument) -> str:
    data = document.model_dump(mode="json", exclude={"geometry_fingerprint"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_geometry_fingerprint(document: GeometryDocument) -> str:
    return hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()


def build_geometry(
    pattern: Pattern,
    graph: StitchGraph,
    *,
    yarn_diameter_cm: float | None = None,
) -> GeometryDocument:
    """Build the complete renderer-ready geometry document.

    ``graph`` must already have passed
    :func:`crochet_reconstruction.graph.validation.validate_graph` — this
    function does not re-validate it, matching the pipeline's "validation
    gates the next stage" structure (compile -> validate -> graph -> validate
    -> geometry).
    """
    stitches_per_cm = float(pattern.input.gauge.stitches_per_cm)
    rounds_per_cm = float(pattern.input.gauge.rounds_per_cm)
    resolved_yarn_diameter = yarn_diameter_cm or default_yarn_diameter_cm(stitches_per_cm)

    stitch_geometry_by_id = place_stitches(pattern, graph)
    stitches = [stitch_geometry_by_id[n.stitch_id] for n in graph.nodes]
    positions = [s.position for s in stitches]

    segments: list[YarnSegmentGeometry] = []
    for segment in graph.yarn_segments:
        to_geo = stitch_geometry_by_id[segment.to_stitch_id]
        control_points: list[Vec3]
        if segment.from_stitch_id is None:
            control_points = [to_geo.position, to_geo.position]
        else:
            from_geo = stitch_geometry_by_id[segment.from_stitch_id]
            control_points = [from_geo.position, to_geo.position]
        segments.append(
            YarnSegmentGeometry(
                segment_id=segment.segment_id,
                owning_stitch_id=segment.owning_stitch_id,
                from_stitch_id=segment.from_stitch_id,
                to_stitch_id=segment.to_stitch_id,
                control_points=control_points,
                radius_cm=resolved_yarn_diameter / 2,
                segment_type=segment.segment_type,
            )
        )

    edges = [
        GeometryEdge(
            edge_id=e.edge_id, edge_type=e.edge_type, source_id=e.source_id, target_id=e.target_id
        )
        for e in graph.edges
    ]

    document = GeometryDocument(
        pattern_fingerprint=pattern.fingerprint,
        graph_fingerprint=graph.fingerprint,
        gauge=GaugeAssumptions(
            stitches_per_cm=stitches_per_cm,
            rounds_per_cm=rounds_per_cm,
            yarn_diameter_cm=resolved_yarn_diameter,
        ),
        stitches=stitches,
        yarn_segments=segments,
        edges=edges,
        bounds=_bounds(positions),
        measurements=_measurements(positions),
        warnings=list(ASSUMPTION_WARNINGS) + list(graph.warnings),
    )
    fingerprint = compute_geometry_fingerprint(document)
    return document.model_copy(update={"geometry_fingerprint": fingerprint})
