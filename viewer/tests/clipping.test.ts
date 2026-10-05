import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { applyClippingToMaterials, buildClippingPlane } from "../src/clipping/clipping";
import type { GeometryBounds } from "../src/types/geometry";
import type { ClippingState } from "../src/state/store";

const bounds: GeometryBounds = { min: [-10, -5, -20], max: [10, 5, 0] };

describe("buildClippingPlane", () => {
  it("centers the plane at offset 0", () => {
    const clipping: ClippingState = { enabled: true, axis: "z", offset: 0, invert: false };
    const plane = buildClippingPlane(bounds, clipping);
    // z center is -10; point (0,0,-10) must lie exactly on the plane.
    const point = new THREE.Vector3(0, 0, -10);
    expect(plane.distanceToPoint(point)).toBeCloseTo(0, 6);
  });

  it("moves toward max bound as offset approaches 1", () => {
    const clipping: ClippingState = { enabled: true, axis: "x", offset: 1, invert: false };
    const plane = buildClippingPlane(bounds, clipping);
    const point = new THREE.Vector3(10, 0, 0);
    expect(plane.distanceToPoint(point)).toBeCloseTo(0, 6);
  });

  it("works on the Y axis (not just X/Z)", () => {
    const clipping: ClippingState = { enabled: true, axis: "y", offset: -1, invert: false };
    const plane = buildClippingPlane(bounds, clipping);
    // y center is 0, min bound is -5 — offset -1 must land exactly on min.
    const point = new THREE.Vector3(0, -5, 0);
    expect(plane.distanceToPoint(point)).toBeCloseTo(0, 6);
  });

  it("invert flips which half-space is kept", () => {
    const clipping: ClippingState = { enabled: true, axis: "x", offset: 0, invert: false };
    const clippingInverted: ClippingState = { ...clipping, invert: true };
    const plane = buildClippingPlane(bounds, clipping);
    const inverted = buildClippingPlane(bounds, clippingInverted);
    const point = new THREE.Vector3(5, 0, 0);
    expect(Math.sign(plane.distanceToPoint(point))).toBe(-Math.sign(inverted.distanceToPoint(point)));
  });
});

describe("applyClippingToMaterials", () => {
  it("assigns the plane to every material and clears it when null", () => {
    const materials = [new THREE.MeshBasicMaterial(), new THREE.MeshBasicMaterial()];
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    applyClippingToMaterials(materials, plane);
    for (const m of materials) expect(m.clippingPlanes).toEqual([plane]);

    applyClippingToMaterials(materials, null);
    for (const m of materials) expect(m.clippingPlanes).toEqual([]);
  });

  it("flags a shader update only when the plane count changes, not when the plane moves", () => {
    const material = new THREE.MeshBasicMaterial();
    const start = material.version;
    applyClippingToMaterials([material], new THREE.Plane(new THREE.Vector3(0, 0, 1), 0));
    expect(material.version).toBe(start + 1);

    applyClippingToMaterials([material], new THREE.Plane(new THREE.Vector3(0, 0, 1), 2));
    applyClippingToMaterials([material], new THREE.Plane(new THREE.Vector3(1, 0, 0), -1));
    expect(material.version).toBe(start + 1);

    applyClippingToMaterials([material], null);
    expect(material.version).toBe(start + 2);
    applyClippingToMaterials([material], null);
    expect(material.version).toBe(start + 2);
  });
});
