import { describe, expect, it } from "vitest";
import {
  buildAnnotationMarker,
  createPointAnnotation,
  createStitchAnnotation,
  describeAnchor,
  MAX_ANNOTATION_LENGTH,
  normaliseAnnotationText,
  resolveAnchorPosition,
  updateAnnotationText,
} from "../src/annotations/annotations";
import { makeTestGeometry } from "./fixtures";

describe("normaliseAnnotationText", () => {
  it("trims surrounding whitespace", () => {
    expect(normaliseAnnotationText("  note  ")).toBe("note");
  });

  it("collapses internal whitespace runs, including pasted newlines", () => {
    expect(normaliseAnnotationText("first\n\n  second\tthird")).toBe("first second third");
  });

  it("returns null for empty or whitespace-only text", () => {
    expect(normaliseAnnotationText("")).toBeNull();
    expect(normaliseAnnotationText("   \n\t ")).toBeNull();
  });

  it("truncates to the documented maximum length", () => {
    const long = "x".repeat(MAX_ANNOTATION_LENGTH + 50);
    expect(normaliseAnnotationText(long)!.length).toBe(MAX_ANNOTATION_LENGTH);
  });

  it("leaves markup characters verbatim — escaping is the display layer's job", () => {
    // The UI renders via textContent, so the text is never parsed as markup.
    // Mangling it here would corrupt legitimate notes like "row < 10".
    expect(normaliseAnnotationText("<script>alert(1)</script>")).toBe("<script>alert(1)</script>");
    expect(normaliseAnnotationText('gauge "tight" & short')).toBe('gauge "tight" & short');
  });
});

describe("createStitchAnnotation", () => {
  it("anchors to the stitch id and carries document provenance", () => {
    const doc = makeTestGeometry();
    const stitchId = doc.stitches[0].stitch_id;
    const annotation = createStitchAnnotation(doc, stitchId, "puckers here")!;

    expect(annotation.anchor).toEqual({ kind: "stitch", stitchId });
    expect(annotation.text).toBe("puckers here");
    expect(annotation.geometryFingerprint).toBe(doc.geometry_fingerprint);
    expect(annotation.updatedAtMs).toBe(annotation.createdAtMs);
  });

  it("returns null for a stitch id not in the document", () => {
    const doc = makeTestGeometry();
    expect(createStitchAnnotation(doc, "no-such-stitch", "note")).toBeNull();
  });

  it("returns null for empty text rather than creating an unlabelled marker", () => {
    const doc = makeTestGeometry();
    expect(createStitchAnnotation(doc, doc.stitches[0].stitch_id, "   ")).toBeNull();
  });

  it("gives every annotation a unique id", () => {
    const doc = makeTestGeometry();
    const id = doc.stitches[0].stitch_id;
    const a = createStitchAnnotation(doc, id, "one")!;
    const b = createStitchAnnotation(doc, id, "two")!;
    expect(a.id).not.toBe(b.id);
  });
});

describe("createPointAnnotation", () => {
  it("stores the raw world position, with no stitch identity", () => {
    const doc = makeTestGeometry();
    const annotation = createPointAnnotation(doc, [1.5, -2, 0.25], "gap in this region")!;
    expect(annotation.anchor).toEqual({ kind: "point", point: [1.5, -2, 0.25] });
  });

  it("returns null for empty text", () => {
    const doc = makeTestGeometry();
    expect(createPointAnnotation(doc, [0, 0, 0], "")).toBeNull();
  });
});

