import type { Vec3 } from "../types/geometry";

export type MeasurementType =
  | "point_distance"
  | "stitch_distance"
  | "object_width"
  | "object_height"
  | "round_circumference";

/**
 * Fields shared by every measurement kind. All measurements from this
 * geometry pipeline are `approximate: true` today — nothing here is a
 * physical measurement, only a distance/extent derived from analytically
 * placed stitch positions (see docs/measurement-tools.md). The field exists
 * (rather than being hardcoded into display strings, as the pre-refactor
 * `Measurement` type did) so a future measurement source that *is* exact
 * could set it to `false` without changing every call site that reads it.
 */
interface MeasurementBase {
  id: string;
  label: string;
  /** The measured value, in `unit`. */
  valueCm: number;
  unit: string;
  approximate: boolean;
  /** `Date.now()` at creation — when this measurement was recorded. */
  createdAtMs: number;
  /** `doc.geometry_fingerprint` at creation time, so a measurement can be
   * recognised as stale if it somehow outlived the model it was taken on
   * (in practice `loadGeometryDocument` clears all measurements on
   * recompile, so this is a belt-and-suspenders association, not the only
   * mechanism preventing stale measurements). */
  geometryFingerprint: string | null;
}

export interface PointDistanceMeasurement extends MeasurementBase {
  type: "point_distance";
  pointA: Vec3;
  pointB: Vec3;
}

export interface StitchDistanceMeasurement extends MeasurementBase {
  type: "stitch_distance";
  stitchIdA: string;
  stitchIdB: string;
}

export interface ObjectWidthMeasurement extends MeasurementBase {
  type: "object_width";
}

export interface ObjectHeightMeasurement extends MeasurementBase {
  type: "object_height";
}

export interface RoundCircumferenceMeasurement extends MeasurementBase {
  type: "round_circumference";
  componentId: string;
  roundIndex: number;
}

export type Measurement =
  | PointDistanceMeasurement
  | StitchDistanceMeasurement
  | ObjectWidthMeasurement
  | ObjectHeightMeasurement
  | RoundCircumferenceMeasurement;
