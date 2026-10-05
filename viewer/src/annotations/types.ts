import type { Vec3 } from "../types/geometry";

/**
 * What an annotation is attached to.
 *
 * A stitch anchor is the meaningful one for inspection — it survives as a
 * *semantic* reference (`stitch_id`), so the marker follows the stitch's real
 * position rather than a remembered screen or world coordinate. A point
 * anchor exists for notes about a region with no single owning stitch (a gap,
 * a seam line, an area of self-intersecting yarn) and stores a raw world
 * position instead, because there is no identity to store.
 *
 * Same discriminated-union shape as `Measurement` in ../measurement/types.ts,
 * for the same reason: the UI layer can render every variant through shared
 * fields and only branch where the variants genuinely differ.
 */
export type AnnotationAnchor =
  | { kind: "stitch"; stitchId: string }
  | { kind: "point"; point: Vec3 };

export interface Annotation {
  id: string;
  /** User-authored free text. Always rendered via `textContent`, never
   * `innerHTML` — see docs/annotations.md's "Untrusted text" section. */
  text: string;
  anchor: AnnotationAnchor;
  /** `Date.now()` at creation. */
  createdAtMs: number;
  /** `Date.now()` at the last text edit; equals `createdAtMs` until edited. */
  updatedAtMs: number;
  /** `doc.geometry_fingerprint` at creation time. `loadGeometryDocument`
   * clears all annotations on recompile (an annotation anchored to the
   * previous model's stitch ids would be meaningless against a new one), so
   * this records the association rather than being the mechanism that
   * enforces it — matching the equivalent field on `Measurement`. */
  geometryFingerprint: string | null;
}
