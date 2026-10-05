import * as THREE from "three";

export type LightingPreset = "neutral_laboratory" | "soft_studio" | "high_contrast_inspection";

interface LightingConfig {
  background: number;
  hemisphereSky: number;
  hemisphereGround: number;
  hemisphereIntensity: number;
  keyIntensity: number;
  fillIntensity: number;
  fillColor: number;
  rimIntensity: number;
}

/**
 * Three presets, all built from the same key/fill/rim recipe — only
 * intensities/colours differ. `neutral_laboratory` is the default: even,
 * shadow-light illumination so stitch structure reads clearly regardless of
 * yarn colour, view mode, or clipping state (per the brief's explicit
 * "avoid highly dramatic cinematic lighting that obscures stitch structure").
 */
const LIGHTING_PRESETS: Record<LightingPreset, LightingConfig> = {
  neutral_laboratory: {
    background: 0x11151c,
    hemisphereSky: 0xffffff,
    hemisphereGround: 0x444455,
    hemisphereIntensity: 1.2,
    keyIntensity: 1.5,
    fillIntensity: 0.4,
    fillColor: 0xaaccff,
    rimIntensity: 0.5,
  },
  soft_studio: {
    background: 0x1a1c22,
    hemisphereSky: 0xfff4e6,
    hemisphereGround: 0x4a4238,
    hemisphereIntensity: 1.0,
    keyIntensity: 1.1,
    fillIntensity: 0.6,
    fillColor: 0xffe8cc,
    rimIntensity: 0.3,
  },
  high_contrast_inspection: {
    background: 0x05070a,
    hemisphereSky: 0xffffff,
    hemisphereGround: 0x111111,
    hemisphereIntensity: 0.6,
    keyIntensity: 2.2,
    fillIntensity: 0.15,
    fillColor: 0xffffff,
    rimIntensity: 0.9,
  },
};

export function createScene(preset: LightingPreset = "neutral_laboratory"): THREE.Scene {
  const scene = new THREE.Scene();
  applyLightingPreset(scene, preset);

  const grid = new THREE.GridHelper(40, 40, 0x2a3040, 0x1c2028);
  grid.position.y = -20;
  scene.add(grid);

  const axes = new THREE.AxesHelper(3);
  scene.add(axes);

  return scene;
}

const LIGHT_NAMES = ["hemisphere-light", "key-light", "fill-light", "rim-light"];

/** Rebuilds the scene's lighting rig in place (used by the lighting-preset switcher). */
export function applyLightingPreset(scene: THREE.Scene, preset: LightingPreset): void {
  for (const name of LIGHT_NAMES) {
    const existing = scene.getObjectByName(name);
    if (existing) scene.remove(existing);
  }

  const config = LIGHTING_PRESETS[preset];
  scene.background = new THREE.Color(config.background);

  const hemisphere = new THREE.HemisphereLight(
    config.hemisphereSky,
    config.hemisphereGround,
    config.hemisphereIntensity,
  );
  hemisphere.name = "hemisphere-light";
  scene.add(hemisphere);

  const key = new THREE.DirectionalLight(0xffffff, config.keyIntensity);
  key.name = "key-light";
  key.position.set(5, 8, 6);
  scene.add(key);

  const fill = new THREE.DirectionalLight(config.fillColor, config.fillIntensity);
  fill.name = "fill-light";
  fill.position.set(-6, 2, -4);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0xffffff, config.rimIntensity);
  rim.name = "rim-light";
  rim.position.set(0, 4, -8);
  scene.add(rim);
}

export function lightingPresetNames(): LightingPreset[] {
  return Object.keys(LIGHTING_PRESETS) as LightingPreset[];
}
