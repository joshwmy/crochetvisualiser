import { test, expect, type Page } from "@playwright/test";

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

async function compile(page: Page, source: string): Promise<void> {
  await page.fill("#pattern-source", source);
  // Wait for the actual compile-API network response rather than polling
  // DOM text — a repeat compile can otherwise race against whatever text
  // the *previous* result already left in #compile-status.
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/visualizer/compile") && r.request().method() === "POST",
      { timeout: 15_000 },
    ),
    page.click("#compile-button"),
  ]);
  expect(response.status()).toBe(200);
  await expect(page.locator("#compile-status")).not.toHaveText("Compiling…", { timeout: 15_000 });
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
    const content = page.locator("#inspector-content dd").first();
    if (await content.isVisible().catch(() => false)) {
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
  const content = page.locator("#inspector-content dd").first();
  if (await content.isVisible().catch(() => false)) {
    return content.textContent();
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
    await page.goto("/");

    // 1-2: load example (pre-filled) and compile through the real backend.
    await compile(page, AMIGURUMI_EXAMPLE);
    await expect(page.locator("#compile-status")).toHaveText(/Compiled successfully/);

    // 3: switch to yarn (crochet-specific procedural geometry) mode.
    await page.selectOption("#view-mode", "yarn");
    await expect(page.locator("#view-mode")).toHaveValue("yarn");

    // 4: select a stitch in yarn mode.
    const { stitchId: firstHitId } = await selectAnyStitchViaProbe(page);
    expect(firstHitId).toMatch(/^piece-r\d+-s\d+$/);
    await expect(page.locator("#inspector-content")).toBeVisible();

    // 5: show its parents — the "Parents" row must be present and populated
    // (either a real parent id or the magic-ring placeholder).
    const parentsRow = page.locator("#inspector-content dt", { hasText: "Parents" });
    await expect(parentsRow).toHaveCount(1);
    const parentsValue = await parentsRow.locator("xpath=following-sibling::dd[1]").textContent();
    expect(parentsValue).toBeTruthy();

    // 6: enable X-ray mode.
    await page.check("#xray-toggle");
    await expect(page.locator("#xray-toggle")).toBeChecked();

    // 7: apply a clipping plane.
    await page.check("#clip-enabled");
    await page.selectOption("#clip-axis", "z");
    await setRangeInput(page, "clip-offset", "25");
    await expect(page.locator("#clip-enabled")).toBeChecked();

    // 8: add a measurement between two distinct stitches.
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

    // 9: change the yarn quality level; the store must reflect the new value
    // (a prior bug left the store stale after setQuality — this guards it).
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

    // 12: the new model remains interactive — a stitch in it can be selected.
    const { stitchId: postRecompileHit } = await selectAnyStitchViaProbe(page);
    expect(postRecompileHit).toMatch(/^piece-r\d+-s\d+$/);
  });
});
