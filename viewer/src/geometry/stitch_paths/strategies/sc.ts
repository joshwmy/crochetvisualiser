import type { StitchGeometry } from "../../../types/geometry";
import type { StitchPathContext, StitchPathResult, StitchPathStrategy } from "../types";
import { buildPlainStitchPaths } from "./plain_stitch";

export class SingleCrochetStrategy implements StitchPathStrategy {
  readonly stitchType = "sc";

  generatePaths(stitch: StitchGeometry, context: StitchPathContext): StitchPathResult {
    return buildPlainStitchPaths(stitch, context, {
      strategyName: "single_crochet",
      heightFactor: 0.6,
      wrapCount: 0,
    });
  }
}
