import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { buildStructuralScene } from "../src/geometry/build_meshes";
import { buildYarnMeshes } from "../src/geometry/build_yarn";
import { validateGeometry } from "../src/geometry/load";
import type { GeometryDocument } from "../src/types/geometry";

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

  it("builds merged yarn meshes within a generous time budget", () => {
    const start = performance.now();
    const meshes = buildYarnMeshes(doc);
    const elapsed = performance.now() - start;
    console.log(`[benchmark] yarn build: ${elapsed.toFixed(1)} ms, ${meshes.length} merged meshes`);
    expect(elapsed).toBeLessThan(5000);
  });

  it("reports fixture JSON size", () => {
    const bytes = Buffer.byteLength(raw, "utf-8");
    console.log(`[benchmark] fixture JSON size: ${(bytes / 1024).toFixed(0)} KB`);
    expect(bytes).toBeGreaterThan(0);
  });
});
