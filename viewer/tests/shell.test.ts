import { afterEach, describe, expect, it } from "vitest";
import {
  renderStatGrid,
  stitchHeadlineHtml,
  stitchTypeLabel,
  wireOnboarding,
  wirePanelTabs,
} from "../src/ui/shell";
import { makeTestGeometry } from "./fixtures";

afterEach(() => {
  document.body.innerHTML = "";
  window.localStorage.clear();
});

describe("renderStatGrid", () => {
  it("renders one tile per pair and escapes values", () => {
    const dl = document.createElement("dl");
    renderStatGrid(dl, [
      ["Stitches", "108"],
      ["Note", "<b>bold</b>"],
    ]);
    expect(dl.querySelectorAll(":scope > div")).toHaveLength(2);
    expect(dl.querySelector("b")).toBeNull();
    expect(dl.textContent).toContain("<b>bold</b>");
  });
});

describe("stitchTypeLabel", () => {
  it("spells out known abbreviations and falls back to the raw type", () => {
    expect(stitchTypeLabel("sc")).toBe("Single crochet");
    expect(stitchTypeLabel("half_double_crochet")).toBe("Half double crochet");
    expect(stitchTypeLabel("bobble_stitch")).toBe("bobble stitch");
  });
});

describe("stitchHeadlineHtml", () => {
  it("gives the position within the round, not across the whole piece", () => {
    const base = makeTestGeometry();
    const template = base.stitches[0];
    // sequence_index counts across the piece: round 1 holds 0-5, round 2 starts at 6.
    const stitches = [0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => ({
      ...template,
      stitch_id: `s${i}`,
      round_index: i < 6 ? 1 : 2,
      sequence_index: i,
    }));
    const doc = { ...base, stitches };
    expect(stitchHeadlineHtml(stitches[7], doc)).toContain("Round 2 · stitch 2");
  });

  it("badges increases", () => {
    const base = makeTestGeometry();
    const stitch = { ...base.stitches[0], is_increase: true };
    expect(stitchHeadlineHtml(stitch, { ...base, stitches: [stitch] })).toContain("Increase");
  });
});

function mountTabs(): void {
  document.body.innerHTML = `
    <nav id="panel-tabs">
      <button role="tab" id="t1" aria-controls="p1" aria-selected="true">One</button>
      <button role="tab" id="t2" aria-controls="p2" aria-selected="false">Two</button>
    </nav>
    <div id="p1"></div>
    <div id="p2" hidden></div>`;
  wirePanelTabs();
}

describe("wirePanelTabs", () => {
  it("shows only the clicked tab's panel", () => {
    mountTabs();
    document.getElementById("t2")!.click();
    expect(document.getElementById("p1")!.hidden).toBe(true);
    expect(document.getElementById("p2")!.hidden).toBe(false);
    expect(document.getElementById("t2")!.getAttribute("aria-selected")).toBe("true");
  });

  it("moves between tabs with the arrow keys", () => {
    mountTabs();
    document
      .getElementById("panel-tabs")!
      .dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    expect(document.getElementById("p2")!.hidden).toBe(false);
    expect(document.activeElement?.id).toBe("t2");
  });
});

describe("wireOnboarding", () => {
  const mount = (): void => {
    document.body.innerHTML = `
      <section id="onboarding"><button id="onboarding-dismiss">Got it</button></section>
      <button id="help-button">How it works</button>`;
    wireOnboarding();
  };

  it("shows on first visit and stays dismissed afterwards", () => {
    mount();
    expect(document.getElementById("onboarding")!.hidden).toBe(false);
    document.getElementById("onboarding-dismiss")!.click();
    expect(document.getElementById("onboarding")!.hidden).toBe(true);

    mount();
    expect(document.getElementById("onboarding")!.hidden).toBe(true);
  });

  it("can be reopened from the help button", () => {
    window.localStorage.setItem("crochet-visualiser:onboarding-dismissed", "1");
    mount();
    document.getElementById("help-button")!.click();
    expect(document.getElementById("onboarding")!.hidden).toBe(false);
  });
});
