import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as THREE from "three";
import { buildStructuralScene } from "../src/geometry/build_meshes";
import { buildYarnPathScene, QUALITY_PRESETS, stitchIdForFace } from "../src/geometry/build_yarn_paths";
import { buildHitProxyScene } from "../src/selection/hit_proxies";
import { validateGeometry } from "../src/geometry/load";
import { SelectionHighlighter } from "../src/selection/highlight";
import { buildGraphOverlay } from "../src/selection/graph_overlay";
import { buildClippingPlane, applyClippingToMaterials } from "../src/clipping/clipping";
import {
  createObjectHeightMeasurement,
  createObjectWidthMeasurement,
  createPointDistanceMeasurement,
  createRoundCircumferenceMeasurement,
  measureDistance,
} from "../src/measurement/measurement";
import type { GeometryDocument } from "../src/types/geometry";
import type { ClippingState } from "../src/state/store";

const dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.join(dirname, "..", "public", "geometry.json");

/**
 * Reports representative fixture measurements, per the requirement to
 * measure rather than claim optimisation. Deliberately no tight pass/fail
 * threshold on timing — only a generous sanity ceiling — since strict
 * timing assertions are fragile across CI hardware.
 */
describe("benchmark: adult_beanie_hdc fixture (1640 stitches)", () => {
  const raw = readFileSync(fixturePath, "utf-8");
  const doc = JSON.parse(raw) as GeometryDocument;

  it("loads and validates within a generous time budget", () => {
    const start = performance.now();
    validateGeometry(doc);
    const elapsed = performance.now() - start;
    console.log(`[benchmark] validation: ${elapsed.toFixed(1)} ms for ${doc.stitches.length} stitches`);
    expect(elapsed).toBeLessThan(2000);
  });

  it("builds the structural instanced scene within a generous time budget", () => {
    const start = performance.now();
    const { groups } = buildStructuralScene(doc);
    const elapsed = performance.now() - start;
    const triangleCount = groups.reduce((sum, g) => {
      const posCount = g.mesh.geometry.getAttribute("position").count;
      return sum + (posCount / 3) * g.mesh.count;
    }, 0);
    console.log(
      `[benchmark] structural build: ${elapsed.toFixed(1)} ms, ${groups.length} draw calls, ` +
        `~${Math.round(triangleCount).toLocaleString()} triangles`,
    );
    expect(elapsed).toBeLessThan(5000);
  });

  for (const qualityName of ["low", "medium", "high"] as const) {
    it(`builds crochet-specific yarn-path geometry at "${qualityName}" quality within budget`, () => {
      const quality = QUALITY_PRESETS[qualityName];
      const start = performance.now();
      const scene = buildYarnPathScene(doc, quality);
      const elapsed = performance.now() - start;
      console.log(
        `[benchmark] yarn-path build (${qualityName}): ${elapsed.toFixed(1)} ms, ` +
          `${scene.components.length} draw calls, ${scene.stats.segmentCount} segments, ` +
          `~${scene.stats.triangleCount.toLocaleString()} triangles`,
      );
      expect(elapsed).toBeLessThan(8000);
    });
  }

  it("reports fixture JSON size", () => {
    const bytes = Buffer.byteLength(raw, "utf-8");
    console.log(`[benchmark] fixture JSON size: ${(bytes / 1024).toFixed(0)} KB`);
    expect(bytes).toBeGreaterThan(0);
  });
});

/**
 * Raycast timing — self-flagged as missing in the prior milestone's own
 * final report. Uses the same Three.js objects (InstancedMesh / merged
 * component Mesh) and the same THREE.Raycaster API the real App uses
 * (App.pickStitch / App.pickYarn), just without going through
 * canvas.getBoundingClientRect() screen-space math — jsdom's canvas has no
 * real layout, so `getBoundingClientRect()` returns a zero-sized rect there
 * and would make every click-to-NDC conversion divide by zero. Raycasting
 * itself needs no WebGL context (only rendering does — see the "App cannot
 * be constructed under Vitest" note below), so casting directly from a
 * chosen NDC vector exercises the real CPU cost this benchmark cares about.
 */
