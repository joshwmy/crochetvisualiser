import * as THREE from "three";
import type { StructuralScene } from "../geometry/build_meshes";

export class Picker {
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();

  pick(
    event: PointerEvent,
    canvas: HTMLCanvasElement,
    camera: THREE.Camera,
    scene: StructuralScene,
  ): string | null {
    const rect = canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, camera);

    const meshes = scene.groups.map((g) => g.mesh);
    const hits = this.raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return null;

    const hit = hits[0];
    const group = scene.groups.find((g) => g.mesh === hit.object);
    if (!group || hit.instanceId === undefined) return null;
    return group.stitchIds[hit.instanceId] ?? null;
  }
}
