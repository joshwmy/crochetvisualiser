import * as THREE from "three";
import type { GeometryBounds } from "../types/geometry";
import type { ClippingState } from "../state/store";

const AXIS_NORMAL: Record<ClippingState["axis"], THREE.Vector3> = {
  x: new THREE.Vector3(1, 0, 0),
  y: new THREE.Vector3(0, 1, 0),
  z: new THREE.Vector3(0, 0, 1),
};

/** Build a world-space clipping plane from the UI's axis/offset/invert state. */
export function buildClippingPlane(bounds: GeometryBounds, clipping: ClippingState): THREE.Plane {
  const axisIndex = { x: 0, y: 1, z: 2 }[clipping.axis];
  const center = (bounds.min[axisIndex] + bounds.max[axisIndex]) / 2;
  const halfExtent = (bounds.max[axisIndex] - bounds.min[axisIndex]) / 2 || 1;
  const planeCoordinate = center + clipping.offset * halfExtent;

  const normal = AXIS_NORMAL[clipping.axis].clone();
  if (clipping.invert) normal.negate();
  // Plane equation: normal . point + constant = 0, with the half-space
  // `normal . point + constant >= 0` kept visible by three.js's convention.
  const constant = clipping.invert ? planeCoordinate : -planeCoordinate;
  return new THREE.Plane(normal, constant);
}

export function applyClippingToMaterials(
  materials: THREE.Material[],
  plane: THREE.Plane | null,
): void {
  const planeCount = plane ? 1 : 0;
  for (const material of materials) {
    // The renderer reads clippingPlanes' values every frame; only a change
    // in how many planes there are alters the compiled shader. Flagging
    // needsUpdate unconditionally (this runs on every store update) made
    // three re-validate every program each time — measurably stalling
    // headless software-GL e2e runs once the yarn shader gained an
    // environment map and ply bump map.
    const previousCount = material.clippingPlanes?.length ?? 0;
    material.clippingPlanes = plane ? [plane] : [];
    if (previousCount !== planeCount) material.needsUpdate = true;
  }
}
