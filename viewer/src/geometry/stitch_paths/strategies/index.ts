import type { StitchGeometry } from "../../../types/geometry";
import type { StitchPathContext, StitchPathResult, StitchPathStrategy } from "../types";
import { SingleCrochetStrategy } from "./sc";
import { HalfDoubleCrochetStrategy } from "./hdc";
import { DoubleCrochetStrategy } from "./dc";
import { ChainStitchStrategy } from "./chain";
import { SlipStitchStrategy } from "./slip_stitch";
import { augmentForDecrease, augmentForIncrease } from "./increase_decrease";

const STRATEGIES: StitchPathStrategy[] = [
  new SingleCrochetStrategy(),
  new HalfDoubleCrochetStrategy(),
  new DoubleCrochetStrategy(),
  new ChainStitchStrategy(),
  new SlipStitchStrategy(),
];

const REGISTRY = new Map(STRATEGIES.map((s) => [s.stitchType, s]));

/** Falls back to the single-crochet strategy for any unrecognised
 * `stitch_type`, with a warning attached — never a silent, unlabelled
 * guess (per the brief's "no unsupported silent fallbacks" requirement). */
export function generateStitchPaths(
  stitch: StitchGeometry,
  context: StitchPathContext,
): StitchPathResult {
  const strategy = REGISTRY.get(stitch.stitch_type);
  let result: StitchPathResult;
  if (strategy) {
    result = strategy.generatePaths(stitch, context);
  } else {
    result = new SingleCrochetStrategy().generatePaths(stitch, context);
    result = {
      ...result,
      strategyName: "single_crochet_fallback",
      warnings: [
        ...result.warnings,
        `Unrecognised stitch_type "${stitch.stitch_type}" — falling back to single-crochet geometry.`,
      ],
    };
  }

  if (stitch.is_increase) result = augmentForIncrease(result, stitch, context);
  if (stitch.is_decrease) result = augmentForDecrease(result, stitch, context);
  return result;
}

export function supportedStitchTypes(): string[] {
  return [...REGISTRY.keys()];
}
