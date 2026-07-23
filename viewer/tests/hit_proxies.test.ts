import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { Picker } from "../src/selection/picking";
import { buildHitProxyScene, disposeHitProxyScene } from "../src/selection/hit_proxies";
import type { GeometryDocument } from "../src/types/geometry";

function makeDoc(): GeometryDocument {
  return {
    schema_version: "0.1.0",
    pattern_fingerprint: null,
    graph_fingerprint: null,
    geometry_fingerprint: null,
    units: "cm",
    gauge: { stitches_per_cm: 2, rounds_per_cm: 2, yarn_diameter_cm: 0.3 },
    stitches: [
      {
        stitch_id: "a",
        component_id: "crown",
        stitch_type: "sc",
        round_index: 1,
        sequence_index: 0,
        position: [0, 0, 0],
        orientation: [0, 0, 0, 1],
        tangent: [1, 0, 0],
        normal: [0, 1, 0],
        binormal: [0, 0, 1],
        scale: 1,
        loop_placement: "both",
        colour_id: "main",
        yarn_id: "main",
        parent_stitch_ids: [],
        is_increase: false,
        is_decrease: false,
        source_reference: "test",
      },
      {
        stitch_id: "b",
        component_id: "body",
        stitch_type: "sc",
        round_index: 1,
        sequence_index: 1,
        position: [5, 0, 0],
        orientation: [0, 0, 0, 1],
        tangent: [1, 0, 0],
        normal: [0, 1, 0],
        binormal: [0, 0, 1],
        scale: 1,
        loop_placement: "both",
        colour_id: "main",
        yarn_id: "main",
        parent_stitch_ids: [],
        is_increase: false,
        is_decrease: false,
        source_reference: "test",
      },
    ],
    yarn_segments: [],
    edges: [],
    bounds: { min: [-1, -1, -1], max: [6, 1, 1] },
    measurements: { overall_height_cm: 1, max_radius_cm: 5, max_circumference_cm: 30 },
    warnings: [],
  };
}

function cameraLookingAt(x: number, y: number, z: number): THREE.PerspectiveCamera {
  const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000);
  camera.position.set(x, y, z + 5);
  camera.lookAt(x, y, z);
  camera.updateMatrixWorld();
  return camera;
}

function makeCanvas(): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.getBoundingClientRect = () => ({
    left: 0,
    top: 0,
    right: 100,
    bottom: 100,
    width: 100,
    height: 100,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
  return canvas;
}

describe("buildHitProxyScene", () => {
  it("builds one instanced group per component with correct stitch-id lookup", () => {
    const scene = buildHitProxyScene(makeDoc());
    expect(scene.groups.map((g) => g.componentId).sort()).toEqual(["body", "crown"]);
    expect(scene.stitchIdToLocation.get("a")?.group.componentId).toBe("crown");
    expect(scene.stitchIdToLocation.get("b")?.group.componentId).toBe("body");
  });

  it("proxy meshes are transparent (zero visual footprint) but stay visible=true so they remain raycastable", () => {
    const scene = buildHitProxyScene(makeDoc());
    for (const group of scene.groups) {
      expect(group.mesh.visible).toBe(true);
      const material = group.mesh.material as THREE.MeshBasicMaterial;
      expect(material.opacity).toBe(0);
      expect(material.transparent).toBe(true);
    }
  });

  it("disposeHitProxyScene removes meshes from the scene and disposes their resources", () => {
    const threeScene = new THREE.Scene();
    const proxyScene = buildHitProxyScene(makeDoc());
    for (const group of proxyScene.groups) threeScene.add(group.mesh);
    expect(threeScene.children.length).toBe(2);

    disposeHitProxyScene(threeScene, proxyScene);
    expect(threeScene.children.length).toBe(0);
  });
});

describe("Picker (hit-proxy regression)", () => {
  it("resolves a stitch id via raycasting against a StructuralScene-shaped proxy set", () => {
    const proxyScene = buildHitProxyScene(makeDoc());
    const threeScene = new THREE.Scene();
    for (const group of proxyScene.groups) threeScene.add(group.mesh);

    const camera = cameraLookingAt(0, 0, 0);
    const picker = new Picker();
    const canvas = makeCanvas();
    const event = { clientX: 50, clientY: 50 } as PointerEvent;

    const stitchId = picker.pick(event, canvas, camera, proxyScene);
    expect(stitchId).toBe("a");
  });

  it("regression: a group whose mesh.visible is false must never be picked — Three.js's Raycaster " +
    "does not skip invisible objects on its own, so Picker must filter explicitly", () => {
    const proxyScene = buildHitProxyScene(makeDoc());
    const crownGroup = proxyScene.groups.find((g) => g.componentId === "crown")!;
    crownGroup.mesh.visible = false;

    const camera = cameraLookingAt(0, 0, 0);
    const picker = new Picker();
    const canvas = makeCanvas();
    const event = { clientX: 50, clientY: 50 } as PointerEvent;

    const stitchId = picker.pick(event, canvas, camera, proxyScene);
    expect(stitchId).toBeNull();
  });

  it("returns null when the ray hits nothing", () => {
    const proxyScene = buildHitProxyScene(makeDoc());
    const camera = cameraLookingAt(100, 100, 100);
    const picker = new Picker();
    const canvas = makeCanvas();
    const event = { clientX: 50, clientY: 50 } as PointerEvent;

    expect(picker.pick(event, canvas, camera, proxyScene)).toBeNull();
  });
});
