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

    // Three.js's Raycaster does NOT skip `.visible = false` objects on its
    // own — `visible` only gates the renderer, not `intersectObjects` — so
    // a hidden component (or, for the hit-proxy scene, a component the
    // user toggled off) must be filtered out here explicitly, or it stays
    // clickable despite being invisible.
    const meshes = scene.groups.filter((g) => g.mesh.visible).map((g) => g.mesh);
    const hits = this.raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return null;

    const hit = hits[0];
    const group = scene.groups.find((g) => g.mesh === hit.object);
    if (!group || hit.instanceId === undefined) return null;
    return group.stitchIds[hit.instanceId] ?? null;
  }
}
