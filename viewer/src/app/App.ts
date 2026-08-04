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
  type YarnPathScene,
} from "../geometry/build_yarn_paths";
import { applyYarnMaterialState } from "../materials/yarn_material";
import { Picker } from "../selection/picking";
import { buildHitProxyScene, disposeHitProxyScene } from "../selection/hit_proxies";
import { SelectionHighlighter } from "../selection/highlight";
import { buildGraphOverlay } from "../selection/graph_overlay";
import { buildPathInspectionMeshes } from "../selection/path_inspection";
import type { SegmentRole, StitchPathResult } from "../geometry/stitch_paths/types";
import {
  buildMeasurementLine,
  createObjectHeightMeasurement,
  createObjectWidthMeasurement,
  createPointDistanceMeasurement,
  createRoundCircumferenceMeasurement,
  measureDistance,
} from "../measurement/measurement";
import {
  buildAnnotationMarker,
  createPointAnnotation,
  createStitchAnnotation,
  updateAnnotationText,
} from "../annotations/annotations";
import type { Vec3 } from "../types/geometry";
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
  /** Invisible per-stitch spheres raycasted against for picking in every
   * view mode — see selection/hit_proxies.ts for why this exists as a
   * separate mesh set instead of reusing the structural meshes. */
  private hitProxies: StructuralScene;
  private currentQuality: QualityName;
  private picker = new Picker();
  private highlighter: SelectionHighlighter;
  private timeline: ConstructionTimeline;
  private store: Store<ViewerState>;
  private canvas: HTMLCanvasElement;
  private doc: GeometryDocument;
  private stats: PerformanceStats;
  private selectedOverlay: THREE.Mesh | null = null;
  private pathContextOverlay: THREE.Mesh | null = null;
  private graphOverlayObject: THREE.LineSegments | null = null;
  private measurementLines: Map<string, THREE.Line> = new Map();
  private annotationMarkers: Map<string, THREE.LineSegments> = new Map();

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
    this.hitProxies = built.hitProxies;
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
    const previousHitProxies = this.hitProxies;

    const quality = this.store ? this.store.get().quality : this.currentQuality;
    const built = this.buildSceneObjects(doc, jsonSizeBytes, quality);

    // Only after the new scene objects are successfully built do we tear
    // down the old ones and swap state — this ordering means a throw
    // inside buildSceneObjects (e.g. a malformed but schema-valid document)
    // leaves the previous valid model fully intact and on screen.
    this.disposeStructural(previousStructural);
    this.disposeYarnScene(previousYarn);
    disposeHitProxyScene(this.scene, previousHitProxies);
    this.disposeOverlays();

    this.structural = built.structural;
    this.yarnScene = built.yarnScene;
    this.hitProxies = built.hitProxies;
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
      pendingMeasurementPoint: null,
      // Annotations are anchored to this model's stitch ids and world
      // positions, so they are cleared alongside measurements rather than
      // being silently re-pointed at whatever stitch now holds the same id.
      annotations: [],
      pendingAnnotationAnchor: null,
      editingAnnotationId: null,
      graphOverlay: false,
      pathModeActive: false,
      pathFocusRole: null,
      // viewMode, cameraMode, opacity, quality, xray, animationSpeed
      // deliberately untouched — user display preferences survive a recompile.
    });
  }

  private buildSceneObjects(
    doc: GeometryDocument,
    jsonSizeBytes: number,
    quality: QualityName,
  ): {
    structural: StructuralScene;
    yarnScene: YarnPathScene;
    hitProxies: StructuralScene;
    stats: PerformanceStats;
  } {
    const genStart = performance.now();
    const structural = buildStructuralScene(doc);
    for (const group of structural.groups) this.scene.add(group.mesh);

    const hitProxies = buildHitProxyScene(doc);
    for (const group of hitProxies.groups) this.scene.add(group.mesh);

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

    return { structural, yarnScene, hitProxies, stats };
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
    if (this.pathContextOverlay) {
      this.scene.remove(this.pathContextOverlay);
      this.pathContextOverlay.geometry.dispose();
      (this.pathContextOverlay.material as THREE.Material).dispose();
      this.pathContextOverlay = null;
    }
    for (const line of this.measurementLines.values()) {
      this.scene.remove(line);
      line.geometry.dispose();
      (line.material as THREE.Material).dispose();
    }
    this.measurementLines.clear();
    for (const marker of this.annotationMarkers.values()) {
      this.scene.remove(marker);
      marker.geometry.dispose();
      (marker.material as THREE.Material).dispose();
    }
    this.annotationMarkers.clear();
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

  /** Test-only hook (see e2e/compile-workflow.spec.ts): proves the
   * documented clipping policy (applyClipping's docstring) by inspecting
   * actual material.clippingPlanes state, rather than trusting the code by
   * inspection alone. `null` for a field means that overlay doesn't
   * currently exist (e.g. no measurement recorded yet). */
  getClippingDebugInfo(): {
    graphOverlayClipped: boolean | null;
    measurementClipped: boolean | null;
    selectionMarkerClipped: boolean;
  } {
    const hasPlanes = (material: THREE.Material): boolean => (material.clippingPlanes?.length ?? 0) > 0;
    const firstMeasurementLine = this.measurementLines.values().next().value as THREE.Line | undefined;
    return {
      graphOverlayClipped: this.graphOverlayObject
        ? hasPlanes(this.graphOverlayObject.material as THREE.Material)
        : null,
      measurementClipped: firstMeasurementLine ? hasPlanes(firstMeasurementLine.material as THREE.Material) : null,
      selectionMarkerClipped: hasPlanes(this.highlighter.getMarkerMesh().material as THREE.Material),
    };
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

  /** Unique semantic path roles present on a stitch's yarn geometry — drives
   * the path-inspection role picker/legend. Empty if the stitch has no
   * yarn-path result (e.g. no document loaded yet). */
  getPathRoles(stitchId: string): SegmentRole[] {
    const result = this.yarnScene.pathResultsByStitch.get(stitchId);
    return result ? [...new Set(result.segments.map((s) => s.role))] : [];
  }

  /** The immediate parent's and next-yarn-sequence stitch's own path
   * results, for path-inspection mode's optional dimmed context (never the
   * whole model — see selection/path_inspection.ts). */
  private getPathContext(stitchId: string): { parent?: StitchPathResult; next?: StitchPathResult } {
    const stitch = this.getStitch(stitchId);
    const parentId = stitch?.parent_stitch_ids[0];
    const parent = parentId ? this.yarnScene.pathResultsByStitch.get(parentId) : undefined;

    const nextEdge = this.doc.edges.find((e) => e.edge_type === "yarn_sequence" && e.source_id === stitchId);
    const next = nextEdge ? this.yarnScene.pathResultsByStitch.get(nextEdge.target_id) : undefined;

    return { parent, next };
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
    const state = this.store.get();

    // Annotation mode is checked before measurement mode so that, if both are
    // somehow toggled on, one click has exactly one meaning. The UI keeps
    // them mutually exclusive (main.ts turns each off when the other is
    // enabled); this ordering makes the behaviour defined regardless.
    if (state.annotationModeActive) {
      if (state.annotationPointMode) {
        const point = this.raycastPoint(event);
        if (!point) return;
        this.store.set({ pendingAnnotationAnchor: { kind: "point", point } });
      } else {
        const clickedStitchId = this.pickStitch(event);
        if (!clickedStitchId) return;
        this.store.set({
          pendingAnnotationAnchor: { kind: "stitch", stitchId: clickedStitchId },
          selectedStitchId: clickedStitchId,
        });
      }
      return;
    }

    if (state.measurementModeActive && state.measurementPointMode) {
      const point = this.raycastPoint(event);
      if (!point) return;
      if (state.pendingMeasurementPoint === null) {
        this.store.set({ pendingMeasurementPoint: point });
      } else {
        const measurement = createPointDistanceMeasurement(this.doc, state.pendingMeasurementPoint, point);
        this.store.set({
          measurements: [...state.measurements, measurement],
          pendingMeasurementPoint: null,
        });
      }
      return;
    }

    const stitchId = this.pickStitch(event);

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

  /** Raw raycast hit point, in world space — unlike pickStitch, does not
   * resolve to a stitch id. Used for arbitrary point-to-point measurement,
   * which must work regardless of whether the click happens to land near a
   * stitch's exact geometry. */
  private raycastPoint(event: PointerEvent): Vec3 | null {
    const rect = this.canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, this.cameraRig.active);
    const state = this.store.get();
    const meshes =
      state.viewMode === "structural"
        ? this.structural.groups.map((g) => g.mesh)
        : this.yarnScene.components.map((c) => c.mesh);
    const hits = raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return null;
    const { x, y, z } = hits[0].point;
    return [x, y, z];
  }

  /** Appends an object-width measurement (max of the model's X/Y bounding-box
   * extents) — see measurement/measurement.ts for why max, not X specifically. */
  addObjectWidthMeasurement(): void {
    const measurement = createObjectWidthMeasurement(this.doc);
    this.store.set({ measurements: [...this.store.get().measurements, measurement] });
  }

  /** Appends an object-height measurement (the model's Z bounding-box extent). */
  addObjectHeightMeasurement(): void {
    const measurement = createObjectHeightMeasurement(this.doc);
    this.store.set({ measurements: [...this.store.get().measurements, measurement] });
  }

  /** Appends a round-circumference measurement for the currently selected
   * stitch's round. Returns false (no-op) if nothing is selected — the
   * caller (main.ts) uses this to keep the triggering button disabled
   * rather than silently failing on click. */
  addRoundCircumferenceMeasurementForSelection(): boolean {
    const stitchId = this.store.get().selectedStitchId;
    const stitch = stitchId ? this.getStitch(stitchId) : null;
    if (!stitch) return false;
    const measurement = createRoundCircumferenceMeasurement(this.doc, stitch.component_id, stitch.round_index);
    if (!measurement) return false;
    this.store.set({ measurements: [...this.store.get().measurements, measurement] });
    return true;
  }

  /**
   * Creates an annotation from the pending anchor and the supplied text.
   *
   * Returns false without changing anything when there is no pending anchor,
   * when the text is empty/whitespace-only, or when a stitch anchor no longer
   * resolves — so the caller can keep its confirm button disabled rather than
   * producing an unlabelled or dangling marker.
   */
  addAnnotationFromPending(text: string): boolean {
    const state = this.store.get();
    const anchor = state.pendingAnnotationAnchor;
    if (!anchor) return false;

    const annotation =
      anchor.kind === "stitch"
        ? createStitchAnnotation(this.doc, anchor.stitchId, text)
        : createPointAnnotation(this.doc, anchor.point, text);
    if (!annotation) return false;

    this.store.set({
      annotations: [...state.annotations, annotation],
      pendingAnnotationAnchor: null,
    });
    return true;
  }

  /** Replaces one annotation's text, leaving its id and anchor untouched.
   * Returns false for an unknown id or empty text — an edit must never blank
   * an annotation out; removing is a separate, explicit action. */
  editAnnotationText(annotationId: string, text: string): boolean {
    const state = this.store.get();
    const existing = state.annotations.find((a) => a.id === annotationId);
    if (!existing) return false;
    const updated = updateAnnotationText(existing, text);
    if (!updated) return false;

    this.store.set({
      annotations: state.annotations.map((a) => (a.id === annotationId ? updated : a)),
      editingAnnotationId: null,
    });
    return true;
  }

  removeAnnotation(annotationId: string): void {
    const state = this.store.get();
    this.store.set({
      annotations: state.annotations.filter((a) => a.id !== annotationId),
      editingAnnotationId:
        state.editingAnnotationId === annotationId ? null : state.editingAnnotationId,
    });
  }

  /** Picks a stitch id via the invisible hit-proxy spheres (selection/
   * hit_proxies.ts) — the same fast `InstancedMesh` raycast in every view
   * mode, regardless of which geometry (structural capsules, yarn tubes)
   * is currently rendered. See hit_proxies.ts's module docstring for the
   * measured yarn-mode raycast cost this replaces. */
  private pickStitch(event: PointerEvent): string | null {
    return this.picker.pick(event, this.canvas, this.cameraRig.active, this.hitProxies);
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
    this.applySelectedOverlay(state);
    this.applyGraphOverlay(state);
    this.applyMeasurements(state);
    this.applyAnnotations(state);
    // Runs last: applySelectedOverlay/applyGraphOverlay/applyMeasurements
    // rebuild their objects from scratch on every call, so clipping must be
    // (re-)applied afterwards to reach the fresh materials, not the
    // disposed previous ones.
    this.applyClipping(state);
  }

  private applyPerStitchVisibility(state: ViewerState): void {
    const [roundComponent, roundIndexStr] = state.isolatedRoundKey?.split(":") ?? [null, null];
    const roundIndex = roundIndexStr ? Number(roundIndexStr) : null;

    // Hit-proxy instances are hidden (zero-scaled, unpickable) in lockstep
    // with the structural ones — animation/round-isolation/component-hide
    // state must affect *what can be picked* the same way in every view
    // mode, even though only structural mode also visibly hides geometry.
    for (const group of this.hitProxies.groups) {
      group.mesh.visible = !state.hiddenComponentIds.has(group.componentId);
    }

    const touchedGroups = new Set(this.structural.groups);
    const touchedProxyGroups = new Set(this.hitProxies.groups);
    for (const stitch of this.doc.stitches) {
      const location = this.structural.stitchIdToLocation.get(stitch.stitch_id);
      const proxyLocation = this.hitProxies.stitchIdToLocation.get(stitch.stitch_id);
      if (!location || !proxyLocation) continue;
      const withinAnimation = stitch.sequence_index < state.animationIndex;
      const withinIsolation =
        roundIndex === null ||
        (stitch.component_id === roundComponent && stitch.round_index === roundIndex);
      const hidden = !withinAnimation || !withinIsolation;
      setInstanceHidden(location.group, location.index, hidden);
      setInstanceHidden(proxyLocation.group, proxyLocation.index, hidden);
      touchedGroups.add(location.group);
      touchedProxyGroups.add(proxyLocation.group);
    }
    for (const group of touchedGroups) commitMatrixUpdates(group);
    for (const group of touchedProxyGroups) commitMatrixUpdates(group);
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

  /**
   * Clipping policy (documented, not accidental — see
   * docs/clipping-and-section-views.md):
   *
   * - Structural and yarn geometry are clipped: they represent the actual
   *   model, so a clip plane should hide what it geometrically cuts away.
   * - The graph overlay and measurement lines are also clipped: they
   *   represent real edges/distances *of* that geometry, so they should
   *   track what's actually visible rather than floating through a
   *   clipped-away region as if unaffected.
   * - The selection marker (highlight.ts's torus) and the selected-stitch/
   *   path-inspection overlay are deliberately EXCLUDED from clipping: they
   *   exist so the user never loses track of *where* their current
   *   selection is, even if the clip plane currently hides it — an
   *   "always know where you are" indicator, not part of the model itself.
   */
  private applyClipping(state: ViewerState): void {
    const plane = state.clipping.enabled ? buildClippingPlane(this.doc.bounds, state.clipping) : null;
    const materials = [
      ...this.structural.groups.map((g) => g.mesh.material as THREE.Material),
      ...this.yarnScene.components.map((c) => c.mesh.material as THREE.Material),
    ];
    if (this.graphOverlayObject) materials.push(this.graphOverlayObject.material as THREE.Material);
    for (const line of this.measurementLines.values()) materials.push(line.material as THREE.Material);
    // Annotation markers are clipped like the model and the measurement
    // lines: an annotation on a stitch that the clipping plane has cut away
    // should disappear with it. The selection marker remains the one
    // deliberate exception (docs/clipping-and-section-views.md).
    for (const marker of this.annotationMarkers.values()) {
      materials.push(marker.material as THREE.Material);
    }
    applyClippingToMaterials(materials, plane);
  }

  /** In x-ray/yarn mode, the selected stitch gets its own small, always-opaque
   * copy of its yarn geometry drawn on top — satisfying "selected stitch
   * remains clear and opaque" without needing per-triangle material control
   * over the merged, translucent component mesh.
   *
   * When path-inspection mode is active, this becomes the path-inspection
   * render instead: segments coloured per semantic role (optionally
   * filtered to one focused role), plus a dimmed, flat-coloured render of
   * the immediate parent/next-in-sequence stitch for context — never the
   * whole model (see selection/path_inspection.ts). Both variants share
   * one overlay lifecycle so there is exactly one "selected stitch is
   * always visible" mesh to dispose, never two competing ones. */
  private applySelectedOverlay(state: ViewerState): void {
    if (this.selectedOverlay) {
      this.scene.remove(this.selectedOverlay);
      this.selectedOverlay.geometry.dispose();
      (this.selectedOverlay.material as THREE.Material).dispose();
      this.selectedOverlay = null;
    }
    if (this.pathContextOverlay) {
      this.scene.remove(this.pathContextOverlay);
      this.pathContextOverlay.geometry.dispose();
      (this.pathContextOverlay.material as THREE.Material).dispose();
      this.pathContextOverlay = null;
    }
    if (state.viewMode !== "yarn" || !state.selectedStitchId) return;
    const result = this.yarnScene.pathResultsByStitch.get(state.selectedStitchId);
    if (!result) return;

    if (state.pathModeActive) {
      const context = this.getPathContext(state.selectedStitchId);
      const built = buildPathInspectionMeshes(result, state.pathFocusRole, context);
      if (built.focusMesh) {
        this.selectedOverlay = built.focusMesh;
        this.scene.add(this.selectedOverlay);
      }
      if (built.contextMesh) {
        this.pathContextOverlay = built.contextMesh;
        this.scene.add(this.pathContextOverlay);
      }
      return;
    }

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

  /** Adds/removes annotation markers to match the store, reusing existing
   * markers by id. Text edits deliberately do not rebuild the marker — the
   * marker encodes only the anchor, and the text lives in the side panel
   * (see annotations/annotations.ts's buildAnnotationMarker). */
  private applyAnnotations(state: ViewerState): void {
    const currentIds = new Set(state.annotations.map((a) => a.id));
    for (const [id, marker] of this.annotationMarkers) {
      if (!currentIds.has(id)) {
        this.scene.remove(marker);
        marker.geometry.dispose();
        (marker.material as THREE.Material).dispose();
        this.annotationMarkers.delete(id);
      }
    }
    const markerRadiusCm = 0.5 / this.doc.gauge.stitches_per_cm;
    for (const annotation of state.annotations) {
      if (this.annotationMarkers.has(annotation.id)) continue;
      const marker = buildAnnotationMarker(this.doc, annotation, markerRadiusCm);
      if (!marker) continue;
      this.annotationMarkers.set(annotation.id, marker);
      this.scene.add(marker);
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
