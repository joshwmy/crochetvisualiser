import * as THREE from "three";
import type { GeometryDocument } from "../types/geometry";
import { validateGeometry } from "../geometry/load";
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
  private store: Store<ViewerState>;
  private canvas: HTMLCanvasElement;
  private doc: GeometryDocument;
  private stats: PerformanceStats;

  constructor(canvas: HTMLCanvasElement, doc: GeometryDocument, jsonSizeBytes: number) {
    this.canvas = canvas;
    this.doc = doc;

    this.scene = createScene();
    this.renderer = createRenderer(canvas);
    this.cameraRig = new CameraRig(canvas, canvas.clientWidth / canvas.clientHeight || 1);
    this.highlighter = new SelectionHighlighter(this.scene);

    const built = this.buildSceneObjects(doc, jsonSizeBytes);
    this.structural = built.structural;
    this.yarnMeshes = built.yarnMeshes;
    this.stats = built.stats;
    this.cameraRig.fitToBounds(doc.bounds);

    this.store = new Store(createInitialState(doc.stitches.length));
    this.timeline = this.createTimeline(doc);

    this.store.subscribe((state) => this.applyState(state));
    this.applyState(this.store.get());

    this.canvas.addEventListener("pointerdown", (event) => this.handlePointerDown(event));

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.cameraRig.controls.enableDamping = !reduceMotion;

    this.renderLoop();
  }

  /**
   * Replace the currently displayed model with a newly compiled one.
   *
   * Validates the document, disposes every Three.js resource owned by the
   * previous model (geometries, materials, the old picking/selection
   * mapping), rebuilds structural + yarn representations, and resets
   * selection/isolation/animation/clipping state to fresh defaults for the
   * new bounds — while preserving user display preferences (view mode,
   * camera projection, global opacity) across the swap. Throws
   * (asynchronously, via the returned rejected promise) without touching
   * any current scene state if `doc` fails validation — a failed load must
   * never leave a half-updated viewer.
   */
  async loadGeometryDocument(doc: GeometryDocument, jsonSizeBytes = 0): Promise<void> {
    validateGeometry(doc);

    const previousStructural = this.structural;
    const previousYarn = this.yarnMeshes;

    const built = this.buildSceneObjects(doc, jsonSizeBytes);

    // Only after the new scene objects are successfully built do we tear
    // down the old ones and swap state — this ordering means a throw
    // inside buildSceneObjects (e.g. a malformed but schema-valid document)
    // leaves the previous valid model fully intact and on screen.
    this.disposeStructural(previousStructural);
    this.disposeYarn(previousYarn);

    this.structural = built.structural;
    this.yarnMeshes = built.yarnMeshes;
    this.stats = built.stats;
    this.doc = doc;

    this.highlighter.clear();
    this.timeline = this.createTimeline(doc);
    this.cameraRig.fitToBounds(doc.bounds);

    this.store.set({
      selectedStitchId: null,
      hoveredStitchId: null,
      isolatedRoundKey: null,
      roundRange: null,
      hiddenComponentIds: new Set(),
      clipping: { enabled: false, axis: "z", offset: 0, invert: false },
      animationIndex: doc.stitches.length,
      animationPlaying: false,
      // viewMode, cameraMode, opacity, animationSpeed deliberately untouched
      // — user display preferences survive a recompile.
    });
  }

  private buildSceneObjects(
    doc: GeometryDocument,
    jsonSizeBytes: number,
  ): { structural: StructuralScene; yarnMeshes: THREE.Mesh[]; stats: PerformanceStats } {
    const genStart = performance.now();
    const structural = buildStructuralScene(doc);
    for (const group of structural.groups) this.scene.add(group.mesh);

    const yarnMeshes = buildYarnMeshes(doc);
    for (const mesh of yarnMeshes) {
      mesh.visible = false;
      this.scene.add(mesh);
    }
    const genEnd = performance.now();

    let triangles = 0;
    for (const group of structural.groups) {
      const positionCount = group.mesh.geometry.getAttribute("position").count;
      triangles += (positionCount / 3) * group.mesh.count;
    }

    const stats: PerformanceStats = {
      stitchCount: doc.stitches.length,
      yarnSegmentCount: doc.yarn_segments.length,
      triangleCount: Math.round(triangles),
      drawCalls: structural.groups.length,
      geometryGenerationMs: genEnd - genStart,
      jsonSizeBytes,
    };

    return { structural, yarnMeshes, stats };
  }

  private createTimeline(doc: GeometryDocument): ConstructionTimeline {
    return new ConstructionTimeline(doc.stitches, (index) => {
      this.store.set({ animationIndex: index });
    });
  }

  private disposeStructural(structural: StructuralScene): void {
    const disposedGeometries = new Set<THREE.BufferGeometry>();
    for (const group of structural.groups) {
      this.scene.remove(group.mesh);
      if (!disposedGeometries.has(group.mesh.geometry)) {
        group.mesh.geometry.dispose();
        disposedGeometries.add(group.mesh.geometry);
      }
      (group.mesh.material as THREE.Material).dispose();
    }
  }

  private disposeYarn(meshes: THREE.Mesh[]): void {
    for (const mesh of meshes) {
      this.scene.remove(mesh);
      mesh.geometry.dispose();
      (mesh.material as THREE.Material).dispose();
    }
  }

  getStore(): Store<ViewerState> {
    return this.store;
  }

  getTimeline(): ConstructionTimeline {
    return this.timeline;
  }

  getStats(): PerformanceStats {
    return this.stats;
  }

  /** Test-only hook (see e2e/compile-workflow.spec.ts): exposes Three.js's
   * own resource accounting so an end-to-end test can confirm repeated
   * `loadGeometryDocument` calls don't leak geometries/textures rather than
   * just trusting the disposal code by inspection. */
  getRendererInfo(): THREE.WebGLInfo {
    return this.renderer.info;
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
