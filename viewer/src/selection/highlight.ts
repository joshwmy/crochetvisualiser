import * as THREE from "three";
import type { StructuralScene } from "../geometry/build_meshes";
import { SELECTED_COLOR } from "../geometry/build_meshes";

/**
 * Selection is never colour-only: a wireframe marker ring is placed at the
 * selected stitch's position and orientation regardless of view mode, so
 * colour-blind users (and yarn/graph modes where instance colour isn't
 * used) still have a shape-based selection indicator.
 */
export class SelectionHighlighter {
  private marker: THREE.Mesh;
  private previousColorByGroup: { group: StructuralScene["groups"][number]; index: number; color: THREE.Color } | null = null;

  constructor(scene: THREE.Scene) {
    const geometry = new THREE.TorusGeometry(0.6, 0.05, 8, 24);
    const material = new THREE.MeshBasicMaterial({ color: SELECTED_COLOR, wireframe: false });
    this.marker = new THREE.Mesh(geometry, material);
    this.marker.visible = false;
    scene.add(this.marker);
  }

  /** Test-only accessor (see App.getClippingDebugInfo) — the marker is
   * deliberately private otherwise; nothing in application code should
   * reach into it directly. */
  getMarkerMesh(): THREE.Mesh {
    return this.marker;
  }

  clear(): void {
    if (this.previousColorByGroup) {
      const { group, index, color } = this.previousColorByGroup;
      group.mesh.setColorAt(index, color);
      if (group.mesh.instanceColor) group.mesh.instanceColor.needsUpdate = true;
      this.previousColorByGroup = null;
    }
    this.marker.visible = false;
  }

  select(stitchId: string | null, structural: StructuralScene): void {
    this.clear();
    if (!stitchId) return;
    const location = structural.stitchIdToLocation.get(stitchId);
    if (!location) return;
    const { group, index } = location;

    const original = group.baseColors[index].clone();
    this.previousColorByGroup = { group, index, color: original };
    group.mesh.setColorAt(index, new THREE.Color(SELECTED_COLOR));
    if (group.mesh.instanceColor) group.mesh.instanceColor.needsUpdate = true;

    const matrix = group.matrices[index];
    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    matrix.decompose(position, quaternion, scale);
    this.marker.position.copy(position);
    this.marker.quaternion.copy(quaternion);
    this.marker.visible = true;
  }
}
