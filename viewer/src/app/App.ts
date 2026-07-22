import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { GeometryDocument } from "../types/geometry";
import { validateGeometry } from "../geometry/load";
import { createScene, applyLightingPreset, type LightingPreset } from "../scene/scene";
import { CameraRig, type ViewPreset } from "../camera/camera";
import { createRenderer } from "../rendering/renderer";
import { buildStructuralScene, commitMatrixUpdates, setInstanceHidden } from "../geometry/build_meshes";
import type { StructuralScene } from "../geometry/build_meshes";
import {
  buildYarnPathScene,
  defaultQualityFor,
  QUALITY_PRESETS,
  stitchIdForFace,
  type YarnPathScene,
} from "../geometry/build_yarn_paths";
import { applyYarnMaterialState } from "../materials/yarn_material";
import { Picker } from "../selection/picking";
import { SelectionHighlighter } from "../selection/highlight";
import { buildGraphOverlay } from "../selection/graph_overlay";
import { buildMeasurementLine, measureDistance } from "../measurement/measurement";
import { ConstructionTimeline } from "../animation/construction";
import { buildClippingPlane, applyClippingToMaterials } from "../clipping/clipping";
import { Store, createInitialState, type QualityName, type ViewerState } from "../state/store";

export interface PerformanceStats {
  stitchCount: number;
  yarnSegmentCount: number;
  triangleCount: number;
  drawCalls: number;
  geometryGenerationMs: number;
  jsonSizeBytes: number;
  yarnPathTriangleCount: number;
  yarnPathSegmentCount: number;
  yarnPathControlPointCount: number;
}

export class App {
  private scene: THREE.Scene;
  private renderer: THREE.WebGLRenderer;
  private cameraRig: CameraRig;
  private structural: StructuralScene;
  private yarnScene: YarnPathScene;
  private currentQuality: QualityName;
  private picker = new Picker();
  private highlighter: SelectionHighlighter;
  private timeline: ConstructionTimeline;
  private store: Store<ViewerState>;
  private canvas: HTMLCanvasElement;
  private doc: GeometryDocument;
  private stats: PerformanceStats;
  private selectedOverlay: THREE.Mesh | null = null;
  private graphOverlayObject: THREE.LineSegments | null = null;
  private measurementLines: Map<string, THREE.Line> = new Map();

