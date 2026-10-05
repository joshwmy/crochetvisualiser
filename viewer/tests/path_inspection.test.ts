import { describe, expect, it } from "vitest";
import { buildPathInspectionMeshes, PATH_ROLE_LEGEND } from "../src/selection/path_inspection";
import { generateStitchPaths } from "../src/geometry/stitch_paths/strategies";
import { makeStitch, makeContextWithStitches } from "./stitch_paths/factory";

describe("buildPathInspectionMeshes", () => {
  it("with no focus role, renders every segment of the selected stitch (highlight all)", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: "hdc", parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);

    const built = buildPathInspectionMeshes(result, null);
    expect(built.focusMesh).not.toBeNull();
    expect(built.rolesPresent.length).toBeGreaterThan(0);
    expect(built.rolesPresent).toEqual(expect.arrayContaining(result.segments.map((s) => s.role)));
  });

  it("focusing one role only renders that role's segments (fewer triangles than highlight-all)", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: "hdc", parent_stitch_ids: ["parent"] });
    const context = makeContextWithStitches([parent, stitch]);
    const result = generateStitchPaths(stitch, context);

    const all = buildPathInspectionMeshes(result, null);
    const focused = buildPathInspectionMeshes(result, "post");

    const allCount = all.focusMesh!.geometry.getAttribute("position").count;
    const focusedCount = focused.focusMesh!.geometry.getAttribute("position").count;
    expect(focusedCount).toBeLessThan(allCount);
  });

  it("focusing a role absent from the stitch yields no focus mesh", () => {
    const stitch = makeStitch({ stitch_type: "chain" });
    const context = makeContextWithStitches([stitch]);
    const result = generateStitchPaths(stitch, context);

    const built = buildPathInspectionMeshes(result, "decrease_bridge");
    expect(built.focusMesh).toBeNull();
  });

  it("without context stitches, no context mesh is built", () => {
    const stitch = makeStitch({ stitch_type: "sc" });
    const context = makeContextWithStitches([stitch]);
    const result = generateStitchPaths(stitch, context);

    const built = buildPathInspectionMeshes(result, null);
    expect(built.contextMesh).toBeNull();
  });

  it("with parent and next context, builds one merged (dimmed) context mesh", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: "sc", parent_stitch_ids: ["parent"] });
    const next = makeStitch({ stitch_type: "sc", parent_stitch_ids: [stitch.stitch_id] });
    const ctx = makeContextWithStitches([parent, stitch, next]);

    const parentResult = generateStitchPaths(parent, ctx);
    const stitchResult = generateStitchPaths(stitch, ctx);
    const nextResult = generateStitchPaths(next, ctx);

    const built = buildPathInspectionMeshes(stitchResult, null, { parent: parentResult, next: nextResult });
    expect(built.contextMesh).not.toBeNull();
    const material = built.contextMesh!.material as import("three").MeshBasicMaterial;
    expect(material.transparent).toBe(true);
    expect(material.opacity).toBeLessThan(1);
  });

  it("never includes context-stitch segments in the focus mesh (context stays visually separate)", () => {
    const parent = makeStitch({ stitch_id: "parent" });
    const stitch = makeStitch({ stitch_type: "sc", parent_stitch_ids: ["parent"] });
    const ctx = makeContextWithStitches([parent, stitch]);
    const parentResult = generateStitchPaths(parent, ctx);
    const stitchResult = generateStitchPaths(stitch, ctx);

    const withoutContext = buildPathInspectionMeshes(stitchResult, null);
    const withContext = buildPathInspectionMeshes(stitchResult, null, { parent: parentResult });
    // The focus mesh (the selected stitch's own geometry) must be identical
    // regardless of whether context is supplied — context only adds a
    // second, separate mesh, never mixes into the focus one.
    expect(withContext.focusMesh!.geometry.getAttribute("position").count).toBe(
      withoutContext.focusMesh!.geometry.getAttribute("position").count,
    );
  });
});

describe("PATH_ROLE_LEGEND", () => {
  it("has a text label and colour for every semantic role", () => {
    expect(PATH_ROLE_LEGEND.length).toBeGreaterThan(0);
    for (const entry of PATH_ROLE_LEGEND) {
      expect(entry.label.length).toBeGreaterThan(0);
      expect(entry.color).toMatch(/^#[0-9a-f]{6}$/);
    }
  });
});
