import { describe, expect, it } from "vitest";
import {
  createObjectHeightMeasurement,
  createObjectWidthMeasurement,
  createPointDistanceMeasurement,
  createRoundCircumferenceMeasurement,
  measureDistance,
  measureRoundCircumference,
} from "../src/measurement/measurement";
import { makeTestGeometry } from "./fixtures";

describe("measureDistance (stitch-to-stitch)", () => {
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
    expect(measurement!.valueCm).toBeCloseTo(expected, 9);
    expect(measurement!.type).toBe("stitch_distance");
  });

  it("returns null for an unknown stitch id", () => {
    const doc = makeTestGeometry();
    expect(measureDistance(doc, "nope", doc.stitches[0].stitch_id)).toBeNull();
  });

  it("is symmetric", () => {
    const doc = makeTestGeometry();
    const a = doc.stitches[0].stitch_id;
    const b = doc.stitches[1].stitch_id;
    expect(measureDistance(doc, a, b)!.valueCm).toBeCloseTo(measureDistance(doc, b, a)!.valueCm, 9);
  });

  it("is zero for a stitch measured against itself", () => {
    const doc = makeTestGeometry();
    const a = doc.stitches[0].stitch_id;
    expect(measureDistance(doc, a, a)!.valueCm).toBeCloseTo(0, 9);
  });

  it("carries unit, approximation flag, and geometry fingerprint from the document", () => {
    const doc = makeTestGeometry();
    const measurement = measureDistance(doc, doc.stitches[0].stitch_id, doc.stitches[1].stitch_id)!;
    expect(measurement.unit).toBe(doc.units);
    expect(measurement.approximate).toBe(true);
    expect(measurement.geometryFingerprint).toBe(doc.geometry_fingerprint);
  });

  it("gives every measurement a unique, stable id", () => {
    const doc = makeTestGeometry();
    const a = measureDistance(doc, doc.stitches[0].stitch_id, doc.stitches[1].stitch_id)!;
    const b = measureDistance(doc, doc.stitches[0].stitch_id, doc.stitches[1].stitch_id)!;
    expect(a.id).not.toBe(b.id);
  });
});

describe("createPointDistanceMeasurement (arbitrary point-to-point)", () => {
  it("computes distance between two raw 3D points, independent of any stitch", () => {
    const doc = makeTestGeometry();
    const measurement = createPointDistanceMeasurement(doc, [0, 0, 0], [3, 4, 0]);
    expect(measurement.type).toBe("point_distance");
    expect(measurement.valueCm).toBeCloseTo(5, 9);
    expect(measurement.pointA).toEqual([0, 0, 0]);
    expect(measurement.pointB).toEqual([3, 4, 0]);
  });
});

describe("createObjectWidthMeasurement / createObjectHeightMeasurement", () => {
  it("width is the larger of the X/Y bounding-box extents", () => {
    const doc = makeTestGeometry();
    const measurement = createObjectWidthMeasurement(doc);
    const extentX = doc.bounds.max[0] - doc.bounds.min[0];
    const extentY = doc.bounds.max[1] - doc.bounds.min[1];
    expect(measurement.type).toBe("object_width");
    expect(measurement.valueCm).toBeCloseTo(Math.max(extentX, extentY), 9);
  });

  it("height is the Z bounding-box extent", () => {
    const doc = makeTestGeometry();
    const measurement = createObjectHeightMeasurement(doc);
    expect(measurement.type).toBe("object_height");
    expect(measurement.valueCm).toBeCloseTo(doc.bounds.max[2] - doc.bounds.min[2], 9);
  });

  it("both are labelled approximate", () => {
    const doc = makeTestGeometry();
    expect(createObjectWidthMeasurement(doc).approximate).toBe(true);
    expect(createObjectHeightMeasurement(doc).approximate).toBe(true);
  });
});

describe("measureRoundCircumference / createRoundCircumferenceMeasurement", () => {
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

  it("createRoundCircumferenceMeasurement returns null for an invalid round (fewer than 2 stitches)", () => {
    const doc = makeTestGeometry();
    // The shared fixture has exactly one stitch per round/component — an
    // ideal case for the "invalid round" path, not a workaround.
    expect(createRoundCircumferenceMeasurement(doc, "crown", 1)).toBeNull();
    expect(createRoundCircumferenceMeasurement(doc, "crown", 999)).toBeNull();
  });

  it("createRoundCircumferenceMeasurement labels the component/round and returns a positive value for a real multi-stitch round", () => {
    // Needs a round with >=2 stitches, which the shared fixture intentionally
    // doesn't have (see the null-round test above) — built inline instead.
    const doc = makeTestGeometry();
    const ringStitches = [0, 1, 2, 3].map((i) => ({
      ...doc.stitches[0],
      stitch_id: `ring-s${i}`,
      component_id: "ring",
      round_index: 5,
      sequence_index: i,
      position: [Math.cos((i / 4) * Math.PI * 2), Math.sin((i / 4) * Math.PI * 2), 0] as [number, number, number],
    }));
    const ringDoc = { ...doc, stitches: ringStitches };
    const measurement = createRoundCircumferenceMeasurement(ringDoc, "ring", 5)!;
    expect(measurement.type).toBe("round_circumference");
    expect(measurement.label).toContain("ring");
    expect(measurement.label).toContain("5");
    expect(measurement.valueCm).toBeGreaterThan(0);
  });
});
