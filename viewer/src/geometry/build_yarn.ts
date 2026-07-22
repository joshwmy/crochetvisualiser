import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { GeometryDocument, YarnSegmentGeometry } from "../types/geometry";

// Basic procedural yarn mode: a straight tube per yarn segment, merged into
// one mesh per component for draw-call efficiency. This is a first-slice
// placeholder, not the "realistic yarn" target described in the product
// spec (no twist detail, no loop-specific curve shaping, no PBR fibre
// material) — see docs/scientific-viewer-spec.md, "Visualisation modes".
const COMPONENT_YARN_COLOR: Record<string, number> = {
  crown: 0x3d8fa3,
  body: 0x3d5fa3,
  brim: 0x77519e,
};

export function buildYarnMeshes(doc: GeometryDocument): THREE.Mesh[] {
  const positionsById = new Map(doc.stitches.map((s) => [s.stitch_id, s.position]));
  const byComponent = new Map<string, YarnSegmentGeometry[]>();
  for (const segment of doc.yarn_segments) {
    const owner = positionsById.has(segment.owning_stitch_id) ? segment.owning_stitch_id : null;
    const componentId = owner
      ? (doc.stitches.find((s) => s.stitch_id === owner)?.component_id ?? "unknown")
      : "unknown";
    const list = byComponent.get(componentId) ?? [];
    list.push(segment);
    byComponent.set(componentId, list);
  }

  const meshes: THREE.Mesh[] = [];
  for (const [componentId, segments] of byComponent) {
    const tubeGeometries: THREE.BufferGeometry[] = [];
    for (const segment of segments) {
      const [start, end] = segment.control_points;
      if (!start || !end) continue;
      const curve = new THREE.LineCurve3(
        new THREE.Vector3(...start),
        new THREE.Vector3(...end),
      );
      tubeGeometries.push(new THREE.TubeGeometry(curve, 1, segment.radius_cm, 6, false));
    }
    if (tubeGeometries.length === 0) continue;
    const merged = mergeGeometries(tubeGeometries, false);
    tubeGeometries.forEach((g) => g.dispose());
    const material = new THREE.MeshStandardMaterial({
      color: COMPONENT_YARN_COLOR[componentId] ?? 0x888888,
      roughness: 0.85,
      metalness: 0.0,
      transparent: true,
      opacity: 1,
    });
    const mesh = new THREE.Mesh(merged, material);
    mesh.name = `yarn-${componentId}`;
    meshes.push(mesh);
  }
  return meshes;
}
