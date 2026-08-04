// Minimal framework-free reactive state. No React: the interaction surface
// for slice 1 (a handful of panels driven by one geometry document) doesn't
// justify a state-management library.

import type { SegmentRole } from "../geometry/stitch_paths/types";
import type { Vec3 } from "../types/geometry";
import type { Measurement } from "../measurement/types";
import type { Annotation, AnnotationAnchor } from "../annotations/types";

export type { Measurement } from "../measurement/types";
export type { Annotation } from "../annotations/types";

export type ViewMode = "structural" | "yarn";
export type QualityName = "low" | "medium" | "high";

export interface ClippingState {
  enabled: boolean;
  axis: "x" | "y" | "z";
  offset: number; // -1..1, fraction of bounds extent along `axis`
  invert: boolean;
}

export interface ViewerState {
  selectedStitchId: string | null;
  hoveredStitchId: string | null;
  isolatedRoundKey: string | null; // `${component_id}:${round_index}` or null
  roundRange: [number, number] | null; // [minRoundIndex, maxRoundIndex] global filter
  hiddenComponentIds: Set<string>;
  opacity: number; // 0..1, global
  viewMode: ViewMode;
  cameraMode: "perspective" | "orthographic";
  clipping: ClippingState;
  animationIndex: number; // 0..stitchCount, stitches with sequence_index < this are "built"
  animationPlaying: boolean;
  animationSpeed: number; // stitches per second
  xray: boolean;
  quality: QualityName;
  graphOverlay: boolean;
  measurements: Measurement[];
  /** First stitch clicked while a measurement is in progress; cleared once the second click completes it. */
  pendingMeasurementStitchId: string | null;
  /** First raw click point recorded while an arbitrary point-to-point
   * measurement is in progress (measurementPointMode: true); cleared once
   * the second click completes it. Independent of pendingMeasurementStitchId
   * since the two measurement kinds record different click data. */
  pendingMeasurementPoint: Vec3 | null;
  measurementModeActive: boolean;
  /** false (default): clicks record stitch-to-stitch measurements. true:
   * clicks record arbitrary point-to-point measurements (raw raycast hit,
   * not snapped to a stitch). Only meaningful while measurementModeActive. */
  measurementPointMode: boolean;
  annotations: Annotation[];
  /** Anchor captured by the next click while annotation mode is active, held
   * until the user supplies text and confirms. Separate from the measurement
   * pending fields so a user can leave a half-started annotation and take a
   * measurement without either clobbering the other. */
  pendingAnnotationAnchor: AnnotationAnchor | null;
  annotationModeActive: boolean;
  /** false (default): clicks anchor an annotation to the clicked stitch.
   * true: clicks anchor it to the raw raycast hit point instead. Only
   * meaningful while annotationModeActive. Mirrors measurementPointMode. */
  annotationPointMode: boolean;
  /** Id of the annotation whose text is currently loaded into the editor, or
   * null when the editor would create a new annotation instead. */
  editingAnnotationId: string | null;
  /** Semantic stitch-path inspection mode (yarn-mode only) — see selection/path_inspection.ts. */
  pathModeActive: boolean;
  /** null means "highlight all roles"; a role narrows display to just that role. */
  pathFocusRole: SegmentRole | null;
}

export type Listener<T> = (state: T) => void;

/** Generic framework-free reactive store — also used by state/compile_store.ts. */
export class Store<T> {
  private state: T;
  private listeners: Set<Listener<T>> = new Set();

  constructor(initial: T) {
    this.state = initial;
  }

  get(): T {
    return this.state;
  }

  set(patch: Partial<T>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener(this.state);
  }

  subscribe(listener: Listener<T>): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

export function createInitialState(stitchCount: number, quality: QualityName = "medium"): ViewerState {
  return {
    selectedStitchId: null,
    hoveredStitchId: null,
    isolatedRoundKey: null,
    roundRange: null,
    hiddenComponentIds: new Set(),
    opacity: 1,
    viewMode: "structural",
    cameraMode: "perspective",
    clipping: { enabled: false, axis: "z", offset: 0, invert: false },
    animationIndex: stitchCount,
    animationPlaying: false,
    animationSpeed: 60,
    xray: false,
    quality,
    graphOverlay: false,
    measurements: [],
    pendingMeasurementStitchId: null,
    pendingMeasurementPoint: null,
    measurementModeActive: false,
    measurementPointMode: false,
    annotations: [],
    pendingAnnotationAnchor: null,
    annotationModeActive: false,
    annotationPointMode: false,
    editingAnnotationId: null,
    pathModeActive: false,
    pathFocusRole: null,
  };
}
