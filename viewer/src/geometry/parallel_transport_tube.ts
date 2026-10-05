import * as THREE from "three";

/**
 * Parallel-transport (rotation-minimizing) frames along a polyline, used
 * instead of `THREE.Curve.computeFrenetFrames`.
 *
 * Investigation (per the brief): Three.js's built-in Frenet-frame
 * computation derives the normal from curvature, which is undefined for a
 * perfectly straight segment and numerically unstable near-zero-curvature
 * points — exactly the shape of this project's "connector"/"increase_branch"/
 * "decrease_bridge" segments (near-straight lines between two stitches) and
 * the low-curvature stretches of a "post" curve. Three.js's fallback picks
 * an arbitrary consistent normal per-curve, which is stable for one static
 * straight segment in isolation, but produces visible discontinuities where
 * a mixed curve (e.g. a post with wrap loops) transitions between
 * high-curvature and near-zero-curvature stretches. Parallel transport
 * avoids this entirely: each frame is derived by rotating the *previous*
 * frame by the angle between consecutive tangents (Rodrigues' rotation),
 * never by curvature, so it degrades gracefully to "no rotation" on a
 * straight stretch instead of picking an arbitrary new normal.
 *
 * Decision: used for every semantic yarn segment in this project (see
 * build_yarn_paths.ts), not just the straight ones — it is never worse than
 * Frenet for curved sections and strictly better for straight ones.
 */
export interface TransportFrame {
  tangent: THREE.Vector3;
  normal: THREE.Vector3;
  binormal: THREE.Vector3;
}

export function computeParallelTransportFrames(
  points: THREE.Vector3[],
  closed: boolean,
): TransportFrame[] {
  const n = points.length;
  if (n < 2) throw new Error("need at least 2 points to compute transport frames");

  const tangents: THREE.Vector3[] = [];
  for (let i = 0; i < n; i++) {
    const prevIndex = closed ? (i - 1 + n) % n : Math.max(0, i - 1);
    const nextIndex = closed ? (i + 1) % n : Math.min(n - 1, i + 1);
    const tangent = points[nextIndex].clone().sub(points[prevIndex]);
    tangents.push(tangent.lengthSq() > 1e-12 ? tangent.normalize() : new THREE.Vector3(1, 0, 0));
  }

  const firstTangent = tangents[0];
  const seed =
    Math.abs(firstTangent.dot(new THREE.Vector3(0, 1, 0))) > 0.99
      ? new THREE.Vector3(1, 0, 0)
      : new THREE.Vector3(0, 1, 0);
  const firstNormal = seed
    .clone()
    .sub(firstTangent.clone().multiplyScalar(seed.dot(firstTangent)))
    .normalize();

  const frames: TransportFrame[] = [
    {
      tangent: firstTangent,
      normal: firstNormal,
      binormal: firstTangent.clone().cross(firstNormal).normalize(),
    },
  ];

  for (let i = 1; i < n; i++) {
    const prevTangent = tangents[i - 1];
    const curTangent = tangents[i];
    const axis = prevTangent.clone().cross(curTangent);
    const normal = frames[i - 1].normal.clone();
    if (axis.lengthSq() > 1e-12) {
      const angle = Math.acos(THREE.MathUtils.clamp(prevTangent.dot(curTangent), -1, 1));
      normal.applyAxisAngle(axis.normalize(), angle);
    }
    normal.sub(curTangent.clone().multiplyScalar(curTangent.dot(normal))).normalize();
    frames.push({ tangent: curTangent, normal, binormal: curTangent.clone().cross(normal).normalize() });
  }

  if (closed) {
    // The accumulated rotation around the loop rarely closes exactly —
    // distribute the residual twist evenly so frame[0] and frame[n-1] meet
    // without a visible seam.
    const gap = Math.acos(THREE.MathUtils.clamp(frames[0].normal.dot(frames[n - 1].normal), -1, 1));
    if (gap > 1e-6) {
      for (let i = 0; i < n; i++) {
        const t = i / (n - 1);
        frames[i].normal.applyAxisAngle(frames[i].tangent, -gap * t);
        frames[i].binormal = frames[i].tangent.clone().cross(frames[i].normal).normalize();
      }
    }
  }

  return frames;
}

/** Builds a tube mesh geometry from sampled centreline points and precomputed frames. */
export function buildTubeGeometry(
  points: THREE.Vector3[],
  frames: TransportFrame[],
  radius: number,
  radialSegments: number,
  closed: boolean,
  color?: THREE.Color,
): THREE.BufferGeometry {
  const n = points.length;
  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  const colors: number[] = [];
  // Each ring carries one extra seam vertex (j === radialSegments, same
  // position as j === 0, v = 1) so the texture wraps cleanly instead of
  // interpolating v backwards across the last quad. Triangle count is
  // unchanged — only the vertex count grows by one per ring.
  const ringSize = radialSegments + 1;
  // u is measured in tube circumferences of arc length, so a texture's
  // aspect stays the same on thick and thin yarn and on long and short runs.
  const circumference = 2 * Math.PI * radius;
  let arcLength = 0;

  for (let i = 0; i < n; i++) {
    if (i > 0) arcLength += points[i].distanceTo(points[i - 1]);
    const u = circumference > 0 ? arcLength / circumference : 0;
    const { normal, binormal } = frames[i];
    for (let j = 0; j < ringSize; j++) {
      const angle = (j / radialSegments) * Math.PI * 2;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      const nx = normal.x * cos + binormal.x * sin;
      const ny = normal.y * cos + binormal.y * sin;
      const nz = normal.z * cos + binormal.z * sin;
      positions.push(points[i].x + nx * radius, points[i].y + ny * radius, points[i].z + nz * radius);
      normals.push(nx, ny, nz);
      uvs.push(u, j / radialSegments);
      if (color) colors.push(color.r, color.g, color.b);
    }
  }

  const indices: number[] = [];
  const segCount = closed ? n : n - 1;
  for (let i = 0; i < segCount; i++) {
    const iNext = closed ? (i + 1) % n : i + 1;
    for (let j = 0; j < radialSegments; j++) {
      const a = i * ringSize + j;
      const b = iNext * ringSize + j;
      const c = iNext * ringSize + j + 1;
      const d = i * ringSize + j + 1;
      indices.push(a, b, d, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  if (color) geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  return geometry;
}

export function triangleCountForTube(pointCount: number, radialSegments: number, closed: boolean): number {
  const segCount = closed ? pointCount : pointCount - 1;
  return segCount * radialSegments * 2;
}
