"""Versioned geometry-transfer schema: Python -> JSON fixture -> browser viewer.

Every stitch record here is traceable back to exactly one
:class:`crochet_reconstruction.graph.models.StitchNode` by ``stitch_id`` —
the renderer must never infer stitch identity from position alone.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from crochet_reconstruction.domain.enums import LoopPlacement, StitchFamily

GEOMETRY_SCHEMA_VERSION = "0.1.0"

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]


class StitchGeometry(BaseModel):
    """Position, orientation, and metadata for one stitch, ready to render."""

    model_config = ConfigDict(frozen=True)

    stitch_id: str
    component_id: str = Field(description="Currently the component kind, e.g. 'crown'.")
    stitch_type: StitchFamily
    round_index: int
    sequence_index: int
    position: Vec3
    orientation: Quat = Field(description="Unit quaternion (x, y, z, w).")
    tangent: Vec3
    normal: Vec3
    binormal: Vec3
    scale: float = 1.0
    loop_placement: LoopPlacement
    colour_id: str
    yarn_id: str
    parent_stitch_ids: list[str]
    is_increase: bool
    is_decrease: bool
    source_reference: str


class YarnSegmentGeometry(BaseModel):
    """Simplified curve for one yarn segment: a straight line between two stitches.

    First-slice simplification: two control points (start, end), not a full
    Catmull-Rom/Bezier centreline. See package docstring for what a later
    procedural-yarn slice would add here without changing the schema shape
    (more control points, same record type).
    """

    model_config = ConfigDict(frozen=True)

    segment_id: str
    owning_stitch_id: str
    from_stitch_id: str | None
    to_stitch_id: str
    control_points: list[Vec3] = Field(min_length=2)
    radius_cm: float = Field(gt=0)
    segment_type: str = "connector"


class GeometryEdge(BaseModel):
    """A graph edge carried through for graph-mode rendering."""

    model_config = ConfigDict(frozen=True)

    edge_id: str
    edge_type: str
    source_id: str
    target_id: str


class GeometryBounds(BaseModel):
    model_config = ConfigDict(frozen=True)

    min: Vec3
    max: Vec3


class GeometryMeasurements(BaseModel):
    """Dimensions derived from the placed geometry — always approximate.

    These are estimates from analytical stitch placement, not measurements
    of a physical object; the viewer must label them as estimated wherever
    displayed (see docs/geometry-transfer-spec.md, "Estimated, not measured").
    """

    model_config = ConfigDict(frozen=True)

    overall_height_cm: float
    max_radius_cm: float
    max_circumference_cm: float


class GaugeAssumptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    stitches_per_cm: float
    rounds_per_cm: float
    yarn_diameter_cm: float


class GeometryDocument(BaseModel):
    """The complete renderer-ready geometry payload for one compiled pattern."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = GEOMETRY_SCHEMA_VERSION
    pattern_fingerprint: str | None
    graph_fingerprint: str | None
    geometry_fingerprint: str | None = None
    units: str = "cm"
    gauge: GaugeAssumptions
    stitches: list[StitchGeometry]
    yarn_segments: list[YarnSegmentGeometry]
    edges: list[GeometryEdge]
    bounds: GeometryBounds
    measurements: GeometryMeasurements
    warnings: list[str] = Field(default_factory=list)
