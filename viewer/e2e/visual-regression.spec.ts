import { test, expect, type Page } from "@playwright/test";
import { openPanelTab, skipOnboarding } from "./helpers";

/**
 * Deterministic screenshot regression suite.
 *
 * Scope, deliberately reduced from the brief's suggested ~15 screenshots to
 * 9: enough to cover every stitch-geometry family (chain, slip stitch, sc,
 * hdc, dc, increase, decrease, FLO, BLO) plus every scientific-inspection
 * mode (yarn, structural, X-ray, clipping, graph overlay, path-inspection,
 * measurement) at least once, without the suite becoming a second, slower
 * copy of the workflow tests in compile-workflow.spec.ts. Documented here
 * rather than silently shortened.
 *
 * Fixture strategy: rather than going through the written-pattern
 * compiler (whose grammar doesn't support chain/slip-stitch/FLO/BLO
 * syntax at all — see docs/known-limitations.md), this suite calls
 * `window.__app.loadGeometryDocument(doc)` directly with a hand-built
 * synthetic GeometryDocument. This is the same public method the real
 * compile workflow calls after a successful compile — using it directly
 * is not a special test-only code path, just a way to supply stitch types
 * and loop placements the grammar can't produce yet, matching the
 * project's own "no parser changes for this audit" boundary.
 *
 * Stabilisation: fixed viewport/deviceScaleFactor (test.use below),
 * `low` quality (fewer triangles = less anti-aliasing-driven pixel noise,
 * and much faster to build across 9 screenshots), `reduced motion`
 * emulated *before* navigation (App reads matchMedia at construction time
 * to disable OrbitControls damping — see App.ts), the default
 * default `soft_studio` lighting preset and default yarn colours (never
 * changed), animation always fully built (this pipeline has no partial
 * default state), and a fixed "front" camera preset for every screenshot.
 * A short `waitForTimeout` after each state change gives the last
 * `requestAnimationFrame` a chance to settle before capturing.
 *
 * Known limitation: WebGL anti-aliasing and font rendering can differ
 * across GPUs/drivers even with all of the above held constant — the
 * `maxDiffPixelRatio` below is deliberately generous (8%) to absorb that
 * without masking a real regression (a genuinely broken render — wrong
 * colours, missing geometry, wrong camera — produces far more than 8%
 * pixel difference). Regenerating baselines to make a real regression
 * disappear is not an acceptable use of `--update-snapshots`; baselines
 * should only be regenerated when a change is an intentional visual
 * change, reviewed as such.
 */

test.use({ viewport: { width: 960, height: 720 }, deviceScaleFactor: 1 });

// `timeout` is generous for the same reason compile-workflow.spec.ts's own
// suite timeout is generous: this environment showed real, occasionally
// large variance in Three.js build/layout-settle time across this whole
// audit session (a shared, CPU-constrained machine, not representative of
// a typical developer machine — see docs/performance-benchmarks.md's
// "Environment" note) — Playwright's default 5s screenshot-stability wait
// was observed to be too tight on a cold first run.
const SCREENSHOT_OPTIONS = { maxDiffPixelRatio: 0.08, timeout: 20_000 } as const;

interface SyntheticStitch {
  stitch_id: string;
  component_id: string;
  stitch_type: string;
  round_index: number;
  sequence_index: number;
  position: [number, number, number];
  orientation: [number, number, number, number];
  tangent: [number, number, number];
  normal: [number, number, number];
  binormal: [number, number, number];
  scale: number;
  loop_placement: string;
  colour_id: string;
  yarn_id: string;
  parent_stitch_ids: string[];
  is_increase: boolean;
  is_decrease: boolean;
  source_reference: string;
}

/**
 * One "kitchen sink" fixture covering every stitch-geometry family and
 * every loop-placement case in a single 11-stitch ring — small enough to
 * build and raycast quickly across 9 screenshots, varied enough to
 * exercise every strategy at least once. Stitches are laid out evenly
 * around a circle so every screenshot uses the same predictable framing.
 */
