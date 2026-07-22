import type { StitchGeometry } from "../../../types/geometry";
import type { StitchPathContext, StitchPathResult, StitchPathStrategy } from "../types";
import { buildPlainStitchPaths } from "./plain_stitch";

export class DoubleCrochetStrategy implements StitchPathStrategy {
  readonly stitchType = "dc";

  generatePaths(stitch: StitchGeometry, context: StitchPathContext): StitchPathResult {
    return buildPlainStitchPaths(stitch, context, {
      strategyName: "double_crochet",
      heightFactor: 1.2,
      wrapCount: 2,
    });
  }
}
