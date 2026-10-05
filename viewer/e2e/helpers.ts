import type { Page } from "@playwright/test";

/** Right-panel tabs (index.html's #panel-tabs). Controls inside a tab are
 * hidden until it is open, and Playwright will not act on hidden controls. */
export type PanelTab = "overview" | "appearance" | "analyse" | "measure";

export async function openPanelTab(page: Page, tab: PanelTab): Promise<void> {
  await page.click(`#tab-btn-${tab}`);
}

/** Marks the first-run welcome card as already dismissed, so it never
 * covers the canvas a spec is about to click. Call before page.goto. */
export async function skipOnboarding(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem("crochet-visualiser:onboarding-dismissed", "1");
    } catch {
      // Storage unavailable: the card shows, and a click on it would fail loudly.
    }
  });
}

/** True when a stitch is selected. The full detail list (#inspector-content)
 * lives in a collapsed <details>, so its visibility no longer says anything;
 * main.ts toggles its `hidden` attribute exactly when selection changes. */
export async function hasSelection(page: Page): Promise<boolean> {
  return (await page.locator("#inspector-content").getAttribute("hidden")) === null;
}
