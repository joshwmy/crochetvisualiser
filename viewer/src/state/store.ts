// Minimal framework-free reactive state. No React: the interaction surface
// for slice 1 (a handful of panels driven by one geometry document) doesn't
// justify a state-management library.

export type ViewMode = "structural" | "yarn";

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
}

export type Listener = (state: ViewerState) => void;

export class Store {
  private state: ViewerState;
  private listeners: Set<Listener> = new Set();

  constructor(initial: ViewerState) {
    this.state = initial;
  }

  get(): ViewerState {
    return this.state;
  }

  set(patch: Partial<ViewerState>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener(this.state);
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

export function createInitialState(stitchCount: number): ViewerState {
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
  };
}
