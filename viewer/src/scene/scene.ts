import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

export type LightingPreset = "neutral_laboratory" | "soft_studio" | "high_contrast_inspection";

export const DEFAULT_LIGHTING_PRESET: LightingPreset = "soft_studio";

interface LightingConfig {
  /** Solid backdrop, or null to let the page's CSS stage gradient show through. */
  background: number | null;
  hemisphereSky: number;
  hemisphereGround: number;
  hemisphereIntensity: number;
  keyIntensity: number;
  fillIntensity: number;
  fillColor: number;
  rimIntensity: number;
  /** Strength of the soft room reflections that give yarn its fibre sheen. */
  environmentIntensity: number;
}

/**
 * Three presets, all built from the same key/fill/rim recipe — only
 * intensities/colours differ. `soft_studio` is the default: warm, gentle
 * light over a transparent backdrop so the model reads as a crocheted
 * object, the way a maker would photograph one. `neutral_laboratory` keeps
 * the even, shadow-light illumination the scientific views were tuned
 * under (per the brief's "avoid highly dramatic cinematic lighting that
 * obscures stitch structure"), and `high_contrast_inspection` exaggerates
 * relief for close inspection.
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
    environmentIntensity: 0.6,
  },
  soft_studio: {
    background: null,
    hemisphereSky: 0xfff4e6,
    hemisphereGround: 0x6b5a4a,
    hemisphereIntensity: 0.35,
    keyIntensity: 1.0,
    fillIntensity: 0.3,
    fillColor: 0xffe8cc,
    rimIntensity: 0.6,
    environmentIntensity: 0.35,
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
    environmentIntensity: 0.3,
  },
};

const HELPER_NAMES = ["floor-grid", "axes"];

/** Hemisphere intensity per unit of missing environment intensity. Tuned by
 * eye so the software-rendered default roughly matches the GPU one. */
const ENVIRONMENT_TO_HEMISPHERE = 2;

export function createScene(preset: LightingPreset = DEFAULT_LIGHTING_PRESET): THREE.Scene {
  const scene = new THREE.Scene();
  applyLightingPreset(scene, preset);

  // Measuring aids, hidden by default: on first sight they make the model
  // read as a CAD part rather than a crocheted piece. Toggled from the
  // Appearance tab via setHelpersVisible.
  const grid = new THREE.GridHelper(40, 40, 0x2a3040, 0x1c2028);
  grid.name = "floor-grid";
  grid.position.y = -20;
  grid.visible = false;
  scene.add(grid);

  const axes = new THREE.AxesHelper(3);
  axes.name = "axes";
  axes.visible = false;
  scene.add(axes);

  return scene;
}

export function setHelpersVisible(scene: THREE.Scene, visible: boolean): void {
  for (const name of HELPER_NAMES) {
    const helper = scene.getObjectByName(name);
    if (helper) helper.visible = visible;
  }
}

/**
 * Gives the scene a soft, neutral room to reflect. Without an environment
 * map the yarn material's sheen and envMapIntensity have nothing to pick
 * up, and fibre reads as flat plastic.
 */
export function applyStudioEnvironment(scene: THREE.Scene, renderer: THREE.WebGLRenderer): void {
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  scene.environment = pmrem.fromScene(room, 0.04).texture;
  room.dispose();
  pmrem.dispose();
}

const LIGHT_NAMES = ["hemisphere-light", "key-light", "fill-light", "rim-light"];

/** Rebuilds the scene's lighting rig in place (used by the lighting-preset switcher). */
export function applyLightingPreset(scene: THREE.Scene, preset: LightingPreset): void {
  for (const name of LIGHT_NAMES) {
    const existing = scene.getObjectByName(name);
    if (existing) scene.remove(existing);
  }

  const config = LIGHTING_PRESETS[preset];
  scene.background = config.background === null ? null : new THREE.Color(config.background);
  scene.environmentIntensity = config.environmentIntensity;

  // Without an environment map (software renderers skip it — see
  // isSoftwareRenderer) its soft fill is missing and colours go muddy, so
  // the hemisphere light takes over that share.
  const hemisphereIntensity = scene.environment
    ? config.hemisphereIntensity
    : config.hemisphereIntensity + config.environmentIntensity * ENVIRONMENT_TO_HEMISPHERE;
  const hemisphere = new THREE.HemisphereLight(
    config.hemisphereSky,
    config.hemisphereGround,
    hemisphereIntensity,
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
