import type { StitchGeometry } from "../../../types/geometry";
import { add, frameOf, loopPoints, scale } from "../common";
import type { StitchPathContext, StitchPathResult, StitchPathStrategy, Vec3 } from "../types";

/**
 * Chain stitch — not produced by the written-pattern parser yet (see
 * docs/known-limitations.md), but implemented and tested behind this
 * strategy interface per the brief's explicit allowance, using synthetic
 * fixtures (tests/stitch_paths/chain.test.ts).
 *
 * Represented as a sequence of interlocking loops: each chain's loop plane
 * alternates between the (T,N) and (T,B) planes (keyed off `sequence_index`
 * parity, for determinism) so consecutive loops visually pass through one
 * another rather than sitting as disconnected rings.
 */
export class ChainStitchStrategy implements StitchPathStrategy {
  readonly stitchType = "chain";

  generatePaths(stitch: StitchGeometry, context: StitchPathContext): StitchPathResult {
    const { T, N, B, P } = frameOf(stitch);
    const alternate = stitch.sequence_index % 2 === 0;
    const planeV = alternate ? N : B;
    const radius = context.yarnRadiusCm * 1.6;

    const loop = loopPoints(P, T, planeV, radius, 10);
    const entryPoint: Vec3 = add(P, scale(T, -radius));
    const exitPoint: Vec3 = add(P, scale(T, radius));

    return {
      stitchId: stitch.stitch_id,
      stitchType: stitch.stitch_type,
      strategyName: "chain",
      segments: [
        { role: "foundation_loop", controlPoints: loop, radius: context.yarnRadiusCm, curveType: "catmull_rom", closed: true },
      ],
      entryPoint,
      exitPoint,
      warnings: [],
    };
  }
}
