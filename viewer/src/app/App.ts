import * as THREE from "three";
import type { GeometryDocument } from "../types/geometry";
import { createScene } from "../scene/scene";
import { CameraRig, type ViewPreset } from "../camera/camera";
import { createRenderer } from "../rendering/renderer";
import { buildStructuralScene, commitMatrixUpdates, setInstanceHidden } from "../geometry/build_meshes";
import type { StructuralScene } from "../geometry/build_meshes";
import { buildYarnMeshes } from "../geometry/build_yarn";
import { Picker } from "../selection/picking";
import { SelectionHighlighter } from "../selection/highlight";
import { ConstructionTimeline } from "../animation/construction";
import { buildClippingPlane, applyClippingToMaterials } from "../clipping/clipping";
import { Store, createInitialState, type ViewerState } from "../state/store";

export interface PerformanceStats {
  stitchCount: number;
  yarnSegmentCount: number;
  triangleCount: number;
  drawCalls: number;
  geometryGenerationMs: number;
  jsonSizeBytes: number;
}

export class App {
  private scene: THREE.Scene;
  private renderer: THREE.WebGLRenderer;
  private cameraRig: CameraRig;
  private structural: StructuralScene;
  private yarnMeshes: THREE.Mesh[];
  private picker = new Picker();
  private highlighter: SelectionHighlighter;
  private timeline: ConstructionTimeline;
  private store: Store;
  private canvas: HTMLCanvasElement;
  private doc: GeometryDocument;
  private stats: PerformanceStats;

  constructor(canvas: HTMLCanvasElement, doc: GeometryDocument, jsonSizeBytes: number) {
    this.canvas = canvas;
    this.doc = doc;

    const genStart = performance.now();
    this.scene = createScene();
    this.renderer = createRenderer(canvas);
    this.cameraRig = new CameraRig(canvas, canvas.clientWidth / canvas.clientHeight || 1);

    this.structural = buildStructuralScene(doc);
    for (const group of this.structural.groups) this.scene.add(group.mesh);

    this.yarnMeshes = buildYarnMeshes(doc);
    for (const mesh of this.yarnMeshes) {
      mesh.visible = false;
      this.scene.add(mesh);
    }
    const genEnd = performance.now();

    this.highlighter = new SelectionHighlighter(this.scene);
    this.cameraRig.fitToBounds(doc.bounds);

    this.store = new Store(createInitialState(doc.stitches.length));
    this.timeline = new ConstructionTimeline(doc.stitches, (index) => {
      this.store.set({ animationIndex: index });
    });

    let triangles = 0;
    for (const group of this.structural.groups) {
      const positionCount = group.mesh.geometry.getAttribute("position").count;
      triangles += (positionCount / 3) * group.mesh.count;
    }

    this.stats = {
      stitchCount: doc.stitches.length,
      yarnSegmentCount: doc.yarn_segments.length,
      triangleCount: Math.round(triangles),
      drawCalls: this.structural.groups.length,
      geometryGenerationMs: genEnd - genStart,
      jsonSizeBytes,
    };

    this.store.subscribe((state) => this.applyState(state));
    this.applyState(this.store.get());

    this.canvas.addEventListener("pointerdown", (event) => this.handlePointerDown(event));

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.cameraRig.controls.enableDamping = !reduceMotion;

    this.renderLoop();
  }

  getStore(): Store {
    return this.store;
  }

  getTimeline(): ConstructionTimeline {
    return this.timeline;
  }

  getStats(): PerformanceStats {
    return this.stats;
  }

  getDoc(): GeometryDocument {
    return this.doc;
  }

  getStitch(stitchId: string) {
    return this.doc.stitches.find((s) => s.stitch_id === stitchId) ?? null;
  }

  setViewPreset(preset: ViewPreset): void {
    this.cameraRig.setPreset(preset);
  }

  toggleProjection(): "perspective" | "orthographic" {
    return this.cameraRig.toggleProjection();
  }

  focusOnStitch(stitchId: string): void {
    const location = this.structural.stitchIdToLocation.get(stitchId);
    if (!location) return;
    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    location.group.matrices[location.index].decompose(position, quaternion, scale);
    this.cameraRig.focusOn(position, 2.5);
  }

  handleResize(): void {
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(width, height, false);
    this.cameraRig.handleResize(width, height);
  }

  private handlePointerDown(event: PointerEvent): void {
    const stitchId = this.picker.pick(event, this.canvas, this.cameraRig.active, this.structural);
    this.store.set({ selectedStitchId: stitchId });
  }

  private applyState(state: ViewerState): void {
    this.highlighter.select(state.selectedStitchId, this.structural);

    const structuralVisible = state.viewMode === "structural";
    for (const group of this.structural.groups) {
      group.mesh.visible = structuralVisible && !state.hiddenComponentIds.has(group.componentId);
    }
    for (const mesh of this.yarnMeshes) {
      const componentId = mesh.name.replace("yarn-", "");
      mesh.visible = !structuralVisible && !state.hiddenComponentIds.has(componentId);
    }

    this.applyPerStitchVisibility(state);
    this.applyOpacity(state.opacity);
    this.applyClipping(state);
  }

  private applyPerStitchVisibility(state: ViewerState): void {
    const [roundComponent, roundIndexStr] = state.isolatedRoundKey?.split(":") ?? [null, null];
    const roundIndex = roundIndexStr ? Number(roundIndexStr) : null;

    const touchedGroups = new Set(this.structural.groups);
    for (const stitch of this.doc.stitches) {
      const location = this.structural.stitchIdToLocation.get(stitch.stitch_id);
      if (!location) continue;
      const withinAnimation = stitch.sequence_index < state.animationIndex;
      const withinIsolation =
        roundIndex === null ||
        (stitch.component_id === roundComponent && stitch.round_index === roundIndex);
      const hidden = !withinAnimation || !withinIsolation;
      setInstanceHidden(location.group, location.index, hidden);
      touchedGroups.add(location.group);
    }
    for (const group of touchedGroups) commitMatrixUpdates(group);
  }

  private applyOpacity(opacity: number): void {
    for (const group of this.structural.groups) {
      (group.mesh.material as THREE.MeshStandardMaterial).opacity = opacity;
    }
    for (const mesh of this.yarnMeshes) {
      (mesh.material as THREE.MeshStandardMaterial).opacity = opacity;
    }
  }

  private applyClipping(state: ViewerState): void {
    const plane = state.clipping.enabled ? buildClippingPlane(this.doc.bounds, state.clipping) : null;
    const materials = [
      ...this.structural.groups.map((g) => g.mesh.material as THREE.Material),
      ...this.yarnMeshes.map((m) => m.material as THREE.Material),
    ];
    applyClippingToMaterials(materials, plane);
  }

  private renderLoop = (): void => {
    requestAnimationFrame(this.renderLoop);
    const now = performance.now();
    this.timeline.tick(now);
    this.cameraRig.update();
    this.renderer.render(this.scene, this.cameraRig.active);
  };
}