describe("benchmark: raycasting (adult_beanie_hdc fixture)", () => {
  const raw = readFileSync(fixturePath, "utf-8");
  const doc = JSON.parse(raw) as GeometryDocument;
  const structural = buildStructuralScene(doc);
  const yarnScene = buildYarnPathScene(doc, QUALITY_PRESETS.medium);

  const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000);
  const center = new THREE.Vector3(
    (doc.bounds.min[0] + doc.bounds.max[0]) / 2,
    (doc.bounds.min[1] + doc.bounds.max[1]) / 2,
    (doc.bounds.min[2] + doc.bounds.max[2]) / 2,
  );
  const radius = Math.max(
    doc.bounds.max[0] - doc.bounds.min[0],
    doc.bounds.max[1] - doc.bounds.min[1],
    doc.bounds.max[2] - doc.bounds.min[2],
    1,
  );
  camera.position.set(center.x, center.y, center.z + radius * 2);
  camera.lookAt(center);
  camera.updateMatrixWorld();

  // A grid of NDC points sweeping most of the frame, not just dead centre —
  // a single always-centred ray would under-represent real click patterns.
  const NDC_GRID: [number, number][] = [];
  for (let x = -0.6; x <= 0.6; x += 0.3) {
    for (let y = -0.6; y <= 0.6; y += 0.3) NDC_GRID.push([x, y]);
  }

  function raycastAll(meshes: THREE.Object3D[]): number {
    const raycaster = new THREE.Raycaster();
    let hits = 0;
    for (const [x, y] of NDC_GRID) {
      raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
      if (raycaster.intersectObjects(meshes, false).length > 0) hits += 1;
    }
    return hits;
  }

  it("structural mode: raycasts a grid of points against the InstancedMesh groups", () => {
    const meshes = structural.groups.map((g) => g.mesh);
    const start = performance.now();
    let hits = 0;
    const iterations = 20;
    for (let i = 0; i < iterations; i++) hits = raycastAll(meshes);
    const elapsed = (performance.now() - start) / iterations;
    console.log(
      `[benchmark] structural raycast: ${elapsed.toFixed(3)} ms per ${NDC_GRID.length}-point sweep ` +
        `(${hits}/${NDC_GRID.length} points hit geometry), averaged over ${iterations} sweeps`,
    );
    expect(elapsed).toBeLessThan(500);
  });

  it("yarn mode: raycasts a grid of points against the merged component meshes", () => {
    const meshes = yarnScene.components.map((c) => c.mesh);
    const start = performance.now();
    let hits = 0;
    const iterations = 20;
    for (let i = 0; i < iterations; i++) hits = raycastAll(meshes);
    const elapsed = (performance.now() - start) / iterations;
    console.log(
      `[benchmark] yarn raycast: ${elapsed.toFixed(3)} ms per ${NDC_GRID.length}-point sweep ` +
        `(${hits}/${NDC_GRID.length} points hit geometry), averaged over ${iterations} sweeps — ` +
        `compare against the structural number above: this is the actual per-triangle cost ` +
        `difference the open-source-resource-adoption.md three-mesh-bvh re-evaluation is about, ` +
        `not a difference in draw-call/mesh count (both are 3 meshes for this fixture).`,
    );
    expect(elapsed).toBeLessThan(2000);
  });

  it("hit-proxy mode: raycasts a grid of points against the invisible per-stitch proxy spheres", () => {
    const hitProxies = buildHitProxyScene(doc);
    const meshes = hitProxies.groups.map((g) => g.mesh);
    const start = performance.now();
    let hits = 0;
    const iterations = 20;
    for (let i = 0; i < iterations; i++) hits = raycastAll(meshes);
    const elapsed = (performance.now() - start) / iterations;
    console.log(
      `[benchmark] hit-proxy raycast: ${elapsed.toFixed(3)} ms per ${NDC_GRID.length}-point sweep ` +
        `(${hits}/${NDC_GRID.length} points hit geometry), averaged over ${iterations} sweeps — ` +
        `this is the "after" number for selection/hit_proxies.ts: App.pickStitch now always raycasts ` +
        `these low-poly instanced spheres instead of the yarn mode number above, in every view mode.`,
    );
    expect(elapsed).toBeLessThan(500);
  });

  it("hit-proxy raycast resolves to a stitch near where a structural raycast would (correctness, not just speed)", () => {
    // Proxies are deliberately sized *larger* than the structural capsule
    // (a comfortable click target, see hit_proxies.ts), so in densely
    // packed regions (e.g. crown rounds near the centre) the nearest-hit
    // proxy can legitimately be an angularly adjacent stitch rather than
    // bit-for-bit the same instance a tighter structural raycast would
    // report — this checks "resolves to *a* real, nearby stitch," not
    // exact-ID equality, which is the property that actually matters for
    // picking correctness.
    const hitProxies = buildHitProxyScene(doc);
    const proxyMeshes = hitProxies.groups.map((g) => g.mesh);
    const structuralMeshes = structural.groups.map((g) => g.mesh);
    const positionById = new Map(doc.stitches.map((s) => [s.stitch_id, s.position]));
    const stitchSpacingCm = 1 / doc.gauge.stitches_per_cm;
    const raycaster = new THREE.Raycaster();
    let compared = 0;
    for (const [x, y] of NDC_GRID) {
      raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
      const structuralHits = raycaster.intersectObjects(structuralMeshes, false);
      if (structuralHits.length === 0 || structuralHits[0].instanceId === undefined) continue;
      const structuralGroup = structural.groups.find((g) => g.mesh === structuralHits[0].object);
      const expectedStitchId = structuralGroup?.stitchIds[structuralHits[0].instanceId!];
      if (!expectedStitchId) continue;

      const proxyHits = raycaster.intersectObjects(proxyMeshes, false);
      if (proxyHits.length === 0 || proxyHits[0].instanceId === undefined) continue;
      const proxyGroup = hitProxies.groups.find((g) => g.mesh === proxyHits[0].object);
      const proxyStitchId = proxyGroup?.stitchIds[proxyHits[0].instanceId!];
      if (!proxyStitchId) continue;

      const expectedPos = positionById.get(expectedStitchId)!;
      const proxyPos = positionById.get(proxyStitchId)!;
      const distance = Math.hypot(
        expectedPos[0] - proxyPos[0],
        expectedPos[1] - proxyPos[1],
        expectedPos[2] - proxyPos[2],
      );

      compared += 1;
      expect(distance).toBeLessThan(stitchSpacingCm * 3);
    }
    expect(compared).toBeGreaterThan(0);
  });

  it("a raycast hit resolves back to a valid stitch id in yarn mode (correctness alongside timing)", () => {
    const meshes = yarnScene.components.map((c) => c.mesh);
    const raycaster = new THREE.Raycaster();
    let resolved = false;
    for (const [x, y] of NDC_GRID) {
      raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
      const hits = raycaster.intersectObjects(meshes, false);
      if (hits.length === 0) continue;
      const comp = yarnScene.components.find((c) => c.mesh === hits[0].object);
      if (!comp || hits[0].faceIndex == null) continue;
      const stitchId = stitchIdForFace(comp.faceRanges, hits[0].faceIndex);
      if (stitchId) {
        resolved = true;
        expect(doc.stitches.some((s) => s.stitch_id === stitchId)).toBe(true);
      }
    }
    expect(resolved).toBe(true);
  });
});

