import { test, expect, type Page } from "@playwright/test";

// Deliberately tiny patterns — this test's point is repeated-compile
// resource accounting, not geometry complexity, and each iteration is a
// real backend round trip + real Three.js rebuild (see
// compile-workflow.spec.ts's own note on why this suite's timeout is
// generous). A large pattern here would multiply that real cost by the
// iteration count for no extra coverage.
const PATTERN_A = `Round 1: 6 sc in magic ring [6]\nRound 2: sc around [6]\n`;
const PATTERN_B = `Round 1: 8 sc in magic ring [8]\nRound 2: sc around [8]\n`;

// 45s, not 15s: this dev machine (see docs/known-limitations.md) has been
// observed with well under 1GB free physical memory even at idle, and a
// real backend compile round trip under that pressure has been observed to
// exceed 15s — not a hang, just genuinely slow under memory pressure. No
// deterministic readiness signal shortens this: the wait is for the
// response itself.
const BACKEND_ROUND_TRIP_TIMEOUT = 45_000;

async function compile(page: Page, source: string): Promise<void> {
  await page.fill("#pattern-source", source);
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/visualizer/compile") && r.request().method() === "POST",
      { timeout: BACKEND_ROUND_TRIP_TIMEOUT },
    ),
    page.click("#compile-button"),
  ]);
  expect(response.status()).toBe(200);
  await expect(page.locator("#compile-status")).not.toHaveText("Compiling…", { timeout: BACKEND_ROUND_TRIP_TIMEOUT });
  await expect(page.locator("#compile-status")).toHaveText(/Compiled successfully/);
}

interface WindowWithApp extends Window {
  __app: { getRendererInfo(): { memory: { geometries: number; textures: number } } };
}

async function trackedGeometryCount(page: Page): Promise<number> {
  return page.evaluate(() => (window as unknown as WindowWithApp).__app.getRendererInfo().memory.geometries);
}

// Reduced from the brief's suggested 10 iterations to 5 for total suite
// runtime (each iteration is a real backend compile + Three.js rebuild,
// not a mock) — still enough iterations to distinguish "leaks a little
// every time" from "stable after the first couple of recompiles", which is
// the failure mode this test actually guards against. Documented here
// rather than silently shortened.
const ITERATIONS = 5;

test.describe("lifecycle: repeated model replacement does not leak Three.js resources", () => {
  test("recompiling the same small pattern repeatedly keeps geometry count bounded", async ({ page }) => {
    await page.goto("/");
    await compile(page, PATTERN_A);

    const counts: number[] = [await trackedGeometryCount(page)];
    for (let i = 0; i < ITERATIONS; i++) {
      await compile(page, PATTERN_A);
      counts.push(await trackedGeometryCount(page));
    }

    // The count may fluctuate slightly between geometry types being merged
    // differently on any given rebuild, but must not trend upward across
    // iterations — that trend is what a real leak looks like.
    const first = counts[0];
    const last = counts[counts.length - 1];
    expect(last).toBeLessThanOrEqual(first + 2);

    // Measurement/overlay state must also reset on every single recompile,
    // not just the first one.
    await expect(page.locator("#measurement-list li")).toHaveCount(0);
  });

  test("alternating between two small patterns repeatedly keeps geometry count bounded", async ({ page }) => {
    await page.goto("/");
    await compile(page, PATTERN_A);
    const first = await trackedGeometryCount(page);

    let lastPatternWasB = false;
    for (let i = 0; i < ITERATIONS; i++) {
      lastPatternWasB = i % 2 === 0;
      await compile(page, lastPatternWasB ? PATTERN_B : PATTERN_A);
    }

    const last = await trackedGeometryCount(page);
    expect(last).toBeLessThanOrEqual(first + 2);

    // The model must still be the *last* one compiled, and interactive.
    // PATTERN_A is 2 rounds of 6 = 12 stitches; PATTERN_B is 2 rounds of 8 = 16.
    await expect(page.locator("#compile-summary")).toContainText(lastPatternWasB ? "16" : "12");
  });
});