function buildKitchenSinkFixture() {
  const specs: Array<{
    id: string;
    type: string;
    parents: string[];
    loop?: string;
    increase?: boolean;
    decrease?: boolean;
  }> = [
    { id: "chain-0", type: "chain", parents: [] },
    { id: "slip-1", type: "slip_stitch", parents: ["chain-0"] },
    { id: "sc-2", type: "sc", parents: ["slip-1"] },
    { id: "hdc-3", type: "hdc", parents: ["sc-2"] },
    { id: "dc-4", type: "dc", parents: ["hdc-3"] },
    { id: "inc-a-5", type: "sc", parents: ["dc-4"], increase: true },
    { id: "inc-b-6", type: "sc", parents: ["dc-4"], increase: true },
    { id: "flo-7", type: "sc", parents: ["inc-b-6"], loop: "front_loop_only" },
    { id: "blo-8", type: "sc", parents: ["flo-7"], loop: "back_loop_only" },
    { id: "plain-9", type: "sc", parents: ["blo-8"] },
    { id: "dec-10", type: "sc", parents: ["blo-8", "plain-9"], decrease: true },
  ];

  const radius = 2.5;
  const n = specs.length;
  const stitches: SyntheticStitch[] = specs.map((spec, i) => {
    const angle = (i / n) * Math.PI * 2;
    const position: [number, number, number] = [Math.cos(angle) * radius, Math.sin(angle) * radius, 0];
    const tangent: [number, number, number] = [-Math.sin(angle), Math.cos(angle), 0];
    const normal: [number, number, number] = [Math.cos(angle), Math.sin(angle), 0];
    const binormal: [number, number, number] = [0, 0, 1];
    return {
      stitch_id: spec.id,
      component_id: "ring",
      stitch_type: spec.type,
      round_index: 1,
      sequence_index: i,
      position,
      orientation: [0, 0, 0, 1],
      tangent,
      normal,
      binormal,
      scale: 1,
      loop_placement: spec.loop ?? "both",
      colour_id: "main",
      yarn_id: "main",
      parent_stitch_ids: spec.parents,
      is_increase: spec.increase ?? false,
      is_decrease: spec.decrease ?? false,
      source_reference: "visual-regression synthetic fixture",
    };
  });

  const edges: { edge_id: string; edge_type: string; source_id: string; target_id: string }[] = [];
  for (let i = 0; i < stitches.length - 1; i++) {
    edges.push({
      edge_id: `yarn-${i}`,
      edge_type: "yarn_sequence",
      source_id: stitches[i].stitch_id,
      target_id: stitches[i + 1].stitch_id,
    });
  }
  for (const stitch of stitches) {
    for (const parentId of stitch.parent_stitch_ids) {
      edges.push({
        edge_id: `insertion-${parentId}-${stitch.stitch_id}`,
        edge_type: "insertion",
        source_id: parentId,
        target_id: stitch.stitch_id,
      });
    }
  }

  return {
    schema_version: "0.1.0",
    pattern_fingerprint: null,
    graph_fingerprint: "visual-regression-graph-fp",
    geometry_fingerprint: "visual-regression-geometry-fp",
    units: "cm",
    gauge: { stitches_per_cm: 1.6, rounds_per_cm: 1.2, yarn_diameter_cm: 0.3 },
    stitches,
    yarn_segments: [],
    edges,
    bounds: {
      min: [-radius, -radius, -0.1] as [number, number, number],
      max: [radius, radius, 0.1] as [number, number, number],
    },
    measurements: {
      overall_height_cm: 0.2,
      max_radius_cm: radius,
      max_circumference_cm: 2 * Math.PI * radius,
    },
    warnings: [],
  };
}

interface AppTestHook {
  loadGeometryDocument(doc: unknown): Promise<void>;
  getStore(): { set(patch: Record<string, unknown>): void; get(): Record<string, unknown> };
}

async function loadFixtureAndStabilize(page: Page): Promise<void> {
  const doc = buildKitchenSinkFixture();
  await page.evaluate(
    async (d) => await (window as unknown as { __app: AppTestHook }).__app.loadGeometryDocument(d),
    doc,
  );
  await openPanelTab(page, "appearance");
  await page.selectOption("#quality-select", "low");
  await page.selectOption("#view-mode", "yarn");
  await page.evaluate(() => {
    const app = (window as unknown as { __app: { setViewPreset(p: string): void } }).__app;
    app.setViewPreset("front");
  });
  await page.waitForTimeout(300);
}

