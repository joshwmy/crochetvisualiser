import { test, expect, type Page } from "@playwright/test";
import { hasSelection, openPanelTab, skipOnboarding } from "./helpers";

const AMIGURUMI_EXAMPLE = `Round 1: 6 sc in magic ring [6]
Round 2: inc in each stitch around [12]
Round 3: (sc, inc) repeat 6 times [18]
Rounds 4-6: sc around [18]
Round 7: (sc, dec) repeat 6 times [12]
Round 8: dec around [6]
`;

const SECOND_VALID_PATTERN = `Round 1: 8 sc in magic ring [8]
Round 2: sc around [8]
Round 3: sc around [8]
`;

const INVALID_PATTERN = `Round 1: 6 sc in magic ring [6]
Round 2: inc around [999]
`;

// 45s, not 15s: this dev machine (see docs/known-limitations.md) has been
// observed with well under 1GB free physical memory even at idle, and a
// real backend compile round trip under that pressure has been observed to
// exceed 15s — not a hang, just genuinely slow under memory pressure. No
// deterministic readiness signal shortens this: the wait is for the
// response itself.
const BACKEND_ROUND_TRIP_TIMEOUT = 45_000;

async function compile(page: Page, source: string): Promise<void> {
  await page.fill("#pattern-source", source);
  // Wait for the actual compile-API network response rather than polling
  // DOM text — a repeat compile can otherwise race against whatever text
  // the *previous* result already left in #compile-status.
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/visualizer/compile") && r.request().method() === "POST",
      { timeout: BACKEND_ROUND_TRIP_TIMEOUT },
    ),
    page.click("#compile-button"),
  ]);
  expect(response.status()).toBe(200);
  await expect(page.locator("#compile-status")).not.toHaveText("Compiling…", { timeout: BACKEND_ROUND_TRIP_TIMEOUT });
}

/** Stitches don't cover every pixel, so probe a small grid near the canvas
 * center until one click actually hits an instanced stitch mesh. */
async function selectAnyStitch(page: Page): Promise<string> {
  const canvas = page.locator("#viewport");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("canvas has no bounding box");

  const offsets = [
    [0, 0],
    [20, 0],
    [-20, 0],
    [0, 20],
    [0, -20],
    [30, 30],
    [-30, -30],
    [40, 0],
    [-40, 0],
  ];
  for (const [dx, dy] of offsets) {
    await canvas.click({ position: { x: box.width / 2 + dx, y: box.height / 2 + dy } });
    if (await hasSelection(page)) {
      const stitchId = await page.locator("#inspector-content dd").first().textContent();
      if (stitchId) return stitchId;
    }
  }
  throw new Error("no stitch was hit after probing the canvas");
}

interface WindowWithApp extends Window {
  __app: { getRendererInfo(): { memory: { geometries: number; textures: number } } };
}

/** Three.js's own live resource count — proves disposal actually ran,
 * rather than just trusting the disposal code by inspection. */
async function trackedGeometryCount(page: Page): Promise<number> {
  return page.evaluate(() => (window as unknown as WindowWithApp).__app.getRendererInfo().memory.geometries);
}

const PROBE_OFFSETS: Array<[number, number]> = [
  [0, 0],
  [20, 0],
  [-20, 0],
  [0, 20],
  [0, -20],
  [30, 30],
  [-30, -30],
  [40, 0],
  [-40, 0],
  [0, 40],
  [0, -40],
  [50, 50],
];

async function clickCanvasAt(page: Page, dx: number, dy: number): Promise<string | null> {
  const canvas = page.locator("#viewport");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("canvas has no bounding box");
  await canvas.click({ position: { x: box.width / 2 + dx, y: box.height / 2 + dy } });
  if (await hasSelection(page)) {
    return page.locator("#inspector-content dd").first().textContent();
  }
  return null;
}

/** Clicks the canvas at successive probe offsets, one click at a time
 * (works in both structural and yarn view modes — yarn tubes are thinner
 * and cover less of the canvas than instanced stitch meshes, so more
 * offsets are tried here than in selectAnyStitch), stopping at the first
 * hit. One click per offset is important for the measurement flow: probing
 * all offsets before checking state would fire several pending/complete
 * measurement cycles before the caller ever gets a chance to look. Returns
 * the hit stitch id and the offset index to resume from on a later call. */
