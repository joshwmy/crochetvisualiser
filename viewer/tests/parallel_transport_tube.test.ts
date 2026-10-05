import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  buildTubeGeometry,
  computeParallelTransportFrames,
  triangleCountForTube,
} from "../src/geometry/parallel_transport_tube";

function isFiniteVec(v: THREE.Vector3): boolean {
  return Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z);
}

describe("computeParallelTransportFrames", () => {
  it("produces orthonormal frames along a straight line", () => {
    const points = [0, 1, 2, 3, 4].map((i) => new THREE.Vector3(i, 0, 0));
    const frames = computeParallelTransportFrames(points, false);
    expect(frames).toHaveLength(points.length);
    for (const frame of frames) {
      expect(isFiniteVec(frame.tangent)).toBe(true);
      expect(frame.tangent.length()).toBeCloseTo(1, 6);
      expect(frame.normal.length()).toBeCloseTo(1, 6);
      expect(frame.binormal.length()).toBeCloseTo(1, 6);
      expect(frame.tangent.dot(frame.normal)).toBeCloseTo(0, 5);
      expect(frame.tangent.dot(frame.binormal)).toBeCloseTo(0, 5);
      expect(frame.normal.dot(frame.binormal)).toBeCloseTo(0, 5);
    }
  });

  it("does not flip the normal discontinuously on a straight segment (no twist)", () => {
    const points = [0, 1, 2, 3, 4].map((i) => new THREE.Vector3(i, 0, 0));
    const frames = computeParallelTransportFrames(points, false);
    for (let i = 1; i < frames.length; i++) {
      expect(frames[i].normal.dot(frames[i - 1].normal)).toBeCloseTo(1, 5);
    }
  });

  it("stays orthonormal around a curved (circular) path", () => {
    const points: THREE.Vector3[] = [];
    for (let i = 0; i < 16; i++) {
      const angle = (i / 16) * Math.PI * 2;
      points.push(new THREE.Vector3(Math.cos(angle), Math.sin(angle), 0));
    }
    const frames = computeParallelTransportFrames(points, true);
    for (const frame of frames) {
      expect(frame.tangent.dot(frame.normal)).toBeCloseTo(0, 4);
      expect(isFiniteVec(frame.normal)).toBe(true);
    }
  });

  it("is deterministic for identical input", () => {
    const points = [0, 1, 2].map((i) => new THREE.Vector3(i, i * 0.3, 0));
    const a = computeParallelTransportFrames(points, false);
    const b = computeParallelTransportFrames(points, false);
    for (let i = 0; i < a.length; i++) {
      expect(a[i].normal.toArray()).toEqual(b[i].normal.toArray());
    }
  });

  it("throws on fewer than 2 points rather than producing garbage", () => {
    expect(() => computeParallelTransportFrames([new THREE.Vector3()], false)).toThrow();
  });
});

describe("buildTubeGeometry", () => {
  it("produces finite, non-NaN vertex positions", () => {
    const points = [0, 1, 2].map((i) => new THREE.Vector3(i, 0, 0));
    const frames = computeParallelTransportFrames(points, false);
    const geometry = buildTubeGeometry(points, frames, 0.1, 6, false);
    const positions = geometry.getAttribute("position").array;
    for (const value of positions) {
      expect(Number.isFinite(value)).toBe(true);
      expect(Number.isNaN(value)).toBe(false);
    }
  });

  it("triangle count matches triangleCountForTube", () => {
    const points = [0, 1, 2, 3].map((i) => new THREE.Vector3(i, 0, 0));
    const frames = computeParallelTransportFrames(points, false);
    const radialSegments = 8;
    const geometry = buildTubeGeometry(points, frames, 0.1, radialSegments, false);
    const indexCount = geometry.getIndex()!.count;
    expect(indexCount / 3).toBe(triangleCountForTube(points.length, radialSegments, false));
  });

  it("higher radialSegments produce more triangles", () => {
    const points = [0, 1].map((i) => new THREE.Vector3(i, 0, 0));
    const low = triangleCountForTube(points.length, 4, false);
    const high = triangleCountForTube(points.length, 12, false);
    expect(high).toBeGreaterThan(low);
  });
});

describe("buildTubeGeometry UVs", () => {
  const points = [0, 1, 2, 3].map((i) => new THREE.Vector3(i, 0, 0));
  const frames = computeParallelTransportFrames(points, false);
  const radialSegments = 6;
  const radius = 0.1;
  const geometry = buildTubeGeometry(points, frames, radius, radialSegments, false);
  const ringSize = radialSegments + 1;

  it("adds one seam vertex per ring, with v running 0..1 around it", () => {
    const uv = geometry.getAttribute("uv");
    expect(uv.count).toBe(points.length * ringSize);
    expect(uv.getY(0)).toBe(0);
    expect(uv.getY(radialSegments)).toBeCloseTo(1);
  });

  it("places the seam vertex exactly on the ring's first vertex", () => {
    const position = geometry.getAttribute("position");
    for (const axis of ["getX", "getY", "getZ"] as const) {
      expect(position[axis](radialSegments)).toBeCloseTo(position[axis](0));
    }
  });

  it("measures u in tube circumferences of arc length", () => {
    const uv = geometry.getAttribute("uv");
    const lastRingFirstVertex = (points.length - 1) * ringSize;
    expect(uv.getX(lastRingFirstVertex)).toBeCloseTo(3 / (2 * Math.PI * radius));
  });
});
