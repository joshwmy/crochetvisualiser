import { describe, expect, it } from "vitest";
import { GeometryLoadError, validateGeometry } from "../src/geometry/load";
import { makeTestGeometry } from "./fixtures";

describe("validateGeometry", () => {
  it("accepts a well-formed document", () => {
    expect(() => validateGeometry(makeTestGeometry())).not.toThrow();
  });

  it("rejects an unsupported schema version", () => {
    const doc = makeTestGeometry();
    doc.schema_version = "9.9.9";
    expect(() => validateGeometry(doc)).toThrow(GeometryLoadError);
  });

  it("rejects an empty stitch list", () => {
    const doc = makeTestGeometry();
    doc.stitches = [];
    expect(() => validateGeometry(doc)).toThrow(/no stitches/);
  });

  it("rejects duplicate stitch_id values", () => {
    const doc = makeTestGeometry();
    doc.stitches[1].stitch_id = doc.stitches[0].stitch_id;
    expect(() => validateGeometry(doc)).toThrow(/duplicate/);
  });

  it("rejects a non-finite coordinate", () => {
    const doc = makeTestGeometry();
    doc.stitches[0].position = [Number.NaN, 0, 0];
    expect(() => validateGeometry(doc)).toThrow(/non-finite/);
  });

  it("rejects a missing graph_fingerprint", () => {
    const doc = makeTestGeometry();
    doc.graph_fingerprint = null;
    expect(() => validateGeometry(doc)).toThrow(/fingerprint/);
  });

  it("rejects a missing geometry_fingerprint", () => {
    const doc = makeTestGeometry();
    doc.geometry_fingerprint = null;
    expect(() => validateGeometry(doc)).toThrow(/fingerprint/);
  });

  it("tolerates a missing pattern_fingerprint (written patterns have none)", () => {
    const doc = makeTestGeometry();
    doc.pattern_fingerprint = null;
    expect(() => validateGeometry(doc)).not.toThrow();
  });
});
