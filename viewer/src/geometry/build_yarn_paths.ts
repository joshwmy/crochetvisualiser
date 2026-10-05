import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { GeometryDocument } from "../types/geometry";
import { buildPathContext } from "./stitch_paths/context";
import { generateStitchPaths } from "./stitch_paths/strategies";
import type { StitchPathResult } from "./stitch_paths/types";
import {
  buildTubeGeometry,
  computeParallelTransportFrames,
  triangleCountForTube,
} from "./parallel_transport_tube";
import { createYarnMaterial, SEMANTIC_YARN_COLORS } from "../materials/yarn_material";

export interface QualityPreset {
  name: "low" | "medium" | "high";
  radialSegments: number;
  /** Curve samples per centimetre of estimated segment length. */
  samplesPerCm: number;
}

export const QUALITY_PRESETS: Record<QualityPreset["name"], QualityPreset> = {
  low: { name: "low", radialSegments: 4, samplesPerCm: 1.5 },
  medium: { name: "medium", radialSegments: 6, samplesPerCm: 3 },
  high: { name: "high", radialSegments: 10, samplesPerCm: 6 },
};

/** Deterministic default: large models default to `low`, matching the
 * brief's "do not automatically select high quality for very large models"
 * requirement — never a random or camera-distance-based heuristic. */
export function defaultQualityFor(stitchCount: number): QualityPreset["name"] {
  if (stitchCount > 4000) return "low";
  if (stitchCount > 500) return "medium";
  return "high";
}

export interface StitchFaceRange {
  stitchId: string;
  startFace: number;
  endFace: number; // exclusive
}

/** Per-vertex stitch kind, so the palette can be recoloured in place. */
export const VERTEX_KIND = { main: 0, increase: 1, decrease: 2 } as const;

export interface YarnPathComponentMesh {
  componentId: string;
  mesh: THREE.Mesh;
  faceRanges: StitchFaceRange[]; // sorted by startFace, contiguous, for binary search
  /** One `VERTEX_KIND` per vertex of `mesh`, in vertex order. */
  vertexKinds: Uint8Array;
}

/**
 * How the yarn is coloured. `highlightShaping` paints increases and
 * decreases in their semantic colours; off, every stitch is `main`, which
 * is what a real one-colour crochet piece looks like.
 */
export interface YarnPalette {
  main: THREE.ColorRepresentation;
  highlightShaping: boolean;
}

export const DEFAULT_YARN_PALETTE: YarnPalette = {
  main: SEMANTIC_YARN_COLORS.main,
  highlightShaping: true,
};

/** Rewrites a yarn component's vertex colours for `palette`, without
 * rebuilding any geometry. */
export function applyYarnPalette(component: YarnPathComponentMesh, palette: YarnPalette): void {
  const attribute = component.mesh.geometry.getAttribute("color") as THREE.BufferAttribute | undefined;
  if (!attribute) return;
  const main = new THREE.Color(palette.main);
  const increase = new THREE.Color(palette.highlightShaping ? SEMANTIC_YARN_COLORS.increase : palette.main);
  const decrease = new THREE.Color(palette.highlightShaping ? SEMANTIC_YARN_COLORS.decrease : palette.main);
  const byKind = [main, increase, decrease];
  const array = attribute.array as Float32Array;
  for (let i = 0; i < component.vertexKinds.length; i++) {
    const colour = byKind[component.vertexKinds[i]];
    array[i * 3] = colour.r;
    array[i * 3 + 1] = colour.g;
    array[i * 3 + 2] = colour.b;
  }
  attribute.needsUpdate = true;
}

export interface YarnPathScene {
  components: YarnPathComponentMesh[];
  warningsByStitch: Map<string, string[]>;
  pathResultsByStitch: Map<string, StitchPathResult>;
  stats: { segmentCount: number; controlPointCount: number; triangleCount: number };
}

function sampleCurve(points: THREE.Vector3[], closed: boolean, samples: number): THREE.Vector3[] {
  if (points.length < 3) return points; // a 2-point line needs no curve fitting
  const curve = new THREE.CatmullRomCurve3(points, closed, "catmullrom", 0.5);
  return curve.getPoints(Math.max(samples, points.length));
}

