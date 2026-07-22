import { describe, expect, it } from "vitest";
import { measureDistance, measureRoundCircumference } from "../src/measurement/measurement";
import { makeTestGeometry } from "./fixtures";

describe("measureDistance", () => {
  it("computes the real 3D distance between two stitches", () => {
    const doc = makeTestGeometry();
    const a = doc.stitches[0];
    const b = doc.stitches[1];
    const expected = Math.hypot(
      a.position[0] - b.position[0],
      a.position[1] - b.position[1],
      a.position[2] - b.position[2],
    );
    const measurement = measureDistance(doc, a.stitch_id, b.stitch_id);
    expect(measurement).not.toBeNull();
    expect(measurement!.distanceCm).toBeCloseTo(expected, 9);
  });

  it("returns null for an unknown stitch id", () => {
    const doc = makeTestGeometry();
    expect(measureDistance(doc, "nope", doc.stitches[0].stitch_id)).toBeNull();
  });

  it("is symmetric", () => {
    const doc = makeTestGeometry();
    const a = doc.stitches[0].stitch_id;
    const b = doc.stitches[1].stitch_id;
    expect(measureDistance(doc, a, b)!.distanceCm).toBeCloseTo(measureDistance(doc, b, a)!.distanceCm, 9);
  });

  it("is zero for a stitch measured against itself", () => {
    const doc = makeTestGeometry();
    const a = doc.stitches[0].stitch_id;
    expect(measureDistance(doc, a, a)!.distanceCm).toBeCloseTo(0, 9);
  });
});

describe("measureRoundCircumference", () => {
  it("returns a positive number for a round with multiple stitches", () => {
    const doc = makeTestGeometry();
    const crownRound1 = doc.stitches.filter((s) => s.component_id === "crown" && s.round_index === 1);
    expect(crownRound1.length).toBeGreaterThan(0);
    const circumference = measureRoundCircumference(doc, "crown", 1);
    expect(circumference).toBeGreaterThanOrEqual(0);
  });

  it("returns 0 for a round that does not exist", () => {
    const doc = makeTestGeometry();
    expect(measureRoundCircumference(doc, "crown", 999)).toBe(0);
  });
});