/**
 * Interaction-operation timings other than raycasting: highlight update,
 * graph-overlay rebuild, a clipping-plane update, and measurement creation.
 * Quality-level switching is *not* duplicated here — it is exactly the
 * yarn-path build time already measured above (setQuality tears down and
 * rebuilds the yarn scene at the new quality, which is the same
 * `buildYarnPathScene` call). X-ray mode switching is a single
 * `material.opacity`/`transparent`/`depthWrite` write per material — not
 * separately timed since it is orders of magnitude cheaper than anything
 * else on this page and there is no realistic scenario where it would be
 * the bottleneck.
 *
 * None of these need a WebGLRenderer/canvas — only `App`'s constructor
 * does (it eagerly creates one), which is why this file benchmarks the
 * underlying pure functions/classes directly rather than driving a real
 * `App` instance; `new App(...)` throws under Vitest's jsdom environment
 * ("Error creating WebGL context") since jsdom has no real GPU/WebGL
 * backing, confirmed by direct probing during this audit. The equivalent
 * full-`App` lifecycle/leak stress test lives in
 * `e2e/compile-workflow.spec.ts` instead, against a real browser.
 */
describe("benchmark: other interaction operations (adult_beanie_hdc fixture)", () => {
  const raw = readFileSync(fixturePath, "utf-8");
  const doc = JSON.parse(raw) as GeometryDocument;
  const structural = buildStructuralScene(doc);
  const selectedStitchId = doc.stitches[Math.floor(doc.stitches.length / 2)].stitch_id;

  it("selection-highlight update", () => {
    const highlighter = new SelectionHighlighter(new THREE.Scene());
    const iterations = 200;
    const start = performance.now();
    for (let i = 0; i < iterations; i++) highlighter.select(selectedStitchId, structural);
    const elapsed = (performance.now() - start) / iterations;
    console.log(`[benchmark] selection-highlight update: ${elapsed.toFixed(3)} ms per call`);
    expect(elapsed).toBeLessThan(50);
  });

  it("graph-overlay rebuild", () => {
    const iterations = 50;
    const start = performance.now();
    for (let i = 0; i < iterations; i++) buildGraphOverlay(doc, selectedStitchId);
    const elapsed = (performance.now() - start) / iterations;
    console.log(`[benchmark] graph-overlay rebuild: ${elapsed.toFixed(3)} ms per call`);
    expect(elapsed).toBeLessThan(200);
  });

  it("clipping-plane update", () => {
    const clipping: ClippingState = { enabled: true, axis: "z", offset: 0.25, invert: false };
    const materials = structural.groups.map((g) => g.mesh.material as THREE.Material);
    const iterations = 200;
    const start = performance.now();
    for (let i = 0; i < iterations; i++) {
      const plane = buildClippingPlane(doc.bounds, clipping);
      applyClippingToMaterials(materials, plane);
    }
    const elapsed = (performance.now() - start) / iterations;
    console.log(`[benchmark] clipping-plane update: ${elapsed.toFixed(3)} ms per call`);
    expect(elapsed).toBeLessThan(50);
  });

  it("measurement creation (every type)", () => {
    const a = doc.stitches[0].stitch_id;
    const b = doc.stitches[1].stitch_id;
    const iterations = 200;
    const start = performance.now();
    for (let i = 0; i < iterations; i++) {
      measureDistance(doc, a, b);
      createPointDistanceMeasurement(doc, [0, 0, 0], [1, 1, 1]);
      createObjectWidthMeasurement(doc);
      createObjectHeightMeasurement(doc);
      createRoundCircumferenceMeasurement(doc, doc.stitches[0].component_id, doc.stitches[0].round_index);
    }
    const elapsed = (performance.now() - start) / iterations;
    console.log(`[benchmark] measurement creation (all 5 types, one call each): ${elapsed.toFixed(3)} ms per round`);
    expect(elapsed).toBeLessThan(50);
  });
});