export function buildYarnPathScene(doc: GeometryDocument, quality: QualityPreset): YarnPathScene {
  const context = buildPathContext(doc);
  const warningsByStitch = new Map<string, string[]>();
  const pathResultsByStitch = new Map<string, StitchPathResult>();
  const byComponent = new Map<string, typeof doc.stitches>();
  for (const stitch of doc.stitches) {
    const list = byComponent.get(stitch.component_id) ?? [];
    list.push(stitch);
    byComponent.set(stitch.component_id, list);
  }

  const components: YarnPathComponentMesh[] = [];
  let totalSegments = 0;
  let totalControlPoints = 0;
  let totalTriangles = 0;

  for (const [componentId, stitches] of byComponent) {
    const geometries: THREE.BufferGeometry[] = [];
    const faceRanges: StitchFaceRange[] = [];
    const kinds: number[] = [];
    let faceCursor = 0;

    for (const stitch of stitches) {
      const result = generateStitchPaths(stitch, context);
      pathResultsByStitch.set(stitch.stitch_id, result);
      if (result.warnings.length > 0) warningsByStitch.set(stitch.stitch_id, result.warnings);

      const stitchKind = stitch.is_increase
        ? VERTEX_KIND.increase
        : stitch.is_decrease
          ? VERTEX_KIND.decrease
          : VERTEX_KIND.main;
      const stitchColor = new THREE.Color(
        stitch.is_increase
          ? SEMANTIC_YARN_COLORS.increase
          : stitch.is_decrease
            ? SEMANTIC_YARN_COLORS.decrease
            : SEMANTIC_YARN_COLORS.main,
      );

      const stitchStartFace = faceCursor;
      for (const segment of result.segments) {
        totalSegments += 1;
        totalControlPoints += segment.controlPoints.length;
        const points = segment.controlPoints.map((p) => new THREE.Vector3(...p));
        const approxLength = points.reduce(
          (sum, p, i) => (i === 0 ? 0 : sum + p.distanceTo(points[i - 1])),
          0,
        );
        const sampleCount = Math.max(4, Math.ceil(approxLength * quality.samplesPerCm));
        const sampled =
          segment.curveType === "catmull_rom"
            ? sampleCurve(points, segment.closed, sampleCount)
            : points;

        if (sampled.length < 2) continue;
        const frames = computeParallelTransportFrames(sampled, segment.closed);
        const geometry = buildTubeGeometry(
          sampled,
          frames,
          segment.radius,
          quality.radialSegments,
          segment.closed,
          stitchColor,
        );
        geometries.push(geometry);
        const vertexCount = geometry.getAttribute("position").count;
        for (let v = 0; v < vertexCount; v++) kinds.push(stitchKind);
        const triangles = triangleCountForTube(sampled.length, quality.radialSegments, segment.closed);
        faceCursor += triangles;
        totalTriangles += triangles;
      }
      faceRanges.push({ stitchId: stitch.stitch_id, startFace: stitchStartFace, endFace: faceCursor });
    }

    if (geometries.length === 0) continue;
    const merged = mergeGeometries(geometries, false);
    geometries.forEach((g) => g.dispose());
    const material = createYarnMaterial({ color: 0xffffff }); // vertexColors below carry the real colour
    material.vertexColors = true;
    const mesh = new THREE.Mesh(merged, material);
    mesh.name = `yarn-paths-${componentId}`;
    components.push({ componentId, mesh, faceRanges, vertexKinds: Uint8Array.from(kinds) });
  }

  return {
    components,
    warningsByStitch,
    pathResultsByStitch,
    stats: { segmentCount: totalSegments, controlPointCount: totalControlPoints, triangleCount: totalTriangles },
  };
}

/** Maps a raycast hit's faceIndex back to the stitch it belongs to via
 * binary search over the sorted, contiguous face ranges. */
export function stitchIdForFace(ranges: StitchFaceRange[], faceIndex: number): string | null {
  let lo = 0;
  let hi = ranges.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const range = ranges[mid];
    if (faceIndex < range.startFace) hi = mid - 1;
    else if (faceIndex >= range.endFace) lo = mid + 1;
    else return range.stitchId;
  }
  return null;
}
