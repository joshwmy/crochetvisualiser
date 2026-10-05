import { test, expect, type Page } from "@playwright/test";
import { openPanelTab, skipOnboarding } from "./helpers";

// Deliberately small (7 symbols) — this spec exercises the SVG-diagram
// workflow end to end through the real backend; a small fixture keeps the
// scene-build/raycast cost low, unlike compile-workflow.spec.ts's
// 1640-stitch reference fixture (see docs/known-limitations.md's
// "Verification caveat" for why this project keeps e2e fixtures modest).
const MAGIC_RING_6SC = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
<g id="ring" data-stitch-type="magic_ring" transform="translate(200,200)"><circle r="8"/></g>
<g data-stitch-type="single_crochet" transform="translate(230,200)"></g>
<g data-stitch-type="single_crochet" transform="translate(215,226.02)"></g>
<g data-stitch-type="single_crochet" transform="translate(185,226.02)"></g>
<g data-stitch-type="single_crochet" transform="translate(170,200)"></g>
<g data-stitch-type="single_crochet" transform="translate(185,173.98)"></g>
<g id="mystery" data-stitch-type="single_crochet" transform="translate(215,173.98)"></g>
</svg>`;

const AMBIGUOUS_MAGIC_RING_6SC = MAGIC_RING_6SC.replace(
  '<g id="mystery" data-stitch-type="single_crochet" transform="translate(215,173.98)"></g>',
  '<rect id="mystery" x="209" y="167.98" width="12" height="12"/>',
);

const MALICIOUS_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script></svg>`;

// 45s, not 15s: this dev machine (see docs/known-limitations.md) has been
// observed with well under 1GB free physical memory even at idle, and a
// real backend analyse/compile round trip under that pressure has been
// observed to exceed 15s — not a hang, just genuinely slow under memory
// pressure. No deterministic readiness signal shortens this: the wait is
// for the response itself.
const BACKEND_ROUND_TRIP_TIMEOUT = 45_000;

async function switchToDiagramMode(page: Page): Promise<void> {
  await page.click('#input-mode-tabs button[data-mode="diagram"]');
  await expect(page.locator("#diagram-panel")).toBeVisible();
}

async function analyse(page: Page, svgSource: string): Promise<void> {
  await page.fill("#diagram-source", svgSource);
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/visualizer/diagram/analyse") && r.request().method() === "POST",
      { timeout: BACKEND_ROUND_TRIP_TIMEOUT },
    ),
    page.click("#diagram-analyse-button"),
  ]);
  expect(response.status()).toBe(200);
  await expect(page.locator("#diagram-status")).toHaveText("Analysed.", { timeout: BACKEND_ROUND_TRIP_TIMEOUT });
}

