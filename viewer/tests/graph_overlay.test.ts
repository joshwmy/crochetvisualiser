import { describe, expect, it } from "vitest";
import { buildGraphOverlay } from "../src/selection/graph_overlay";
import { makeTestGeometry } from "./fixtures";

describe("buildGraphOverlay", () => {
  it("only draws edges touching the selected stitch (bounded neighbourhood, not the whole graph)", () => {
    const doc = makeTestGeometry();
    const selected = "crown-r02-s000"; // has one insertion edge in the fixture
    const overlay = buildGraphOverlay(doc, selected);
    const positionCount = overlay.geometry.getAttribute("position").count;
    const relevantEdges = doc.edges.filter(
      (e) => e.source_id === selected || e.target_id === selected,
    );
    expect(positionCount).toBe(relevantEdges.length * 2);
  });

  it("produces no geometry for a stitch with no edges", () => {
    const doc = makeTestGeometry();
    const overlay = buildGraphOverlay(doc, "crown-r01-s000-does-not-exist");
    expect(overlay.geometry.getAttribute("position").count).toBe(0);
  });

  it("has finite vertex positions", () => {
    const doc = makeTestGeometry();
    const overlay = buildGraphOverlay(doc, "crown-r02-s000");
    const positions = overlay.geometry.getAttribute("position").array;
    for (const value of positions) expect(Number.isFinite(value)).toBe(true);
  });
});
