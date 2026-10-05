import * as THREE from "three";
import type { GeometryDocument, StitchGeometry } from "../types/geometry";

// First-slice simplification: every stitch shares one capsule size derived
// from gauge, regardless of stitch_type (sc vs hdc). Real per-stitch-type
// dimensions are deferred to the "stitch-specific geometry strategies" slice
// (see docs/known-limitations.md) — this is a placeholder shape, not a
// claim that sc and hdc render at visually distinct heights yet.
const COMPONENT_BASE_COLOR: Record<string, number> = {
  crown: 0x4fb0c6,
  body: 0x4f7bc6,
  brim: 0x9a6fd1,
};
const INCREASE_COLOR = 0xe8a33d;
const DECREASE_COLOR = 0xe85d5d;
export const SELECTED_COLOR = 0xf5e642;

export interface StitchInstanceGroup {
  componentId: string;
  mesh: THREE.InstancedMesh;
  stitchIds: string[]; // index = instance index
  baseColors: THREE.Color[]; // index = instance index, the color before any highlight
  matrices: THREE.Matrix4[]; // index = instance index, the true (non-hidden) transform
}

export interface StructuralScene {
  groups: StitchInstanceGroup[];
  stitchIdToLocation: Map<string, { group: StitchInstanceGroup; index: number }>;
}

function capsuleGeometry(radius: number, length: number): THREE.CapsuleGeometry {
  const geometry = new THREE.CapsuleGeometry(radius, length, 4, 8);
  // Align the capsule's long axis with local +Z (our "binormal"/height axis)
  // instead of three.js's default local +Y, to match the orientation
  // convention used by geometry/frames.py on the Python side.
  geometry.rotateX(Math.PI / 2);
  return geometry;
}

export function buildStructuralScene(doc: GeometryDocument): StructuralScene {
  const stitchHeight = (1 / doc.gauge.rounds_per_cm) * 0.8;
  const stitchRadius = doc.gauge.yarn_diameter_cm * 1.4;
  const sharedGeometry = capsuleGeometry(stitchRadius, stitchHeight);

  const byComponent = new Map<string, StitchGeometry[]>();
  for (const stitch of doc.stitches) {
    const list = byComponent.get(stitch.component_id) ?? [];
    list.push(stitch);
    byComponent.set(stitch.component_id, list);
  }

  const groups: StitchInstanceGroup[] = [];
  const stitchIdToLocation = new Map<string, { group: StitchInstanceGroup; index: number }>();

  for (const [componentId, stitches] of byComponent) {
    // No vertexColors: CapsuleGeometry has no `color` attribute, so the flag
    // multiplied every fragment by WebGL's default (0,0,0) and the whole
    // structural view rendered black. Per-stitch colour comes from
    // mesh.instanceColor, which three applies without that flag.
    const material = new THREE.MeshStandardMaterial({
      roughness: 0.75,
      metalness: 0.05,
      transparent: true,
      opacity: 1,
    });
    const mesh = new THREE.InstancedMesh(sharedGeometry, material, stitches.length);
    mesh.instanceColor = new THREE.InstancedBufferAttribute(
      new Float32Array(stitches.length * 3),
      3,
    );

    const group: StitchInstanceGroup = {
      componentId,
      mesh,
      stitchIds: new Array(stitches.length),
      baseColors: new Array(stitches.length),
      matrices: new Array(stitches.length),
    };

    const matrix = new THREE.Matrix4();
    const quaternion = new THREE.Quaternion();
    const position = new THREE.Vector3();
    const scaleVec = new THREE.Vector3();

    stitches.forEach((stitch, index) => {
      position.set(...stitch.position);
      quaternion.set(...stitch.orientation);
      scaleVec.set(stitch.scale, stitch.scale, stitch.scale);
      matrix.compose(position, quaternion, scaleVec);
      mesh.setMatrixAt(index, matrix);
      group.matrices[index] = matrix.clone();

      const baseHex = stitch.is_increase
        ? INCREASE_COLOR
        : stitch.is_decrease
          ? DECREASE_COLOR
          : (COMPONENT_BASE_COLOR[componentId] ?? 0x999999);
      const color = new THREE.Color(baseHex);
      mesh.setColorAt(index, color);

      group.stitchIds[index] = stitch.stitch_id;
      group.baseColors[index] = color;
      stitchIdToLocation.set(stitch.stitch_id, { group, index });
    });

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.name = `stitches-${componentId}`;
    groups.push(group);
  }

  return { groups, stitchIdToLocation };
}

const ZERO_SCALE_MATRIX = new THREE.Matrix4().makeScale(0, 0, 0);

export function setInstanceHidden(group: StitchInstanceGroup, index: number, hidden: boolean): void {
  group.mesh.setMatrixAt(index, hidden ? ZERO_SCALE_MATRIX : group.matrices[index]);
}

export function commitMatrixUpdates(group: StitchInstanceGroup): void {
  group.mesh.instanceMatrix.needsUpdate = true;
}
