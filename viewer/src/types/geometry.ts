// Mirrors src/crochet_reconstruction/geometry/models.py field-for-field.
// The viewer must never guess a shape the Python schema doesn't declare.
//
// SUPPORTED_SCHEMA_VERSION is match-tested against GEOMETRY_SCHEMA_VERSION by
// tests/test_frontend_type_mirror.py. The interface *fields* below are not
// structurally checked — see that file's "what this does not cover".

export type Vec3 = [number, number, number];
export type Quat = [number, number, number, number];

export interface StitchGeometry {
  stitch_id: string;
  component_id: string;
  stitch_type: string;
  round_index: number;
  sequence_index: number;
  position: Vec3;
  orientation: Quat;
  tangent: Vec3;
  normal: Vec3;
  binormal: Vec3;
  scale: number;
  loop_placement: string;
  colour_id: string;
  yarn_id: string;
  parent_stitch_ids: string[];
  is_increase: boolean;
  is_decrease: boolean;
  source_reference: string;
}

export interface YarnSegmentGeometry {
  segment_id: string;
  owning_stitch_id: string;
  from_stitch_id: string | null;
  to_stitch_id: string;
  control_points: Vec3[];
  radius_cm: number;
  segment_type: string;
}

export interface GeometryEdge {
  edge_id: string;
  edge_type: string;
  source_id: string;
  target_id: string;
}

export interface GeometryBounds {
  min: Vec3;
  max: Vec3;
}

export interface GeometryMeasurements {
  overall_height_cm: number;
  max_radius_cm: number;
  max_circumference_cm: number;
}

export interface GaugeAssumptions {
  stitches_per_cm: number;
  rounds_per_cm: number;
  yarn_diameter_cm: number;
}

export interface GeometryDocument {
  schema_version: string;
  pattern_fingerprint: string | null;
  graph_fingerprint: string | null;
  geometry_fingerprint: string | null;
  units: string;
  gauge: GaugeAssumptions;
  stitches: StitchGeometry[];
  yarn_segments: YarnSegmentGeometry[];
  edges: GeometryEdge[];
  bounds: GeometryBounds;
  measurements: GeometryMeasurements;
  warnings: string[];
}

export const SUPPORTED_SCHEMA_VERSION = "0.1.0";
