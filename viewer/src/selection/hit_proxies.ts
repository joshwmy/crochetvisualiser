import * as THREE from "three";
import type { GeometryDocument, StitchGeometry } from "../types/geometry";
import type { StitchInstanceGroup, StructuralScene } from "../geometry/build_meshes";

/**
 * Simplified, always-present, never-rendered per-stitch hit targets used
 * for picking in *every* visual mode (structural/yarn/x-ray/graph-overlay/
 * path) — not just structural mode.
 *
 * Why: the previous benchmark (docs/open-source-resource-adoption.md,
 * "three-mesh-bvh" re-evaluation) found yarn-mode raycasting against the
 * merged, high-triangle-count tube meshes ~35-45x slower than structural
 * mode's `InstancedMesh` raycast (689ms vs 19ms per 25-point sweep on the
 * 1640-stitch reference fixture) — a linear per-triangle scan cost, not a
 * draw-call-count difference. Rather than add an acceleration structure
 * (`three-mesh-bvh`) on top of the *visible* high-poly yarn geometry, this
 * reuses the existing `Picker` class against one small invisible sphere per
 * stitch — the same low-poly-instanced-mesh shape structural mode already
 * picks against fast, decoupled entirely from which geometry is currently
 * rendered. See docs/open-source-resource-adoption.md for the measured
 * before/after this produced.
 *
 * Deliberately a *separate* mesh set from `build_meshes.ts`'s structural
 * scene, not a repurposing of it: reusing the structural meshes directly
 * would mean either rendering them (defeating "does not change visible
 * geometry") or hiding them via `.visible = false` (which also removes them
 * from raycasting — Three.js's `Raycaster.intersectObjects` skips invisible
 * objects). A fully transparent, always-`visible = true` sibling mesh has
 * zero visual footprint while staying hit-testable.
 */
export function buildHitProxyScene(doc: GeometryDocument): StructuralScene {
  const stitchRadius = doc.gauge.yarn_diameter_cm * 1.4;
  // At least as large as the widest visible representation (yarn tubes can
  // render wider than the structural capsule at high quality) so "click
  // near what you see" still holds in every mode, not just structural.
  const proxyRadius = Math.max(stitchRadius, doc.gauge.yarn_diameter_cm) * 1.8;
  const sharedGeometry = new THREE.SphereGeometry(proxyRadius, 8, 6);

  const byComponent = new Map<string, StitchGeometry[]>();
  for (const stitch of doc.stitches) {
    const list = byComponent.get(stitch.component_id) ?? [];
    list.push(stitch);
    byComponent.set(stitch.component_id, list);
  }

  const groups: StitchInstanceGroup[] = [];
  const stitchIdToLocation = new Map<string, { group: StitchInstanceGroup; index: number }>();

  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const scaleVec = new THREE.Vector3(1, 1, 1);

  for (const [componentId, stitches] of byComponent) {
    const material = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0,
      depthWrite: false,
      depthTest: false,
      colorWrite: false,
    });
    const mesh = new THREE.InstancedMesh(sharedGeometry, material, stitches.length);
    mesh.name = `hit-proxy-${componentId}`;
    // Proxies must never occlude or shadow the real geometry.
    mesh.renderOrder = -1;
    // Deliberately left at the default `frustumCulled = true`: raycasting
    // in Three.js ignores frustum culling entirely (it only gates what the
    // *renderer* draws each frame), so disabling it would buy picking
    // nothing while forcing the renderer to always process this whole
    // instanced mesh even when it's fully off-screen — a real, needless
    // per-frame cost with zero raycast benefit.

    const group: StitchInstanceGroup = {
      componentId,
      mesh,
      stitchIds: new Array(stitches.length),
      baseColors: new Array(stitches.length),
      matrices: new Array(stitches.length),
    };

    stitches.forEach((stitch, index) => {
      position.set(...stitch.position);
      quaternion.set(...stitch.orientation);
      matrix.compose(position, quaternion, scaleVec);
      mesh.setMatrixAt(index, matrix);
      group.matrices[index] = matrix.clone();
      group.stitchIds[index] = stitch.stitch_id;
      stitchIdToLocation.set(stitch.stitch_id, { group, index });
    });

    mesh.instanceMatrix.needsUpdate = true;
    groups.push(group);
  }

  return { groups, stitchIdToLocation };
}

export function disposeHitProxyScene(scene: THREE.Scene, hitProxies: StructuralScene): void {
  const disposedGeometries = new Set<THREE.BufferGeometry>();
  for (const group of hitProxies.groups) {
    scene.remove(group.mesh);
    if (!disposedGeometries.has(group.mesh.geometry)) {
      group.mesh.geometry.dispose();
      disposedGeometries.add(group.mesh.geometry);
    }
    (group.mesh.material as THREE.Material).dispose();
  }
}