test.describe("SVG diagram ingestion workflow", () => {
  test("analyse, correct an unresolved symbol, compile to 3D, select a stitch", async ({ page }) => {
    await skipOnboarding(page);
    await page.goto("/");
    await switchToDiagramMode(page);

    // 1: analyse a chart with one unclassified symbol ("mystery" rect).
    await analyse(page, AMBIGUOUS_MAGIC_RING_6SC);
    await expect(page.locator("#diagram-summary dd").nth(5)).toHaveText(/No/); // "Ready to compile"
    await expect(page.locator("#diagram-diagnostics-list li[data-severity='error']")).toHaveCount(1);

    // 2: select the unresolved symbol via the symbol list and correct it.
    await page.locator("#diagram-symbol-list button", { hasText: "unclassified" }).click();
    await expect(page.locator("#diagram-correction-panel")).toBeVisible();
    await page.selectOption("#diagram-stitch-type-select", "single_crochet");
    await page.click("#diagram-apply-correction");

    // 3: compile to 3D through the real backend — must load into the
    // existing Three.js viewer via the same App.loadGeometryDocument path
    // the written-pattern workflow uses.
    const [compileResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/visualizer/diagram/compile") && r.request().method() === "POST",
        { timeout: BACKEND_ROUND_TRIP_TIMEOUT },
      ),
      page.click("#diagram-compile-button"),
    ]);
    expect(compileResponse.status()).toBe(200);
    await expect(page.locator("#diagram-status")).toHaveText("Compiled successfully.", { timeout: BACKEND_ROUND_TRIP_TIMEOUT });

    const stitchCount = await page.evaluate(
      () => (window as unknown as { __app: { getDoc(): { stitches: unknown[] } } }).__app.getDoc().stitches.length,
    );
    expect(stitchCount).toBe(6);

    // 4: switch to yarn mode and select a stitch — exercises the
    // structural hit-proxy picking path (selection/hit_proxies.ts) on a
    // diagram-derived model.
    await openPanelTab(page, "appearance");
    await page.selectOption("#view-mode", "yarn");
    const canvas = page.locator("#viewport");
    const box = (await canvas.boundingBox())!;
    let selectedId: string | null = null;
    for (const [dx, dy] of [[0, 0], [20, 0], [-20, 0], [0, 20], [0, -20], [30, 30], [-30, -30]]) {
      await canvas.click({ position: { x: box.width / 2 + dx, y: box.height / 2 + dy } });
      selectedId = await page.evaluate(
        () =>
          (window as unknown as { __app: { getStore(): { get(): { selectedStitchId: string | null } } } }).__app
            .getStore()
            .get().selectedStitchId,
      );
      if (selectedId) break;
    }
    expect(selectedId).toMatch(/^piece-r\d+-s\d+$/);

    // 5: return to 2D review — corrections/document must survive the round-trip.
    await page.click("#diagram-return-to-review-button");
    await expect(page.locator("#diagram-preview-section")).toBeVisible();
  });

  test("malicious SVG is rejected and does not disturb a previously loaded valid model", async ({ page }) => {
    await skipOnboarding(page);
    await page.goto("/");
    await switchToDiagramMode(page);

    // Load a valid diagram-derived model first.
    await analyse(page, MAGIC_RING_6SC);
    const [compileResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/visualizer/diagram/compile") && r.request().method() === "POST",
        { timeout: BACKEND_ROUND_TRIP_TIMEOUT },
      ),
      page.click("#diagram-compile-button"),
    ]);
    expect(compileResponse.status()).toBe(200);
    await expect(page.locator("#diagram-status")).toHaveText("Compiled successfully.", { timeout: BACKEND_ROUND_TRIP_TIMEOUT });

    const beforeCount = await page.evaluate(
      () => (window as unknown as { __app: { getDoc(): { stitches: unknown[] } } }).__app.getDoc().stitches.length,
    );
    expect(beforeCount).toBe(6);

    // Submit malicious content — must be rejected with a structured
    // diagnostic, and the page must never have executed the script (no
    // dialog/alert was ever triggered — Playwright would hang waiting for
    // one to be dismissed if it had).
    await page.fill("#diagram-source", MALICIOUS_SVG);
    const [analyseResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/visualizer/diagram/analyse") && r.request().method() === "POST",
        { timeout: BACKEND_ROUND_TRIP_TIMEOUT },
      ),
      page.click("#diagram-analyse-button"),
    ]);
    const body = await analyseResponse.json();
    expect(body.success).toBe(false);
    expect(body.diagnostics[0].code).toBe("UNSAFE_SVG_CONTENT");

    // The previously loaded valid model must be completely untouched.
    const afterCount = await page.evaluate(
      () => (window as unknown as { __app: { getDoc(): { stitches: unknown[] } } }).__app.getDoc().stitches.length,
    );
    expect(afterCount).toBe(6);
  });

  test("written-pattern workflow is unaffected by the diagram mode addition", async ({ page }) => {
    await skipOnboarding(page);
    await page.goto("/");
    // Default mode on load must still be the written-pattern panel.
    await expect(page.locator("#written-pattern-panel")).toBeVisible();
    await expect(page.locator("#diagram-panel")).toBeHidden();
  });
});
