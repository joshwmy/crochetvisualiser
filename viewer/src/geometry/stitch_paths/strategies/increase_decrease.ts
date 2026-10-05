import type { StitchGeometry } from "../../../types/geometry";
import { lerp } from "../common";
import type { StitchPathContext, StitchPathResult, StitchPathSegment } from "../types";

/**
 * Increase/decrease are not their own stitch *types* in this domain model
 * (an increase's `IncreaseOp.stitch` field is still sc/hdc/dc) — they are a
 * property of any plain stitch. So instead of separate strategies, this
 * module augments a base strategy's result with the extra branch/bridge
 * segment the brief requires, called from strategies/index.ts after the
 * type-specific strategy has already run.
 */
export function augmentForIncrease(
  base: StitchPathResult,
  stitch: StitchGeometry,
  context: StitchPathContext,
): StitchPathResult {
  const parentId = stitch.parent_stitch_ids[0];
  const parent = parentId ? context.getStitch(parentId) : undefined;
  if (!parent) return base;

  // Both increase children share this one parent (see graph/builder.py's
  // `increase_group_id`); each child independently draws a branch back to
  // the shared parent position. Rendered together, two children's branches
  // form a visible fan/V from one point — no extra backend data needed
  // since both children already carry the same `parent_stitch_ids[0]`.
  const branch: StitchPathSegment = {
    role: "increase_branch",
    controlPoints: [parent.position, base.entryPoint],
    radius: context.yarnRadiusCm * 0.9,
    curveType: "line",
    closed: false,
  };
  return { ...base, segments: [...base.segments, branch] };
}

export function augmentForDecrease(
  base: StitchPathResult,
  stitch: StitchGeometry,
  context: StitchPathContext,
): StitchPathResult {
  const parents = stitch.parent_stitch_ids
    .map((id) => context.getStitch(id))
    .filter((s): s is StitchGeometry => s !== undefined);
  if (parents.length < 2) return base;

  const [first, second] = parents;
  const midpoint = lerp(first.position, second.position, 0.5);
  const bridge: StitchPathSegment = {
    role: "decrease_bridge",
    controlPoints: [first.position, midpoint, second.position],
    radius: context.yarnRadiusCm * 0.9,
    curveType: "catmull_rom",
    closed: false,
  };
  const converge: StitchPathSegment = {
    role: "decrease_bridge",
    controlPoints: [midpoint, base.entryPoint],
    radius: context.yarnRadiusCm * 0.9,
    curveType: "line",
    closed: false,
  };
  return { ...base, segments: [...base.segments, bridge, converge] };
}
