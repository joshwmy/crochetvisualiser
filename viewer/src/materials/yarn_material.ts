import * as THREE from "three";

/**
 * Reusable yarn material preset. Starts from `MeshPhysicalMaterial` — per
 * the brief, unless measurement shows it's inadequate, which nothing in
 * this project has yet (no frame-time regression has been measured
 * attributable to material choice; see docs/yarn-material-and-lighting.md).
 *
 * Deliberately avoids: high clearcoat, transmission, and normal-map
 * "glitter" — all of which read as plastic/wet rather than soft fibre.
 * Sheen (a thin-fibre-like grazing highlight) is what actually gives yarn
 * its look; roughness stays high so specular highlights stay soft and wide
 * rather than sharp and mirror-like.
 */
export interface YarnMaterialOptions {
  color?: THREE.ColorRepresentation;
  roughness?: number;
  sheen?: number;
  sheenRoughness?: number;
  sheenColor?: THREE.ColorRepresentation;
  envMapIntensity?: number;
  opacity?: number;
}

const DEFAULTS: Required<YarnMaterialOptions> = {
  color: 0xcbb89a,
  roughness: 0.92,
  sheen: 0.65,
  sheenRoughness: 0.55,
  sheenColor: 0xffffff,
  envMapIntensity: 0.6,
  opacity: 1,
};

export function createYarnMaterial(options: YarnMaterialOptions = {}): THREE.MeshPhysicalMaterial {
  const resolved = { ...DEFAULTS, ...options };
  const material = new THREE.MeshPhysicalMaterial({
    color: resolved.color,
    roughness: resolved.roughness,
    metalness: 0,
    sheen: resolved.sheen,
    sheenRoughness: resolved.sheenRoughness,
    sheenColor: new THREE.Color(resolved.sheenColor),
    envMapIntensity: resolved.envMapIntensity,
    transparent: resolved.opacity < 1,
    opacity: resolved.opacity,
    clearcoat: 0,
    transmission: 0,
  });
  return material;
}

export const SEMANTIC_YARN_COLORS = {
  main: 0xcbb89a,
  increase: 0xe8a33d,
  decrease: 0xe85d5d,
  selected: 0xf5e642,
} as const;

/** Applies the shared x-ray/opacity/highlight state to an existing yarn material in place. */
export function applyYarnMaterialState(
  material: THREE.MeshPhysicalMaterial,
  state: { opacity: number; xray: boolean },
): void {
  const effectiveOpacity = state.xray ? Math.min(state.opacity, 0.22) : state.opacity;
  material.opacity = effectiveOpacity;
  material.transparent = effectiveOpacity < 1;
  material.depthWrite = effectiveOpacity >= 0.98;
}
