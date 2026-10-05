import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  applyYarnPalette,
  buildYarnPathScene,
  defaultQualityFor,
  QUALITY_PRESETS,
  stitchIdForFace,
  VERTEX_KIND,
} from "../src/geometry/build_yarn_paths";
import { SEMANTIC_YARN_COLORS } from "../src/materials/yarn_material";
import { makeTestGeometry } from "./fixtures";

describe("buildYarnPathScene", () => {
  it("produces one component mesh with contiguous, sorted face ranges covering every stitch", () => {
    const doc = makeTestGeometry();
    const scene = buildYarnPathScene(doc, QUALITY_PRESETS.medium);
    expect(scene.components.length).toBeGreaterThan(0);
    for (const comp of scene.components) {
      const stitchesInComponent = doc.stitches.filter((s) => s.component_id === comp.componentId);
      expect(comp.faceRanges).toHaveLength(stitchesInComponent.length);
      for (let i = 1; i < comp.faceRanges.length; i++) {
        expect(comp.faceRanges[i].startFace).toBe(comp.faceRanges[i - 1].endFace);
      }
    }
  });

  it("maps every face index back to exactly the owning stitch via stitchIdForFace", () => {
    const doc = makeTestGeometry();
    const scene = buildYarnPathScene(doc, QUALITY_PRESETS.medium);
    for (const comp of scene.components) {
      for (const range of comp.faceRanges) {
        expect(stitchIdForFace(comp.faceRanges, range.startFace)).toBe(range.stitchId);
        expect(stitchIdForFace(comp.faceRanges, range.endFace - 1)).toBe(range.stitchId);
      }
    }
  });

  it("returns null for an out-of-range face index", () => {
    const doc = makeTestGeometry();
    const scene = buildYarnPathScene(doc, QUALITY_PRESETS.medium);
    const comp = scene.components[0];
    expect(stitchIdForFace(comp.faceRanges, -1)).toBeNull();
    expect(stitchIdForFace(comp.faceRanges, 999_999_999)).toBeNull();
  });

  it("has no NaN or infinite vertex coordinates in the merged geometry", () => {
    const doc = makeTestGeometry();
    const scene = buildYarnPathScene(doc, QUALITY_PRESETS.low);
    for (const comp of scene.components) {
      const positions = comp.mesh.geometry.getAttribute("position").array;
      for (const value of positions) {
        expect(Number.isFinite(value)).toBe(true);
      }
    }
  });

  it("higher quality presets produce more triangles", () => {
    const doc = makeTestGeometry();
    const low = buildYarnPathScene(doc, QUALITY_PRESETS.low);
    const high = buildYarnPathScene(doc, QUALITY_PRESETS.high);
    expect(high.stats.triangleCount).toBeGreaterThan(low.stats.triangleCount);
  });

  it("records per-stitch warnings only for stitches that actually warned", () => {
    const doc = makeTestGeometry();
    doc.stitches[0].loop_placement = "front_loop_only";
    doc.stitches[0].parent_stitch_ids = [doc.stitches[1].stitch_id];
    const scene = buildYarnPathScene(doc, QUALITY_PRESETS.medium);
    expect(scene.warningsByStitch.has(doc.stitches[0].stitch_id)).toBe(true);
  });
});

describe("defaultQualityFor", () => {
  it("picks low for very large models, never automatically high", () => {
    expect(defaultQualityFor(10_000)).toBe("low");
  });

  it("picks high only for small models", () => {
    expect(defaultQualityFor(50)).toBe("high");
  });

  it("picks medium for mid-sized models", () => {
    expect(defaultQualityFor(1000)).toBe("medium");
  });
});

describe("applyYarnPalette", () => {
  const doc = makeTestGeometry();
  const component = buildYarnPathScene(doc, QUALITY_PRESETS.low).components[0];
  const colours = component.mesh.geometry.getAttribute("color");
  const firstVertexOfKind = (kind: number): number => component.vertexKinds.indexOf(kind);

  // Colours are stored as float32, so compare per channel with a tolerance.
  const expectColour = (vertex: number, hex: number): void => {
    const expected = new THREE.Color(hex);
    expect(colours.getX(vertex)).toBeCloseTo(expected.r, 5);
    expect(colours.getY(vertex)).toBeCloseTo(expected.g, 5);
    expect(colours.getZ(vertex)).toBeCloseTo(expected.b, 5);
  };

  it("records one stitch kind per vertex", () => {
    expect(component.vertexKinds.length).toBe(component.mesh.geometry.getAttribute("position").count);
    expect(firstVertexOfKind(VERTEX_KIND.increase)).toBeGreaterThanOrEqual(0);
  });

  it("paints every stitch the main colour when shaping highlights are off", () => {
    applyYarnPalette(component, { main: 0x9fb38f, highlightShaping: false });
    expectColour(firstVertexOfKind(VERTEX_KIND.main), 0x9fb38f);
    expectColour(firstVertexOfKind(VERTEX_KIND.increase), 0x9fb38f);
  });

  it("paints increases in their semantic colour when shaping highlights are on", () => {
    applyYarnPalette(component, { main: 0x9fb38f, highlightShaping: true });
    expectColour(firstVertexOfKind(VERTEX_KIND.main), 0x9fb38f);
    expectColour(firstVertexOfKind(VERTEX_KIND.increase), SEMANTIC_YARN_COLORS.increase);
  });
});
