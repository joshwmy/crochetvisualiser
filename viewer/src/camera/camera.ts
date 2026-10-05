import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { GeometryBounds } from "../types/geometry";

export type ViewPreset = "front" | "back" | "left" | "right" | "top" | "bottom" | "reset";

export class CameraRig {
  readonly perspective: THREE.PerspectiveCamera;
  readonly orthographic: THREE.OrthographicCamera;
  active: THREE.PerspectiveCamera | THREE.OrthographicCamera;
  readonly controls: OrbitControls;
  private center: THREE.Vector3 = new THREE.Vector3();
  private radius = 10;

  constructor(domElement: HTMLElement, aspect: number) {
    // Near plane deliberately small and far plane large so the camera can
    // move inside a hollow object (e.g. inside the beanie) without clipping
    // through the interior surface — a scientific-inspection viewer must
    // never prevent that, per the interior-camera requirement.
    this.perspective = new THREE.PerspectiveCamera(50, aspect, 0.01, 500);
    const orthoSize = 10;
    this.orthographic = new THREE.OrthographicCamera(
      -orthoSize * aspect,
      orthoSize * aspect,
      orthoSize,
      -orthoSize,
      0.01,
      500,
    );
    this.active = this.perspective;
    this.controls = new OrbitControls(this.active, domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    // No minDistance floor: the user must be able to fly the camera inside
    // a hollow object, not just orbit its exterior.
  }

  fitToBounds(bounds: GeometryBounds): void {
    const min = new THREE.Vector3(...bounds.min);
    const max = new THREE.Vector3(...bounds.max);
    this.center = min.clone().add(max).multiplyScalar(0.5);
    this.radius = Math.max(max.distanceTo(min) * 0.75, 1);
    this.resetView();
  }

  resetView(): void {
    const offset = new THREE.Vector3(1, 0.6, 1.4).normalize().multiplyScalar(this.radius * 2);
    this.applyView(offset);
  }

  setPreset(preset: ViewPreset): void {
    const distance = this.radius * 2.2;
    const directions: Record<ViewPreset, THREE.Vector3> = {
      front: new THREE.Vector3(0, 0, 1),
      back: new THREE.Vector3(0, 0, -1),
      left: new THREE.Vector3(-1, 0, 0),
      right: new THREE.Vector3(1, 0, 0),
      top: new THREE.Vector3(0, 1, 0.0001),
      bottom: new THREE.Vector3(0, -1, 0.0001),
      reset: new THREE.Vector3(1, 0.6, 1.4).normalize(),
    };
    this.applyView(directions[preset].multiplyScalar(distance));
  }

  private applyView(offset: THREE.Vector3): void {
    this.active.position.copy(this.center).add(offset);
    this.active.lookAt(this.center);
    this.controls.target.copy(this.center);
    this.controls.update();
  }

  focusOn(point: THREE.Vector3, distance: number): void {
    const direction = this.active.position.clone().sub(this.controls.target).normalize();
    this.active.position.copy(point).add(direction.multiplyScalar(Math.max(distance, 0.5)));
    this.controls.target.copy(point);
    this.controls.update();
  }

  toggleProjection(): "perspective" | "orthographic" {
    const isPerspective = this.active === this.perspective;
    const nextCamera = isPerspective ? this.orthographic : this.perspective;
    nextCamera.position.copy(this.active.position);
    nextCamera.quaternion.copy(this.active.quaternion);
    this.active = nextCamera;
    this.controls.object = this.active;
    this.controls.update();
    return isPerspective ? "orthographic" : "perspective";
  }

  handleResize(width: number, height: number): void {
    const aspect = width / height;
    this.perspective.aspect = aspect;
    this.perspective.updateProjectionMatrix();
    const orthoSize = 10;
    this.orthographic.left = -orthoSize * aspect;
    this.orthographic.right = orthoSize * aspect;
    this.orthographic.top = orthoSize;
    this.orthographic.bottom = -orthoSize;
    this.orthographic.updateProjectionMatrix();
  }

  update(): void {
    this.controls.update();
  }
}