  constructor(canvas: HTMLCanvasElement, doc: GeometryDocument, jsonSizeBytes: number) {
    this.canvas = canvas;
    this.doc = doc;
    this.currentQuality = defaultQualityFor(doc.stitches.length);

    this.scene = createScene();
    this.renderer = createRenderer(canvas);
    this.cameraRig = new CameraRig(canvas, canvas.clientWidth / canvas.clientHeight || 1);
    this.highlighter = new SelectionHighlighter(this.scene);

    const built = this.buildSceneObjects(doc, jsonSizeBytes, this.currentQuality);
    this.structural = built.structural;
    this.yarnScene = built.yarnScene;
    this.stats = built.stats;
    for (const comp of this.yarnScene.components) comp.mesh.visible = false;
    this.cameraRig.fitToBounds(doc.bounds);

    this.store = new Store(createInitialState(doc.stitches.length, this.currentQuality));
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
   * previous model (geometries, materials, overlays, measurement lines),
   * rebuilds structural + yarn-path representations, and resets selection/
   * isolation/animation/clipping/measurement state to fresh defaults for the
   * new bounds — while preserving user display preferences (view mode,
   * camera projection, opacity, quality) across the swap. Throws
   * (asynchronously, via the returned rejected promise) without touching
   * any current scene state if `doc` fails validation — a failed load must
   * never leave a half-updated viewer.
   */
  async loadGeometryDocument(doc: GeometryDocument, jsonSizeBytes = 0): Promise<void> {
    validateGeometry(doc);

    const previousStructural = this.structural;
    const previousYarn = this.yarnScene;

    const quality = this.store ? this.store.get().quality : this.currentQuality;
    const built = this.buildSceneObjects(doc, jsonSizeBytes, quality);

    // Only after the new scene objects are successfully built do we tear
    // down the old ones and swap state — this ordering means a throw
    // inside buildSceneObjects (e.g. a malformed but schema-valid document)
    // leaves the previous valid model fully intact and on screen.
    this.disposeStructural(previousStructural);
    this.disposeYarnScene(previousYarn);
    this.disposeOverlays();

    this.structural = built.structural;
    this.yarnScene = built.yarnScene;
    this.stats = built.stats;
    this.doc = doc;
    this.currentQuality = quality;

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
      measurements: [],
      pendingMeasurementStitchId: null,
      graphOverlay: false,
      // viewMode, cameraMode, opacity, quality, xray, animationSpeed
      // deliberately untouched — user display preferences survive a recompile.
    });
  }

  private buildSceneObjects(
    doc: GeometryDocument,
    jsonSizeBytes: number,
    quality: QualityName,
  ): { structural: StructuralScene; yarnScene: YarnPathScene; stats: PerformanceStats } {
    const genStart = performance.now();
    const structural = buildStructuralScene(doc);
    for (const group of structural.groups) this.scene.add(group.mesh);

    const yarnScene = buildYarnPathScene(doc, QUALITY_PRESETS[quality]);
    for (const comp of yarnScene.components) this.scene.add(comp.mesh);
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
      yarnPathTriangleCount: yarnScene.stats.triangleCount,
      yarnPathSegmentCount: yarnScene.stats.segmentCount,
      yarnPathControlPointCount: yarnScene.stats.controlPointCount,
    };

    return { structural, yarnScene, stats };
  }

  setQuality(quality: QualityName): void {
    if (quality === this.currentQuality) return;
    const previousYarn = this.yarnScene;
    const rebuilt = buildYarnPathScene(this.doc, QUALITY_PRESETS[quality]);
    for (const comp of rebuilt.components) {
      this.scene.add(comp.mesh);
      comp.mesh.visible = this.store.get().viewMode === "yarn";
    }
    this.disposeYarnScene(previousYarn);
    this.yarnScene = rebuilt;
    this.currentQuality = quality;
    // Keep the store in sync so loadGeometryDocument's "preserve the user's
    // quality choice across a recompile" logic reads the real current
    // value, not whatever quality was selected at construction time.
    this.store.set({ quality });
  }

  setLightingPreset(preset: LightingPreset): void {
    applyLightingPreset(this.scene, preset);
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

  private disposeYarnScene(yarnScene: YarnPathScene): void {
    for (const comp of yarnScene.components) {
      this.scene.remove(comp.mesh);
      comp.mesh.geometry.dispose();
      (comp.mesh.material as THREE.Material).dispose();
    }
  }

  private disposeOverlays(): void {
    if (this.selectedOverlay) {
      this.scene.remove(this.selectedOverlay);
      this.selectedOverlay.geometry.dispose();
      (this.selectedOverlay.material as THREE.Material).dispose();
      this.selectedOverlay = null;
    }
    if (this.graphOverlayObject) {
      this.scene.remove(this.graphOverlayObject);
      this.graphOverlayObject.geometry.dispose();
      (this.graphOverlayObject.material as THREE.Material).dispose();
      this.graphOverlayObject = null;
    }
    for (const line of this.measurementLines.values()) {
      this.scene.remove(line);
      line.geometry.dispose();
      (line.material as THREE.Material).dispose();
    }
    this.measurementLines.clear();
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

  getYarnPathResult(stitchId: string) {
    return this.yarnScene.pathResultsByStitch.get(stitchId) ?? null;
  }

  getYarnWarnings(stitchId: string): string[] {
    return this.yarnScene.warningsByStitch.get(stitchId) ?? [];
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
    const stitchId = this.pickStitch(event);
    const state = this.store.get();

    if (state.measurementModeActive && stitchId) {
      if (state.pendingMeasurementStitchId === null) {
        this.store.set({ pendingMeasurementStitchId: stitchId, selectedStitchId: stitchId });
      } else if (state.pendingMeasurementStitchId !== stitchId) {
        const measurement = measureDistance(this.doc, state.pendingMeasurementStitchId, stitchId);
        if (measurement) {
          this.store.set({
            measurements: [...state.measurements, measurement],
            pendingMeasurementStitchId: null,
            selectedStitchId: stitchId,
          });
        }
      }
      return;
    }

    this.store.set({ selectedStitchId: stitchId });
  }

  private pickStitch(event: PointerEvent): string | null {
    const state = this.store.get();
    if (state.viewMode === "structural") {
      return this.picker.pick(event, this.canvas, this.cameraRig.active, this.structural);
    }
    return this.pickYarn(event);
  }

  private pickYarn(event: PointerEvent): string | null {
    const rect = this.canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, this.cameraRig.active);
    const meshes = this.yarnScene.components.map((c) => c.mesh);
    const hits = raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return null;
    const hit = hits[0];
    const comp = this.yarnScene.components.find((c) => c.mesh === hit.object);
    if (!comp || hit.faceIndex === undefined || hit.faceIndex === null) return null;
    return stitchIdForFace(comp.faceRanges, hit.faceIndex);
  }

  private applyState(state: ViewerState): void {
    this.highlighter.select(state.viewMode === "structural" ? state.selectedStitchId : null, this.structural);

    const structuralVisible = state.viewMode === "structural";
    for (const group of this.structural.groups) {
      group.mesh.visible = structuralVisible && !state.hiddenComponentIds.has(group.componentId);
    }
    for (const comp of this.yarnScene.components) {
      comp.mesh.visible = !structuralVisible && !state.hiddenComponentIds.has(comp.componentId);
    }

    this.applyPerStitchVisibility(state);
    this.applyOpacityAndXray(state);
    this.applyClipping(state);
    this.applySelectedOverlay(state);
    this.applyGraphOverlay(state);
    this.applyMeasurements(state);
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

  private applyOpacityAndXray(state: ViewerState): void {
    const effectiveOpacity = state.xray ? Math.min(state.opacity, 0.22) : state.opacity;
    for (const group of this.structural.groups) {
      const material = group.mesh.material as THREE.MeshStandardMaterial;
      material.opacity = effectiveOpacity;
      material.transparent = effectiveOpacity < 1;
      material.depthWrite = effectiveOpacity >= 0.98;
    }
    for (const comp of this.yarnScene.components) {
      applyYarnMaterialState(comp.mesh.material as THREE.MeshPhysicalMaterial, {
        opacity: state.opacity,
        xray: state.xray,
      });
    }
  }

  private applyClipping(state: ViewerState): void {
    const plane = state.clipping.enabled ? buildClippingPlane(this.doc.bounds, state.clipping) : null;
    const materials = [
      ...this.structural.groups.map((g) => g.mesh.material as THREE.Material),
      ...this.yarnScene.components.map((c) => c.mesh.material as THREE.Material),
    ];
    applyClippingToMaterials(materials, plane);
  }

  /** In x-ray/yarn mode, the selected stitch gets its own small, always-opaque
   * copy of its yarn geometry drawn on top — satisfying "selected stitch
   * remains clear and opaque" without needing per-triangle material control
   * over the merged, translucent component mesh. */
  private applySelectedOverlay(state: ViewerState): void {
    if (this.selectedOverlay) {
      this.scene.remove(this.selectedOverlay);
      this.selectedOverlay.geometry.dispose();
      (this.selectedOverlay.material as THREE.Material).dispose();
      this.selectedOverlay = null;
    }
    if (state.viewMode !== "yarn" || !state.selectedStitchId) return;
    const result = this.yarnScene.pathResultsByStitch.get(state.selectedStitchId);
    if (!result) return;

    const geometries: THREE.BufferGeometry[] = [];
    for (const segment of result.segments) {
      const points = segment.controlPoints.map((p) => new THREE.Vector3(...p));
      if (points.length < 2) continue;
      geometries.push(new THREE.TubeGeometry(
        new THREE.CatmullRomCurve3(points, segment.closed),
        Math.max(points.length * 2, 8),
        segment.radius * 1.05,
        8,
        segment.closed,
      ));
    }
    if (geometries.length === 0) return;
    const merged = mergeGeometries(geometries, false);
    geometries.forEach((g) => g.dispose());
    const material = new THREE.MeshBasicMaterial({ color: 0xf5e642, transparent: false, depthTest: true });
    this.selectedOverlay = new THREE.Mesh(merged, material);
    this.selectedOverlay.name = "selected-stitch-overlay";
    this.scene.add(this.selectedOverlay);
  }

  private applyGraphOverlay(state: ViewerState): void {
    if (this.graphOverlayObject) {
      this.scene.remove(this.graphOverlayObject);
      this.graphOverlayObject.geometry.dispose();
      (this.graphOverlayObject.material as THREE.Material).dispose();
      this.graphOverlayObject = null;
    }
    if (!state.graphOverlay || !state.selectedStitchId) return;
    this.graphOverlayObject = buildGraphOverlay(this.doc, state.selectedStitchId);
    this.scene.add(this.graphOverlayObject);
  }

  private applyMeasurements(state: ViewerState): void {
    const currentIds = new Set(state.measurements.map((m) => m.id));
    for (const [id, line] of this.measurementLines) {
      if (!currentIds.has(id)) {
        this.scene.remove(line);
        line.geometry.dispose();
        (line.material as THREE.Material).dispose();
        this.measurementLines.delete(id);
      }
    }
    for (const measurement of state.measurements) {
      if (this.measurementLines.has(measurement.id)) continue;
      const line = buildMeasurementLine(this.doc, measurement);
      if (!line) continue;
      this.measurementLines.set(measurement.id, line);
      this.scene.add(line);
    }
  }

  private renderLoop = (): void => {
    requestAnimationFrame(this.renderLoop);
    const now = performance.now();
    this.timeline.tick(now);
    this.cameraRig.update();
    this.renderer.render(this.scene, this.cameraRig.active);
  };
}
