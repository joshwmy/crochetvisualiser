import type { StitchGeometry } from "../../../types/geometry";
import type { StitchPathContext, StitchPathResult, StitchPathStrategy } from "../types";
import { buildPlainStitchPaths } from "./plain_stitch";

export class HalfDoubleCrochetStrategy implements StitchPathStrategy {
  readonly stitchType = "hdc";

  generatePaths(stitch: StitchGeometry, context: StitchPathContext): StitchPathResult {
    return buildPlainStitchPaths(stitch, context, {
      strategyName: "half_double_crochet",
      heightFactor: 0.85,
      wrapCount: 1,
    });
  }
}
