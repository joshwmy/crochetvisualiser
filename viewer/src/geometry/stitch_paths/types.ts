// Semantic per-stitch yarn-path model. Deliberately framework-neutral (no
// THREE.* classes) — see docs/stitch-geometry-strategies.md's "why no
// backend schema change" note: every input field a strategy needs
// (stitch_type, loop_placement, parent_stitch_ids, is_increase/decrease,
// orientation frame) already exists on the shipped GeometryDocument, so
// this whole layer is a pure frontend interpretation of existing data —
// it never round-trips back through the API or changes any fingerprint.
//
// Strategies return data; viewer/src/geometry/build_yarn_paths.ts is the
// only place that touches THREE.js to turn this into tube meshes. This
// keeps "semantic path parts must not be discarded immediately" true: the
// role/entry/exit/warnings survive as mesh userData for inspection.

import type { StitchGeometry } from "../../types/geometry";

export type Vec3 = [number, number, number];

/** Semantic role of one yarn-path segment — see the brief's vocabulary. */
export type SegmentRole =
  | "foundation_loop"
  | "top_loop"
  | "front_loop"
  | "back_loop"
  | "post"
  | "yarn_over"
  | "pull_through"
  | "connector"
  | "increase_branch"
  | "decrease_bridge";

export interface StitchPathSegment {
  role: SegmentRole;
  /** Centreline control points, world-space cm, >= 2 points. */
  controlPoints: Vec3[];
  /** Tube radius in cm, > 0. */
  radius: number;
  /** Curve family the builder should sweep this with. */
  curveType: "catmull_rom" | "line";
  /** Whether the tube should close into a loop (start == end). */
  closed: boolean;
}

export interface StitchPathResult {
  stitchId: string;
  stitchType: string;
  strategyName: string;
  segments: StitchPathSegment[];
  entryPoint: Vec3;
  exitPoint: Vec3;
  /** Non-fatal notices — e.g. an approximated loop-placement offset. */
  warnings: string[];
}

/** Read-only lookup the strategies need across stitch boundaries
 * (parent geometry for attachment/loop-placement, gauge for scale). */
export interface StitchPathContext {
  getStitch(stitchId: string): StitchGeometry | undefined;
  yarnRadiusCm: number;
  /** Row spacing in cm — used only as a *visual* post-length reference;
   * does not change any stitch's actual backend-computed position. */
  rowHeightCm: number;
}

export interface StitchPathStrategy {
  readonly stitchType: string;
  generatePaths(stitch: StitchGeometry, context: StitchPathContext): StitchPathResult;
}