async function selectStitch(page: Page, stitchId: string): Promise<void> {
  await page.evaluate(
    (id) => (window as unknown as { __app: AppTestHook }).__app.getStore().set({ selectedStitchId: id }),
    stitchId,
  );
  await page.waitForTimeout(150);
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await skipOnboarding(page);
  await page.goto("/");
  await expect(page.locator("#viewport")).toBeVisible();
  // "#viewport" (the <canvas>) exists in the static HTML before any JS
  // runs — it is not proof that `main()`'s async default-fixture fetch and
  // `new App(...)` construction have finished and set `window.__app`.
  // Without this wait, loadFixtureAndStabilize's page.evaluate can race
  // that async startup and throw "Cannot read properties of undefined
  // (reading 'loadGeometryDocument')" — observed intermittently while
  // building this suite, not a hypothetical.
  await page.waitForFunction(() => Boolean((window as unknown as { __app?: unknown }).__app));
  await loadFixtureAndStabilize(page);
});

test.describe("visual regression: scientific viewer", () => {
  test("yarn mode overview (all stitch families)", async ({ page }) => {
    await expect(page.locator("#viewport")).toHaveScreenshot("yarn-overview.png", SCREENSHOT_OPTIONS);
  });

  test("structural mode overview", async ({ page }) => {
    await page.selectOption("#view-mode", "structural");
    await page.waitForTimeout(300);
    await expect(page.locator("#viewport")).toHaveScreenshot("structural-overview.png", SCREENSHOT_OPTIONS);
  });

  test("front-loop-only attachment, selected", async ({ page }) => {
    await selectStitch(page, "flo-7");
    await expect(page.locator("#viewport")).toHaveScreenshot("flo-attachment.png", SCREENSHOT_OPTIONS);
  });

  test("back-loop-only attachment, selected", async ({ page }) => {
    await selectStitch(page, "blo-8");
    await expect(page.locator("#viewport")).toHaveScreenshot("blo-attachment.png", SCREENSHOT_OPTIONS);
  });

  test("selected stitch with graph overlay", async ({ page }) => {
    await selectStitch(page, "inc-a-5");
    await openPanelTab(page, "analyse");
    await page.check("#graph-overlay-toggle");
    await page.waitForTimeout(300);
    await expect(page.locator("#viewport")).toHaveScreenshot("graph-overlay.png", SCREENSHOT_OPTIONS);
  });

  test("selected stitch in path-inspection mode, focused on the post role", async ({ page }) => {
    await selectStitch(page, "dc-4");
    await openPanelTab(page, "analyse");
    await page.check("#path-mode-toggle");
    await page.waitForTimeout(150);
    await page.selectOption("#path-role-select", "post");
    await page.waitForTimeout(300);
    await expect(page.locator("#viewport")).toHaveScreenshot("path-inspection-post-role.png", SCREENSHOT_OPTIONS);
  });

  test("X-ray mode", async ({ page }) => {
    await openPanelTab(page, "analyse");
    await page.check("#xray-toggle");
    await page.waitForTimeout(300);
    await expect(page.locator("#viewport")).toHaveScreenshot("xray-mode.png", SCREENSHOT_OPTIONS);
  });

  test("clipped model", async ({ page }) => {
    await openPanelTab(page, "analyse");
    await page.check("#clip-enabled");
    await page.selectOption("#clip-axis", "z");
    await page.waitForTimeout(300);
    await expect(page.locator("#viewport")).toHaveScreenshot("clipped.png", SCREENSHOT_OPTIONS);
  });

  test("point measurement recorded between two synthetic stitches", async ({ page }) => {
    await page.evaluate(() => {
      const win = window as unknown as {
        __app: {
          getDoc(): { stitches: { stitch_id: string; position: [number, number, number] }[] };
          getStore(): { set(patch: Record<string, unknown>): void };
        };
      };
      const doc = win.__app.getDoc();
      const a = doc.stitches.find((s) => s.stitch_id === "sc-2")!;
      const b = doc.stitches.find((s) => s.stitch_id === "dc-4")!;
      win.__app.getStore().set({
        measurements: [
          {
            id: "visual-regression-measurement",
            type: "point_distance",
            label: "Point-to-point distance",
            valueCm: Math.hypot(
              a.position[0] - b.position[0],
              a.position[1] - b.position[1],
              a.position[2] - b.position[2],
            ),
            unit: "cm",
            approximate: true,
            createdAtMs: 0,
            geometryFingerprint: "visual-regression-geometry-fp",
            pointA: a.position,
            pointB: b.position,
          },
        ],
      });
    });
    await page.waitForTimeout(300);
    await expect(page.locator("#viewport")).toHaveScreenshot("point-measurement.png", SCREENSHOT_OPTIONS);
  });
});