async function selectAnyStitchViaProbe(
  page: Page,
  skipOffsets = 0,
): Promise<{ stitchId: string; nextSkip: number }> {
  for (let i = skipOffsets; i < PROBE_OFFSETS.length; i++) {
    const [dx, dy] = PROBE_OFFSETS[i];
    const hit = await clickCanvasAt(page, dx, dy);
    if (hit) return { stitchId: hit, nextSkip: i + 1 };
  }
  throw new Error("no stitch was hit after probing the canvas");
}

async function setRangeInput(page: Page, id: string, value: string): Promise<void> {
  await page.locator(`#${id}`).evaluate((el, v) => {
    const input = el as HTMLInputElement;
    input.value = v;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

test.describe("written pattern compile workflow", () => {
  test("compile, select, recompile, and reject invalid input", async ({ page }) => {
    await skipOnboarding(page);
    await page.goto("/");

    // 1-2: start with viewer, paste example.
    await expect(page.locator("#pattern-source")).toBeVisible();

    // 3-4: compile through backend, confirm summary.
    await compile(page, AMIGURUMI_EXAMPLE);
    await expect(page.locator("#compile-status")).toHaveText(/Compiled successfully/);
    await expect(page.locator("#compile-summary")).toContainText("108"); // stitchCount
    await expect(page.locator("#compile-summary")).toContainText("8"); // sectionCount

    // 5: canvas has a loaded model — info panel reflects the new fingerprint.
    await expect(page.locator("#info")).toContainText("Geometry fingerprint");

    // 6-7: select a stitch, verify it belongs to the newly compiled pattern.
    const firstStitchId = await selectAnyStitch(page);
    expect(firstStitchId).toMatch(/^piece-r\d+-s\d+$/);

    // 8-9: compile a second valid pattern; the first model must be replaced,
    // not duplicated (checked via the summary changing, via re-selecting a
    // stitch that must belong to the *new* pattern, and via Three.js's own
    // resource count not accumulating stale geometry from the first model).
    const geometryCountBeforeSecondCompile = await trackedGeometryCount(page);
    await compile(page, SECOND_VALID_PATTERN);
    await expect(page.locator("#compile-status")).toHaveText(/Compiled successfully/);
    await expect(page.locator("#compile-summary")).toContainText("24"); // 8+8+8 stitches

    const geometryCountAfterSecondCompile = await trackedGeometryCount(page);
    expect(geometryCountAfterSecondCompile).toBeLessThanOrEqual(geometryCountBeforeSecondCompile);

    const secondStitchId = await selectAnyStitch(page);
    expect(secondStitchId).toMatch(/^piece-r\d+-s\d+$/);

    // 10-11: submit an invalid pattern; diagnostics appear and the second
    // valid model remains visible (summary must not clear/change to the
    // invalid attempt's absence of a summary).
    const summaryBeforeInvalid = await page.locator("#compile-summary").textContent();
    await compile(page, INVALID_PATTERN);
    await expect(page.locator("#compile-status")).toHaveText(/could not be compiled/);
    await expect(page.locator("#diagnostics-list li")).toHaveCount(1, { timeout: 5000 });
    await expect(page.locator("#diagnostics-list")).toContainText("declares 999 stitches");

    // The last *successful* summary must still be the second pattern's —
    // the failed compile must not have touched the live model.
    const summaryAfterInvalid = await page.locator("#compile-summary").textContent();
    expect(summaryAfterInvalid).toBe(summaryBeforeInvalid);

    const stillSelectable = await selectAnyStitch(page);
    expect(stillSelectable).toMatch(/^piece-r\d+-s\d+$/);
  });
});

test.describe("scientific viewer: yarn mode, x-ray, clipping, measurement, quality", () => {
  test("full crochet-specific inspection workflow across a recompile", async ({ page }) => {
    await skipOnboarding(page);
    await page.goto("/");

    // 1-2: load example (pre-filled) and compile through the real backend.
    await compile(page, AMIGURUMI_EXAMPLE);
    await expect(page.locator("#compile-status")).toHaveText(/Compiled successfully/);

    // 3: switch to yarn (crochet-specific procedural geometry) mode.
    await openPanelTab(page, "appearance");
    await page.selectOption("#view-mode", "yarn");
    await expect(page.locator("#view-mode")).toHaveValue("yarn");

    // 3b: enable path mode *before* selecting anything — the role picker
    // must not offer a real role with nothing selected to inspect.
    await openPanelTab(page, "analyse");
    await page.check("#path-mode-toggle");
    await expect(page.locator("#path-role-select")).toBeDisabled();
    await expect(page.locator("#path-role-select option")).toHaveCount(1);

    // 4: select a stitch in yarn mode.
    const { stitchId: firstHitId } = await selectAnyStitchViaProbe(page);
    expect(firstHitId).toMatch(/^piece-r\d+-s\d+$/);
    // The full detail list is folded into "All stitch details"; the headline
    // is what shows a stitch is selected.
    await expect(page.locator("#inspector-headline")).toBeVisible();

    // 5: show its parents — the "Parents" row must be present and populated
    // (either a real parent id or the magic-ring placeholder).
    const parentsRow = page.locator("#inspector-content dt", { hasText: "Parents" });
    await expect(parentsRow).toHaveCount(1);
    const parentsValue = await parentsRow.locator("xpath=following-sibling::dd[1]").textContent();
    expect(parentsValue).toBeTruthy();

    // 5b: with a stitch now selected, the role picker enables and populates;
    // pick a role, confirm the inspector's "Path role in focus" row
    // reflects it as text (not colour-only), then clear the focus.
    await expect(page.locator("#path-role-select")).toBeEnabled();
    const roleOptionCount = await page.locator("#path-role-select option").count();
    expect(roleOptionCount).toBeGreaterThan(1); // "All roles" + at least one real role
    const firstRealRole = await page.locator("#path-role-select option").nth(1).getAttribute("value");
    expect(firstRealRole).toBeTruthy();
    await page.selectOption("#path-role-select", firstRealRole!);
    const focusRow = page.locator("#inspector-content dt", { hasText: "Path role in focus" });
    await expect(focusRow).toHaveCount(1);
    await expect(focusRow.locator("xpath=following-sibling::dd[1]")).toHaveText(firstRealRole!);

    await page.click("#path-clear-focus");
    await expect(focusRow.locator("xpath=following-sibling::dd[1]")).toHaveText("(all roles highlighted)");
    // Deliberately left checked here — step 11b below confirms a recompile
    // resets it, rather than this test resetting it manually first.

    // 6: enable X-ray mode.
    await page.check("#xray-toggle");
    await expect(page.locator("#xray-toggle")).toBeChecked();

    // 7: apply a clipping plane — via the slider, confirming the numeric
    // input mirrors it, then via the numeric input directly, then reset.
    await page.check("#clip-enabled");
    await page.selectOption("#clip-axis", "z");
    await setRangeInput(page, "clip-offset", "25");
    await expect(page.locator("#clip-enabled")).toBeChecked();
    await expect(page.locator("#clip-offset-number")).toHaveValue("25");

    await page.fill("#clip-offset-number", "-40");
    await page.locator("#clip-offset-number").dispatchEvent("input");
    await expect(page.locator("#clip-offset")).toHaveValue("-40");

    await page.click("#clip-reset");
    await expect(page.locator("#clip-enabled")).not.toBeChecked();
    await expect(page.locator("#clip-offset")).toHaveValue("0");
    await expect(page.locator("#clip-offset-number")).toHaveValue("0");

    // 7b: re-enable clipping and the graph overlay together, then verify
    // the documented policy via the test-only debug hook: graph overlay
    // and measurement lines are clipped like real geometry, but the
    // selection marker is deliberately exempt (see App.applyClipping).
    await page.check("#clip-enabled");
    await page.check("#graph-overlay-toggle");
    await expect(page.locator("#graph-overlay-legend")).toBeVisible();
    const clippingDebug = await page.evaluate(
      () =>
        (
          window as unknown as {
            __app: {
              getClippingDebugInfo(): { graphOverlayClipped: boolean | null; selectionMarkerClipped: boolean };
            };
          }
        ).__app.getClippingDebugInfo(),
    );
    expect(clippingDebug.graphOverlayClipped).toBe(true);
    expect(clippingDebug.selectionMarkerClipped).toBe(false);

    // 8: add a measurement between two distinct stitches.
    await openPanelTab(page, "measure");
    await page.check("#measurement-mode-toggle");
    await expect(page.locator("#measurement-status")).toHaveText(/Click a stitch/);
    let skip = 0;
    for (let attempt = 0; attempt < PROBE_OFFSETS.length; attempt++) {
      const result = await selectAnyStitchViaProbe(page, skip);
      skip = result.nextSkip;
      if ((await page.locator("#measurement-list li").count()) > 0) break;
    }
    await expect(page.locator("#measurement-list li")).toHaveCount(1, { timeout: 5000 });
    await expect(page.locator("#measurement-list li").first()).toContainText("cm (approx.)");
    await page.uncheck("#measurement-mode-toggle");

    // 8b: object width, object height, and round circumference (the
    // currently selected stitch's round) — each a one-click measurement,
    // not a click-two-points flow.
    await page.click("#measure-width");
    await page.click("#measure-height");
    await expect(page.locator("#measurement-list li")).toHaveCount(3);
    await expect(page.locator("#measurement-list li").nth(1)).toContainText("Object width");
    await expect(page.locator("#measurement-list li").nth(2)).toContainText("Object height");

    await expect(page.locator("#measure-round-circumference")).toBeEnabled(); // a stitch is selected from step 8's clicks
    await page.click("#measure-round-circumference");
    await expect(page.locator("#measurement-list li")).toHaveCount(4);
    await expect(page.locator("#measurement-list li").nth(3)).toContainText("circumference");

    // 8c: arbitrary point-to-point measurement (not snapped to a stitch) —
    // clicks a raw raycast hit point, so success is judged by the
    // measurement list growing, not by the inspector (which point-mode
    // clicks never touch).
    await page.selectOption("#measurement-kind-select", "point");
    await page.check("#measurement-mode-toggle");
    await expect(page.locator("#measurement-status")).toHaveText(/Click a point/);
    const canvas = page.locator("#viewport");
    const canvasBox = (await canvas.boundingBox())!;
    for (const [dx, dy] of PROBE_OFFSETS) {
      await canvas.click({ position: { x: canvasBox.width / 2 + dx, y: canvasBox.height / 2 + dy } });
      if ((await page.locator("#measurement-list li").count()) === 5) break;
    }
    await expect(page.locator("#measurement-list li")).toHaveCount(5, { timeout: 5000 });
    await expect(page.locator("#measurement-list li").nth(4)).toContainText("Point-to-point");
    await page.uncheck("#measurement-mode-toggle");
    await page.selectOption("#measurement-kind-select", "stitch");

    // 9: change the yarn quality level; the store must reflect the new value
    // (a prior bug left the store stale after setQuality — this guards it).
    await openPanelTab(page, "appearance");
    await page.selectOption("#quality-select", "low");
    const qualityAfterChange = await page.evaluate(
      () => (window as unknown as { __app: { getStore(): { get(): { quality: string } } } }).__app.getStore().get()
        .quality,
    );
    expect(qualityAfterChange).toBe("low");

    // 10: compile a second, different pattern.
    const geometryCountBeforeSecondCompile = await trackedGeometryCount(page);
    await compile(page, SECOND_VALID_PATTERN);
    await expect(page.locator("#compile-status")).toHaveText(/Compiled successfully/);

    // 11: old geometry and measurement state must be disposed, not accumulated.
    const geometryCountAfterSecondCompile = await trackedGeometryCount(page);
    expect(geometryCountAfterSecondCompile).toBeLessThanOrEqual(geometryCountBeforeSecondCompile);
    await expect(page.locator("#measurement-list li")).toHaveCount(0);

    // 11b: path-inspection mode must also reset — an old role focus (or the
    // mode itself) referencing the previous model's data must not survive.
    await expect(page.locator("#path-mode-toggle")).not.toBeChecked();

    // 11c: clipping (left enabled since step 7b) must also reset, and the
    // DOM controls must visibly reflect that reset, not just internal state.
    await expect(page.locator("#clip-enabled")).not.toBeChecked();
    await expect(page.locator("#clip-offset")).toHaveValue("0");

    // 12: the new model remains interactive — a stitch in it can be selected.
    const { stitchId: postRecompileHit } = await selectAnyStitchViaProbe(page);
    expect(postRecompileHit).toMatch(/^piece-r\d+-s\d+$/);
  });
});
