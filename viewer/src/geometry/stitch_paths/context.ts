import type { GeometryDocument } from "../../types/geometry";
import type { StitchPathContext } from "./types";

export function buildPathContext(doc: GeometryDocument): StitchPathContext {
  const byId = new Map(doc.stitches.map((s) => [s.stitch_id, s]));
  return {
    getStitch: (id) => byId.get(id),
    yarnRadiusCm: doc.gauge.yarn_diameter_cm / 2,
    rowHeightCm: 1 / doc.gauge.rounds_per_cm,
  };
}
