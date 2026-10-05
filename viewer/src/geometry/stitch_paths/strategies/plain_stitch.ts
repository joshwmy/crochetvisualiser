import type { StitchGeometry } from "../../../types/geometry";
import { add, frameOf, lerp, loopPoints, scale } from "../common";
import type { LoopAttachment, StitchPathContext, StitchPathResult, StitchPathSegment, Vec3 } from "../types";

/**
 * Shared builder for sc/hdc/dc: attach -> post -> (wraps) -> top loop -> exit.
 *
 * `heightFactor` and `wrapCount` are the only things that differ between the
 * three stitch types (see sc.ts/hdc.ts/dc.ts) — this is a deliberate,
 * documented cosmetic exaggeration: the underlying stitch *position* comes
 * unchanged from the backend's uniform-row-height layout (a separate,
 * already-documented limitation, see docs/known-limitations.md); only the
 * locally-drawn curve between a visually-lowered "attach" point and the
 * stitch's real position varies by type, which is enough to make sc/hdc/dc
 * visually distinguishable without touching the geometry-generation backend.
 */
export function buildPlainStitchPaths(
  stitch: StitchGeometry,
  context: StitchPathContext,
  opts: { strategyName: string; heightFactor: number; wrapCount: number },
): StitchPathResult {
  const { T, N, B, P } = frameOf(stitch);
  const warnings: string[] = [];
  const height = context.rowHeightCm * opts.heightFactor;
  const halfWidth = context.yarnRadiusCm * 3;

  let attachBase: Vec3 = add(P, scale(B, -height));
  const segments: StitchPathSegment[] = [];

  const parentId = stitch.parent_stitch_ids[0];
  const parent = parentId ? context.getStitch(parentId) : undefined;

  let loopAttachment: LoopAttachment;

  if (parent && stitch.loop_placement !== "both") {
    const lateral = stitch.loop_placement === "front_loop_only" ? 1 : -1;
    attachBase = add(attachBase, scale(parent.normal, lateral * context.yarnRadiusCm * 1.2));
    segments.push({
      role: stitch.loop_placement === "front_loop_only" ? "front_loop" : "back_loop",
      controlPoints: [parent.position, attachBase],
      radius: context.yarnRadiusCm,
      curveType: "line",
      closed: false,
    });
    warnings.push(
      `Loop placement (${stitch.loop_placement}) is shown as an approximate lateral offset, ` +
        "not an exact anatomical loop model.",
    );
    loopAttachment = {
      requested: stitch.loop_placement,
      resolved: "lateral offset approximation of the requested single loop — no strategy models two anatomically distinct loops",
      exact: false,
    };
  } else if (parent) {
    segments.push({
      role: "connector",
      controlPoints: [parent.position, attachBase],
      radius: context.yarnRadiusCm,
      curveType: "line",
      closed: false,
    });
    loopAttachment = {
      requested: stitch.loop_placement,
      resolved: "full stitch top (both loops) — the standard insertion, no loop split needed",
      exact: true,
    };
  } else {
    loopAttachment = {
      requested: stitch.loop_placement,
      resolved: "no parent stitch to attach a loop to (magic ring root)",
      exact: true,
    };
  }

  const postPoints: Vec3[] = [attachBase];
  for (let w = 1; w <= opts.wrapCount; w++) {
    const t = w / (opts.wrapCount + 1);
    const along = lerp(attachBase, P, t);
    postPoints.push(along);
    segments.push({
      role: "yarn_over",
      controlPoints: loopPoints(along, T, N, context.yarnRadiusCm * 1.8, 8),
      radius: context.yarnRadiusCm,
      curveType: "catmull_rom",
      closed: true,
    });
  }
  postPoints.push(P);

  segments.push({
    role: "post",
    controlPoints: postPoints,
    radius: context.yarnRadiusCm,
    curveType: "catmull_rom",
    closed: false,
  });

  segments.push({
    role: "top_loop",
    controlPoints: loopPoints(P, T, N, context.yarnRadiusCm * 2, 10),
    radius: context.yarnRadiusCm,
    curveType: "catmull_rom",
    closed: true,
  });

  const exitPoint: Vec3 = add(P, scale(T, halfWidth));
  segments.push({
    role: "connector",
    controlPoints: [P, exitPoint],
    radius: context.yarnRadiusCm,
    curveType: "line",
    closed: false,
  });

  return {
    stitchId: stitch.stitch_id,
    stitchType: stitch.stitch_type,
    strategyName: opts.strategyName,
    segments,
    entryPoint: parent ? parent.position : attachBase,
    exitPoint,
    loopAttachment,
    warnings,
  };
}