describe("updateAnnotationText", () => {
  it("returns a new object and does not mutate the original", () => {
    const doc = makeTestGeometry();
    const original = createStitchAnnotation(doc, doc.stitches[0].stitch_id, "before")!;
    const updated = updateAnnotationText(original, "after")!;

    expect(updated).not.toBe(original);
    expect(original.text).toBe("before");
    expect(updated.text).toBe("after");
  });

  it("preserves id, anchor, and creation time", () => {
    const doc = makeTestGeometry();
    const original = createStitchAnnotation(doc, doc.stitches[0].stitch_id, "before")!;
    const updated = updateAnnotationText(original, "after")!;

    expect(updated.id).toBe(original.id);
    expect(updated.anchor).toEqual(original.anchor);
    expect(updated.createdAtMs).toBe(original.createdAtMs);
  });

  it("advances updatedAtMs to at least the creation time", () => {
    const doc = makeTestGeometry();
    const original = createStitchAnnotation(doc, doc.stitches[0].stitch_id, "before")!;
    const updated = updateAnnotationText(original, "after")!;
    expect(updated.updatedAtMs).toBeGreaterThanOrEqual(original.createdAtMs);
  });

  it("returns null for empty text so an edit can never blank an annotation out", () => {
    const doc = makeTestGeometry();
    const original = createStitchAnnotation(doc, doc.stitches[0].stitch_id, "before")!;
    expect(updateAnnotationText(original, "  ")).toBeNull();
  });
});

describe("resolveAnchorPosition", () => {
  it("follows the stitch's current position rather than a remembered coordinate", () => {
    const doc = makeTestGeometry();
    const stitchId = doc.stitches[0].stitch_id;
    const annotation = createStitchAnnotation(doc, stitchId, "note")!;

    const moved = {
      ...doc,
      stitches: doc.stitches.map((s) =>
        s.stitch_id === stitchId ? { ...s, position: [9, 9, 9] as [number, number, number] } : s,
      ),
    };
    expect(resolveAnchorPosition(moved, annotation)).toEqual([9, 9, 9]);
  });

  it("returns the stored point for a point anchor", () => {
    const doc = makeTestGeometry();
    const annotation = createPointAnnotation(doc, [4, 5, 6], "note")!;
    expect(resolveAnchorPosition(doc, annotation)).toEqual([4, 5, 6]);
  });

  it("returns null when a stitch anchor no longer resolves", () => {
    const doc = makeTestGeometry();
    const annotation = createStitchAnnotation(doc, doc.stitches[0].stitch_id, "note")!;
    const emptied = { ...doc, stitches: [] };
    expect(resolveAnchorPosition(emptied, annotation)).toBeNull();
  });
});

describe("describeAnchor", () => {
  it("names the stitch for a stitch anchor", () => {
    expect(describeAnchor({ kind: "stitch", stitchId: "crown-r01-s000" })).toContain("crown-r01-s000");
  });

  it("shows rounded coordinates for a point anchor", () => {
    expect(describeAnchor({ kind: "point", point: [1.234, 2.345, 3.456] })).toBe("point (1.2, 2.3, 3.5)");
  });
});

describe("buildAnnotationMarker", () => {
  it("places the marker at the resolved anchor position", () => {
    const doc = makeTestGeometry();
    const stitch = doc.stitches[1];
    const annotation = createStitchAnnotation(doc, stitch.stitch_id, "note")!;
    const marker = buildAnnotationMarker(doc, annotation, 0.3)!;

    expect(marker.position.toArray()).toEqual(stitch.position);
  });

  it("names the marker after the annotation so it can be disposed individually", () => {
    const doc = makeTestGeometry();
    const annotation = createStitchAnnotation(doc, doc.stitches[0].stitch_id, "note")!;
    const marker = buildAnnotationMarker(doc, annotation, 0.3)!;
    expect(marker.name).toBe(`annotation-${annotation.id}`);
  });

  it("returns null when the anchor cannot be resolved, rather than a marker at the origin", () => {
    const doc = makeTestGeometry();
    const annotation = createStitchAnnotation(doc, doc.stitches[0].stitch_id, "note")!;
    const emptied = { ...doc, stitches: [] };
    expect(buildAnnotationMarker(emptied, annotation, 0.3)).toBeNull();
  });

  it("scales with the radius it is given", () => {
    const doc = makeTestGeometry();
    const annotation = createPointAnnotation(doc, [0, 0, 0], "note")!;
    const small = buildAnnotationMarker(doc, annotation, 0.1)!;
    const large = buildAnnotationMarker(doc, annotation, 1.0)!;

    const extent = (marker: typeof small): number => {
      marker.geometry.computeBoundingBox();
      const box = marker.geometry.boundingBox!;
      return box.max.x - box.min.x;
    };
    expect(extent(large)).toBeGreaterThan(extent(small));
  });
});
