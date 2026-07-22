import type { StitchGeometry } from "../../src/types/geometry";
import type { StitchPathContext } from "../../src/geometry/stitch_paths/types";

let counter = 0;

/** A minimal, valid, orthonormal-framed synthetic stitch for strategy unit tests. */
export function makeStitch(overrides: Partial<StitchGeometry> = {}): StitchGeometry {
  counter += 1;
  const angle = counter * 0.3;
  return {
    stitch_id: `test-r01-s${String(counter).padStart(3, "0")}`,
    component_id: "piece",
    stitch_type: "sc",
    round_index: 1,
    sequence_index: counter,
    position: [Math.cos(angle) * 2, Math.sin(angle) * 2, 0],
    orientation: [0, 0, 0, 1],
    tangent: [-Math.sin(angle), Math.cos(angle), 0],
    normal: [Math.cos(angle), Math.sin(angle), 0],
    binormal: [0, 0, 1],
    scale: 1,
    loop_placement: "both",
    colour_id: "main",
    yarn_id: "main",
    parent_stitch_ids: [],
    is_increase: false,
    is_decrease: false,
    source_reference: "test fixture",
    ...overrides,
  };
}

export function makeContext(overrides: Partial<StitchPathContext> = {}): StitchPathContext {
  const stitches = new Map<string, StitchGeometry>();
  return {
    getStitch: (id) => stitches.get(id),
    yarnRadiusCm: 0.15,
    rowHeightCm: 0.8,
    ...overrides,
  };
}

/** A context backed by a real list of stitches, for parent-lookup scenarios. */
export function makeContextWithStitches(stitches: StitchGeometry[]): StitchPathContext {
  const byId = new Map(stitches.map((s) => [s.stitch_id, s]));
  return {
    getStitch: (id) => byId.get(id),
    yarnRadiusCm: 0.15,
    rowHeightCm: 0.8,
  };
}

export function resetCounter(): void {
  counter = 0;
}
