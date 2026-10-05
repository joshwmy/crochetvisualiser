import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { StitchPathResult, SegmentRole } from "../geometry/stitch_paths/types";
import { buildTubeGeometry, computeParallelTransportFrames } from "../geometry/parallel_transport_tube";

/**
 * Colour-per-role palette for the semantic path-inspection mode. Colour is
 * a secondary cue only — every consumer of this module must also expose
 * the role as text (inspector row, legend label, `<select>` option), per
 * the "colour alone is not sufficient" requirement. See
 * docs/stitch-geometry-strategies.md's role vocabulary.
 */
export const PATH_ROLE_COLORS: Record<SegmentRole, number> = {
  foundation_loop: 0x9a6fd1,
  top_loop: 0xf5e642,
  front_loop: 0x5fb0e6,
  back_loop: 0xe8a33d,
  post: 0xcbb89a,
  yarn_over: 0x4be08a,
  pull_through: 0x36c98f,
  connector: 0x9aa0a6,
  increase_branch: 0xff9f45,
  decrease_bridge: 0xe85d5d,
};

export const PATH_ROLE_LABELS: Record<SegmentRole, string> = {
  foundation_loop: "Foundation loop",
  top_loop: "Top loop",
  front_loop: "Front loop (attachment)",
  back_loop: "Back loop (attachment)",
  post: "Post",
  yarn_over: "Yarn over",
  pull_through: "Pull through",
  connector: "Connector",
  increase_branch: "Increase branch",
  decrease_bridge: "Decrease bridge",
};

export const PATH_ROLE_LEGEND: { role: SegmentRole; color: string; label: string }[] = (
  Object.keys(PATH_ROLE_COLORS) as SegmentRole[]
).map((role) => ({
  role,
  color: `#${PATH_ROLE_COLORS[role].toString(16).padStart(6, "0")}`,
  label: PATH_ROLE_LABELS[role],
}));

function tubeForSegment(segment: StitchPathResult["segments"][number], color: THREE.Color): THREE.BufferGeometry | null {
  const points = segment.controlPoints.map((p) => new THREE.Vector3(...p));
  if (points.length < 2) return null;
  const sampled =
    segment.curveType === "catmull_rom"
      ? new THREE.CatmullRomCurve3(points, segment.closed).getPoints(Math.max(points.length * 3, 12))
      : points;
  if (sampled.length < 2) return null;
  const frames = computeParallelTransportFrames(sampled, segment.closed);
  return buildTubeGeometry(sampled, frames, segment.radius * 1.1, 8, segment.closed, color);
}

export interface PathInspectionResult {
  /** Selected stitch's own segments, coloured per role, filtered by focus. */
  focusMesh: THREE.Mesh | null;
  /** Context stitches (parent / next-in-sequence), flat neutral colour, always dimmed. */
  contextMesh: THREE.Mesh | null;
  /** Every role actually present on the selected stitch — drives the role picker/legend. */
  rolesPresent: SegmentRole[];
}

const CONTEXT_COLOR = new THREE.Color(0x555a63);

/**
 * Builds the geometry for path-inspection mode. Never renders every stitch
 * in the model — only `selected` (always) and, if provided, `parent`/`next`
 * as dimmed context (per the brief's "do not display semantic paths for
 * every stitch simultaneously" requirement).
 */
export function buildPathInspectionMeshes(
  selected: StitchPathResult,
  focusedRole: SegmentRole | null,
  context: { parent?: StitchPathResult; next?: StitchPathResult } = {},
): PathInspectionResult {
  const rolesPresent = [...new Set(selected.segments.map((s) => s.role))];

  const focusGeometries: THREE.BufferGeometry[] = [];
  for (const segment of selected.segments) {
    if (focusedRole && segment.role !== focusedRole) continue;
    const geometry = tubeForSegment(segment, new THREE.Color(PATH_ROLE_COLORS[segment.role]));
    if (geometry) focusGeometries.push(geometry);
  }
  let focusMesh: THREE.Mesh | null = null;
  if (focusGeometries.length > 0) {
    const merged = mergeGeometries(focusGeometries, false);
    focusGeometries.forEach((g) => g.dispose());
    const material = new THREE.MeshBasicMaterial({ vertexColors: true, depthTest: true });
    focusMesh = new THREE.Mesh(merged, material);
    focusMesh.name = "path-inspection-focus";
  }

  const contextGeometries: THREE.BufferGeometry[] = [];
  for (const result of [context.parent, context.next]) {
    if (!result) continue;
    for (const segment of result.segments) {
      const geometry = tubeForSegment(segment, CONTEXT_COLOR);
      if (geometry) contextGeometries.push(geometry);
    }
  }
  let contextMesh: THREE.Mesh | null = null;
  if (contextGeometries.length > 0) {
    const merged = mergeGeometries(contextGeometries, false);
    contextGeometries.forEach((g) => g.dispose());
    const material = new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.35,
      depthTest: true,
    });
    contextMesh = new THREE.Mesh(merged, material);
    contextMesh.name = "path-inspection-context";
  }

  return { focusMesh, contextMesh, rolesPresent };
}
