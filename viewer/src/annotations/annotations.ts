import * as THREE from "three";
import type { GeometryDocument, Vec3 } from "../types/geometry";
import type { Annotation, AnnotationAnchor } from "./types";

/** Longest accepted annotation text. A note is a label, not a document; the
 * cap bounds both the DOM list and the in-memory store, and gives the UI a
 * definite number to show a remaining-character count against. */
export const MAX_ANNOTATION_LENGTH = 280;

let counter = 0;
function makeId(): string {
  counter += 1;
  return `annotation-${Date.now()}-${counter}`;
}

/**
 * Normalise user-entered annotation text.
 *
 * Collapses runs of whitespace (including newlines pasted from elsewhere)
 * into single spaces, trims, and truncates to `MAX_ANNOTATION_LENGTH`.
 * Returns `null` for text that is empty or whitespace-only, so "add an
 * annotation with no content" is rejected at the boundary rather than
 * creating an unlabelled marker floating in the scene.
 *
 * This is normalisation, **not** sanitisation for safe display — the text is
 * kept verbatim otherwise, including any `<`, `>`, or quote characters. Safe
 * rendering is the display layer's job and is achieved by assigning to
 * `textContent`, never `innerHTML`; see docs/annotations.md.
 */
export function normaliseAnnotationText(raw: string): string | null {
  const collapsed = raw.replace(/\s+/g, " ").trim();
  if (collapsed.length === 0) return null;
  return collapsed.slice(0, MAX_ANNOTATION_LENGTH);
}

function create(
  doc: GeometryDocument,
  anchor: AnnotationAnchor,
  text: string,
): Annotation | null {
  const normalised = normaliseAnnotationText(text);
  if (normalised === null) return null;
  const now = Date.now();
  return {
    id: makeId(),
    text: normalised,
    anchor,
    createdAtMs: now,
    updatedAtMs: now,
    geometryFingerprint: doc.geometry_fingerprint,
  };
}

/** Annotation anchored to a stitch by id. Returns `null` if the stitch is not
 * in `doc` (a stale id from a previous model) or the text is empty. */
export function createStitchAnnotation(
  doc: GeometryDocument,
  stitchId: string,
  text: string,
): Annotation | null {
  if (!doc.stitches.some((s) => s.stitch_id === stitchId)) return null;
  return create(doc, { kind: "stitch", stitchId }, text);
}

/** Annotation anchored to a raw world position, for notes about a region with
 * no single owning stitch. Returns `null` if the text is empty. */
export function createPointAnnotation(
  doc: GeometryDocument,
  point: Vec3,
  text: string,
): Annotation | null {
  return create(doc, { kind: "point", point }, text);
}

/**
 * A copy of `annotation` with new text and a refreshed `updatedAtMs`.
 *
 * Returns a new object rather than mutating in place, and returns `null` for
 * empty text so an edit can never blank out an existing annotation into an
 * unlabelled marker — the caller should remove it instead, which is an
 * explicit action.
 */
export function updateAnnotationText(annotation: Annotation, text: string): Annotation | null {
  const normalised = normaliseAnnotationText(text);
  if (normalised === null) return null;
  return { ...annotation, text: normalised, updatedAtMs: Date.now() };
}

/** World position an annotation's marker belongs at, or `null` if a stitch
 * anchor no longer resolves against `doc`. */
export function resolveAnchorPosition(doc: GeometryDocument, annotation: Annotation): Vec3 | null {
  // Bound to a local so the discriminated-union narrowing survives into the
  // `find` callback, where TypeScript would otherwise widen it again.
  const anchor = annotation.anchor;
  if (anchor.kind === "point") return anchor.point;
  const stitch = doc.stitches.find((s) => s.stitch_id === anchor.stitchId);
  return stitch ? stitch.position : null;
}

/** Short, ready-to-display description of what an anchor points at. Takes the
 * anchor rather than the whole annotation so the pending-anchor UI (which has
 * no annotation yet) can use the same wording as the saved list. */
export function describeAnchor(anchor: AnnotationAnchor): string {
  return anchor.kind === "stitch"
    ? `stitch ${anchor.stitchId}`
    : `point (${anchor.point.map((c) => c.toFixed(1)).join(", ")})`;
}

/**
 * The scene marker for one annotation: a small wireframe octahedron at the
 * anchor position.
 *
 * **The text itself is deliberately not drawn in 3D.** Rendering it would mean
 * generating a canvas texture per annotation and disposing it alongside the
 * mesh, and the label would then compete with the model for legibility at
 * every camera distance. The annotation list in the side panel carries the
 * text instead — the same split `docs/measurement-tools.md` already applies to
 * scalar measurements, which render as list entries rather than scene overlays.
 *
 * The octahedron shape (not just a colour) distinguishes an annotation marker
 * from the selection marker and the dashed measurement lines, following the
 * project's existing "never rely on colour alone" overlay convention.
 */
export function buildAnnotationMarker(
  doc: GeometryDocument,
  annotation: Annotation,
  radiusCm: number,
): THREE.LineSegments | null {
  const position = resolveAnchorPosition(doc, annotation);
  if (!position) return null;

  // WireframeGeometry copies what it needs from the source, so the solid
  // octahedron is disposed immediately — leaving it to the garbage collector
  // would leak a GPU buffer per annotation, which the repeated-recompile
  // stress test exists to catch.
  const source = new THREE.OctahedronGeometry(radiusCm);
  const geometry = new THREE.WireframeGeometry(source);
  source.dispose();
  const material = new THREE.LineBasicMaterial({ color: 0xf0b429 });
  const marker = new THREE.LineSegments(geometry, material);
  marker.position.set(...position);
  marker.name = `annotation-${annotation.id}`;
  return marker;
}
