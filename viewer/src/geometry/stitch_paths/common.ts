import type { StitchGeometry } from "../../types/geometry";
import type { Vec3 } from "./types";

export function add(a: Vec3, b: Vec3): Vec3 {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

export function scale(a: Vec3, s: number): Vec3 {
  return [a[0] * s, a[1] * s, a[2] * s];
}

export function lerp(a: Vec3, b: Vec3, t: number): Vec3 {
  return add(scale(a, 1 - t), scale(b, t));
}

/** A small loop of `count` points in the plane spanned by (u, v), centred at `center`. */
export function loopPoints(center: Vec3, u: Vec3, v: Vec3, radius: number, count = 8): Vec3[] {
  const points: Vec3[] = [];
  for (let i = 0; i < count; i++) {
    const angle = (2 * Math.PI * i) / count;
    const offset = add(scale(u, Math.cos(angle) * radius), scale(v, Math.sin(angle) * radius));
    points.push(add(center, offset));
  }
  return points;
}

/** The stitch's local frame as plain tuples, for readability at call sites. */
export function frameOf(stitch: StitchGeometry): { T: Vec3; N: Vec3; B: Vec3; P: Vec3 } {
  return { T: stitch.tangent, N: stitch.normal, B: stitch.binormal, P: stitch.position };
}
