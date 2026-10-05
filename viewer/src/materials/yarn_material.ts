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
 * rather than sharp and mirror-like. A procedural ply bump map adds the
 * twisted-strand relief that makes a tube read as yarn rather than wire.
 */
export interface YarnMaterialOptions {
  color?: THREE.ColorRepresentation;
  roughness?: number;
  sheen?: number;
  sheenRoughness?: number;
  sheenColor?: THREE.ColorRepresentation;
  envMapIntensity?: number;
  opacity?: number;
  /** Twisted-ply surface relief. Off for flat analysis overlays. */
  plyTexture?: boolean;
}

const DEFAULTS: Required<YarnMaterialOptions> = {
  color: 0xcbb89a,
  roughness: 0.85,
  // Low and warm: a strong white sheen bleaches every yarn colour toward
  // grey-pink (observed while tuning the soft_studio default).
  sheen: 0.35,
  sheenRoughness: 0.5,
  sheenColor: 0xfff0ea,
  envMapIntensity: 0.9,
  opacity: 1,
  plyTexture: true,
};

/** Strands twisted together in the ply texture. */
const PLY_COUNT = 3;
const PLY_TEXTURE_SIZE = 128;
/** Bump depth. Tuned by eye at close zoom: below ~8 the plies vanish into
 * hairlines, above ~25 they read as zebra-striped rope on high-DPI screens. */
const PLY_BUMP_SCALE = 14;

let plyTexture: THREE.Texture | null = null;

/**
 * A tileable grayscale texture of `PLY_COUNT` strands spiralling around the
 * tube. Tube UVs (parallel_transport_tube.ts) run u along the yarn in units
 * of circumference and v around it, so a band whose phase advances equally
 * in u and v twists at roughly 45° — close to a real worsted yarn's ply
 * angle. Integer periods on both axes keep the texture seamless.
 *
 * Built as a DataTexture from raw bytes, so it needs no 2D canvas and
 * behaves identically in browsers and in jsdom unit tests.
 */
function getPlyTexture(): THREE.Texture {
  if (plyTexture) return plyTexture;
  const size = PLY_TEXTURE_SIZE;
  const data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const phase = (PLY_COUNT * (x + y)) / size;
      // A rounded ridge per strand with a narrow dark groove between them,
      // plus faint fibre streaks running along each strand.
      const strand = Math.pow(Math.sin(Math.PI * (phase % 1)), 0.6);
      const fibre = 0.06 * Math.sin((2 * Math.PI * 9 * (x - y)) / size);
      const byte = Math.round(Math.max(0, Math.min(1, 0.15 + 0.8 * strand + fibre)) * 255);
      const offset = (y * size + x) * 4;
      data[offset] = byte;
      data[offset + 1] = byte;
      data[offset + 2] = byte;
      data[offset + 3] = 255;
    }
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.colorSpace = THREE.NoColorSpace;
  texture.anisotropy = 4;
  texture.needsUpdate = true;
  plyTexture = texture;
  return plyTexture;
}

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
  if (resolved.plyTexture) {
    material.bumpMap = getPlyTexture();
    material.bumpScale = PLY_BUMP_SCALE;
  }
  return material;
}

export const SEMANTIC_YARN_COLORS = {
  main: 0xcbb89a,
  increase: 0xe8a33d,
  decrease: 0xe85d5d,
  selected: 0xf5e642,
} as const;

/** Yarn colours offered in the viewer. Muted, real-yarn-like tones rather
 * than saturated UI colours, so the model reads as a crocheted object. */
export const YARN_COLOURS = [
  { id: "rose", label: "Dusty rose", hex: 0xd99a92 },
  { id: "oat", label: "Oatmeal", hex: 0xd8c7a8 },
  { id: "sage", label: "Sage", hex: 0x9fb38f },
  { id: "sky", label: "Sky", hex: 0x8fb4d1 },
  { id: "mustard", label: "Mustard", hex: 0xd9a944 },
  { id: "lavender", label: "Lavender", hex: 0xb3a2cf },
  { id: "charcoal", label: "Charcoal", hex: 0x55504c },
] as const;

export type YarnColourId = (typeof YARN_COLOURS)[number]["id"];

export const DEFAULT_YARN_COLOUR: YarnColourId = "rose";

export function yarnColourHex(id: YarnColourId): number {
  return (YARN_COLOURS.find((c) => c.id === id) ?? YARN_COLOURS[0]).hex;
}

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
