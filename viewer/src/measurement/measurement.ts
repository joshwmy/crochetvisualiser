import * as THREE from "three";
import type { GeometryDocument } from "../types/geometry";
import type {
  Measurement,
  ObjectHeightMeasurement,
  ObjectWidthMeasurement,
  PointDistanceMeasurement,
  RoundCircumferenceMeasurement,
  StitchDistanceMeasurement,
} from "./types";

/** All measurements from this pipeline are approximate — see docs/measurement-tools.md. */
const APPROXIMATE = true;

let counter = 0;
function makeId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now()}-${counter}`;
}

function distance(a: [number, number, number], b: [number, number, number]): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

/** Arbitrary point-to-point distance — the two points need not correspond
 * to any stitch, e.g. a raw raycast hit on the yarn/structural surface. */
export function createPointDistanceMeasurement(
  doc: GeometryDocument,
  pointA: [number, number, number],
  pointB: [number, number, number],
): PointDistanceMeasurement {
  return {
    id: makeId("point-distance"),
    type: "point_distance",
    label: "Point-to-point distance",
    valueCm: distance(pointA, pointB),
    unit: doc.units,
    approximate: APPROXIMATE,
    createdAtMs: Date.now(),
    geometryFingerprint: doc.geometry_fingerprint,
    pointA,
    pointB,
  };
}

/** Point-to-point / stitch-to-stitch distance in the document's real-world
 * unit (`doc.units`, always "cm" today) — approximate, since it's derived
 * from analytically-placed stitch positions, not a physical measurement.
 * See docs/measurement-tools.md. */
export function createStitchDistanceMeasurement(
  doc: GeometryDocument,
  stitchIdA: string,
  stitchIdB: string,
): StitchDistanceMeasurement | null {
  const a = doc.stitches.find((s) => s.stitch_id === stitchIdA);
  const b = doc.stitches.find((s) => s.stitch_id === stitchIdB);
  if (!a || !b) return null;
  return {
    id: makeId("stitch-distance"),
    type: "stitch_distance",
    label: `${stitchIdA} ↔ ${stitchIdB}`,
    valueCm: distance(a.position, b.position),
    unit: doc.units,
    approximate: APPROXIMATE,
    createdAtMs: Date.now(),
    geometryFingerprint: doc.geometry_fingerprint,
    stitchIdA,
    stitchIdB,
  };
}

/** Backwards-compatible alias for the pre-refactor call sites/tests. */
export function measureDistance(
  doc: GeometryDocument,
  stitchIdA: string,
  stitchIdB: string,
): StitchDistanceMeasurement | null {
  return createStitchDistanceMeasurement(doc, stitchIdA, stitchIdB);
}

/** Approximate overall width: the larger of the model's X/Y bounding-box
 * extents. The geometry pipeline builds rotationally symmetric shapes
 * (docs/known-limitations.md, "Category and vocabulary"), so X and Y
 * extents should be near-equal in practice; the max is used rather than
 * assuming X specifically, so this stays correct if that assumption ever
 * loosens. Z is excluded — see createObjectHeightMeasurement for why Z is
 * the vertical axis in this pipeline's convention. */
export function createObjectWidthMeasurement(doc: GeometryDocument): ObjectWidthMeasurement {
  const { min, max } = doc.bounds;
  const extentX = max[0] - min[0];
  const extentY = max[1] - min[1];
  return {
    id: makeId("object-width"),
    type: "object_width",
    label: "Object width",
    valueCm: Math.max(extentX, extentY),
    unit: doc.units,
    approximate: APPROXIMATE,
    createdAtMs: Date.now(),
    geometryFingerprint: doc.geometry_fingerprint,
  };
}

/** Approximate overall height: the model's Z bounding-box extent. Z is the
 * vertical/round-progression axis in this pipeline's layout convention
 * (geometry/rotational_rounds.py builds each round at a decreasing Z as
 * rounds progress, dome height also along Z) — not an assumption made
 * fresh here. */
export function createObjectHeightMeasurement(doc: GeometryDocument): ObjectHeightMeasurement {
  const { min, max } = doc.bounds;
  return {
    id: makeId("object-height"),
    type: "object_height",
    label: "Object height",
    valueCm: max[2] - min[2],
    unit: doc.units,
    approximate: APPROXIMATE,
    createdAtMs: Date.now(),
    geometryFingerprint: doc.geometry_fingerprint,
  };
}

/** Approximate round circumference: sum of consecutive horizontal-neighbour
 * edge lengths within one round (an analytic estimate, not a measured
 * physical circumference — see docs/measurement-tools.md). Method: a
 * closed polyline through the round's stitch positions in sequence-index
 * order (the "round anchor polyline" method — not the analytical crown
 * radius, and not the stitch-path centreline, both of which would give a
 * different number for the same round; see docs/measurement-tools.md for
 * why this method was chosen). */
export function createRoundCircumferenceMeasurement(
  doc: GeometryDocument,
  componentId: string,
  roundIndex: number,
): RoundCircumferenceMeasurement | null {
  const ring = doc.stitches
    .filter((s) => s.component_id === componentId && s.round_index === roundIndex)
    .sort((a, b) => a.sequence_index - b.sequence_index);
  if (ring.length < 2) return null;
  let total = 0;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i].position;
    const b = ring[(i + 1) % ring.length].position;
    total += Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  }
  return {
    id: makeId("round-circumference"),
    type: "round_circumference",
    label: `Round ${roundIndex} circumference (${componentId})`,
    valueCm: total,
    unit: doc.units,
    approximate: APPROXIMATE,
    createdAtMs: Date.now(),
    geometryFingerprint: doc.geometry_fingerprint,
    componentId,
    roundIndex,
  };
}

/** Legacy pure function kept for direct reuse/tests independent of the
 * Measurement record wrapper. */
export function measureRoundCircumference(
  doc: GeometryDocument,
  componentId: string,
  roundIndex: number,
): number {
  return createRoundCircumferenceMeasurement(doc, componentId, roundIndex)?.valueCm ?? 0;
}

/** Builds the dashed-line visual for any measurement kind that has a
 * concrete pair of endpoints in 3D space (point-to-point, stitch-to-stitch).
 * Object width/height/round-circumference are scalar summaries with no
 * single natural line segment to draw, so they render only in the
 * measurement list, not as a scene overlay — see docs/measurement-tools.md. */
export function buildMeasurementLine(doc: GeometryDocument, measurement: Measurement): THREE.Line | null {
  let a: [number, number, number] | undefined;
  let b: [number, number, number] | undefined;

  if (measurement.type === "point_distance") {
    a = measurement.pointA;
    b = measurement.pointB;
  } else if (measurement.type === "stitch_distance") {
    a = doc.stitches.find((s) => s.stitch_id === measurement.stitchIdA)?.position;
    b = doc.stitches.find((s) => s.stitch_id === measurement.stitchIdB)?.position;
  } else {
    return null;
  }
  if (!a || !b) return null;

  const geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(...a),
    new THREE.Vector3(...b),
  ]);
  const material = new THREE.LineDashedMaterial({ color: 0x5fb0e6, dashSize: 0.15, gapSize: 0.08 });
  const line = new THREE.Line(geometry, material);
  line.computeLineDistances();
  line.name = `measurement-${measurement.id}`;
  return line;
}
