import type { StitchGeometry } from "../../../types/geometry";
import { add, frameOf, loopPoints, scale } from "../common";
import type { StitchPathContext, StitchPathResult, StitchPathStrategy, Vec3 } from "../types";

/**
 * Slip stitch — same "recognised but not yet parser-producible" status as
 * chain (see chain.ts's docstring). Represented as a compact attachment
 * loop with minimal vertical rise (a small fraction of a normal stitch's
 * post height) and immediate yarn continuity, per the brief.
 */
export class SlipStitchStrategy implements StitchPathStrategy {
  readonly stitchType = "slip_stitch";

  generatePaths(stitch: StitchGeometry, context: StitchPathContext): StitchPathResult {
    const { T, N, B, P } = frameOf(stitch);
    const height = context.rowHeightCm * 0.15;
    const attachBase: Vec3 = add(P, scale(B, -height));
    const parentId = stitch.parent_stitch_ids[0];
    const parent = parentId ? context.getStitch(parentId) : undefined;

    const segments = [
      ...(parent
        ? [
            {
              role: "connector" as const,
              controlPoints: [parent.position, attachBase],
              radius: context.yarnRadiusCm,
              curveType: "line" as const,
              closed: false,
            },
          ]
        : []),
      {
        role: "foundation_loop" as const,
        controlPoints: loopPoints(P, T, N, context.yarnRadiusCm * 1.4, 8),
        radius: context.yarnRadiusCm,
        curveType: "catmull_rom" as const,
        closed: true,
      },
    ];

    const exitPoint: Vec3 = add(P, scale(T, context.yarnRadiusCm * 2));

    return {
      stitchId: stitch.stitch_id,
      stitchType: stitch.stitch_type,
      strategyName: "slip_stitch",
      segments,
      entryPoint: parent ? parent.position : attachBase,
      exitPoint,
      warnings: [],
    };
  }
}
