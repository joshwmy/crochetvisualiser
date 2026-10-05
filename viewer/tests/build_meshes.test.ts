import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { buildStructuralScene, commitMatrixUpdates, setInstanceHidden } from "../src/geometry/build_meshes";
import { makeTestGeometry } from "./fixtures";

describe("buildStructuralScene", () => {
  it("creates one instanced mesh group per component and maps every stitch", () => {
    const doc = makeTestGeometry();
    const { groups, stitchIdToLocation } = buildStructuralScene(doc);

    const componentIds = groups.map((g) => g.componentId).sort();
    expect(componentIds).toEqual(["body", "crown"]);

    for (const stitch of doc.stitches) {
      expect(stitchIdToLocation.has(stitch.stitch_id)).toBe(true);
    }
    // Every rendered instance must map back to exactly one semantic stitch ID.
    const totalInstances = groups.reduce((sum, g) => sum + g.stitchIds.length, 0);
    expect(totalInstances).toBe(doc.stitches.length);
  });

  it("every group instance count matches its mesh.count", () => {
    const doc = makeTestGeometry();
    const { groups } = buildStructuralScene(doc);
    for (const group of groups) {
      expect(group.mesh.count).toBe(group.stitchIds.length);
      expect(group.matrices.length).toBe(group.stitchIds.length);
      expect(group.baseColors.length).toBe(group.stitchIds.length);
    }
  });

  it("setInstanceHidden zeroes scale and restores the original transform", () => {
    const doc = makeTestGeometry();
    const { groups } = buildStructuralScene(doc);
    const group = groups[0];
    const original = group.matrices[0].clone();

    setInstanceHidden(group, 0, true);
    commitMatrixUpdates(group);
    const hiddenMatrix = new THREE.Matrix4();
    group.mesh.getMatrixAt(0, hiddenMatrix);
    const scale = new THREE.Vector3();
    hiddenMatrix.decompose(new THREE.Vector3(), new THREE.Quaternion(), scale);
    expect(scale.length()).toBeCloseTo(0, 9);

    setInstanceHidden(group, 0, false);
    commitMatrixUpdates(group);
    const restoredMatrix = new THREE.Matrix4();
    group.mesh.getMatrixAt(0, restoredMatrix);
    expect(restoredMatrix.equals(original)).toBe(true);
  });
});