/**
 * Diagram-mode visual regression. Unlike the suite above, this one has no
 * shortcut equivalent to `loadGeometryDocument` — diagram analysis/topology
 * inference is server-side — so each test goes through the real backend
 * (the same `webServer`-managed uvicorn process every other e2e spec uses,
 * not a second one). The 2D-preview screenshots are inherently more stable
 * than the 3D ones above: `#diagram-preview` is a plain, fully
 * client-rendered SVG with no WebGL/anti-aliasing variance, so no
 * `maxDiffPixelRatio` slack is needed for those two.
 *
 * Bounded scope (see docs/svg-diagram-milestone-audit.md's
 * "Visual-regression baselines" section for the full reasoning): this
 * covers the 2D review view, a corrected-symbol state, and one
 * diagram-derived 3D render — not the full nine-scenario list from the
 * original ask. A dedicated "security-error state" screenshot was skipped
 * since that state has no distinct visual surface beyond the diagnostics
 * list diagram-workflow.spec.ts already asserts on by text.
 */
test.describe("visual regression: SVG diagram", () => {
  const RING_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
<g id="ring" data-stitch-type="magic_ring" transform="translate(200,200)"><circle r="8"/></g>
<g data-stitch-type="single_crochet" transform="translate(230,200)"></g>
<g data-stitch-type="single_crochet" transform="translate(215,226.02)"></g>
<g data-stitch-type="single_crochet" transform="translate(185,226.02)"></g>
<g data-stitch-type="single_crochet" transform="translate(170,200)"></g>
<g data-stitch-type="single_crochet" transform="translate(185,173.98)"></g>
<rect id="mystery" x="209" y="167.98" width="12" height="12"/>
</svg>`;

  async function analyseRing(page: Page): Promise<void> {
    await page.click('#input-mode-tabs button[data-mode="diagram"]');
    await page.fill("#diagram-source", RING_SVG);
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/visualizer/diagram/analyse") && r.request().method() === "POST",
        { timeout: 45_000 },
      ),
      page.click("#diagram-analyse-button"),
    ]);
    await expect(page.locator("#diagram-status")).toHaveText("Analysed.", { timeout: 45_000 });
  }

  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await skipOnboarding(page);
    await page.goto("/");
    await page.waitForFunction(() => Boolean((window as unknown as { __app?: unknown }).__app));
  });

  test("analysed flat-circle diagram, 2D review", async ({ page }) => {
    await analyseRing(page);
    await expect(page.locator("#diagram-preview")).toHaveScreenshot("diagram-2d-review.png", {
      timeout: 20_000,
    });
  });

  test("corrected ambiguous symbol shown with manual-correction colour", async ({ page }) => {
    await analyseRing(page);
    await page.locator("#diagram-symbol-list button", { hasText: "unclassified" }).click();
    await page.selectOption("#diagram-stitch-type-select", "single_crochet");
    await page.click("#diagram-apply-correction");
    await page.waitForTimeout(150);
    await expect(page.locator("#diagram-preview")).toHaveScreenshot("diagram-2d-corrected-symbol.png", {
      timeout: 20_000,
    });
  });

  test("diagram-derived 3D structural model, selected stitch", async ({ page }) => {
    await analyseRing(page);
    await page.locator("#diagram-symbol-list button", { hasText: "unclassified" }).click();
    await page.selectOption("#diagram-stitch-type-select", "single_crochet");
    await page.click("#diagram-apply-correction");
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/visualizer/diagram/compile") && r.request().method() === "POST",
        { timeout: 45_000 },
      ),
      page.click("#diagram-compile-button"),
    ]);
    await expect(page.locator("#diagram-status")).toHaveText("Compiled successfully.", { timeout: 45_000 });
    // Yarn is the default view now; this baseline is of the structural one.
    await openPanelTab(page, "appearance");
    await page.selectOption("#view-mode", "structural");
    await page.selectOption("#quality-select", "low");
    await page.evaluate(() => {
      const app = (window as unknown as { __app: { setViewPreset(p: string): void } }).__app;
      app.setViewPreset("front");
    });
    await page.evaluate(() => {
      const win = window as unknown as {
        __app: {
          getDoc(): { stitches: { stitch_id: string }[] };
          getStore(): { set(patch: Record<string, unknown>): void };
        };
      };
      const firstStitchId = win.__app.getDoc().stitches[0].stitch_id;
      win.__app.getStore().set({ selectedStitchId: firstStitchId });
    });
    await page.waitForTimeout(300);
    await expect(page.locator("#viewport")).toHaveScreenshot("diagram-3d-selected-stitch.png", SCREENSHOT_OPTIONS);
  });
});
