import type { App } from "../app/App";
import type { GeometryDocument, StitchGeometry } from "../types/geometry";
import {
  DEFAULT_YARN_COLOUR,
  YARN_COLOURS,
  yarnColourHex,
  type YarnColourId,
} from "../materials/yarn_material";

/**
 * The page "shell": progressive-disclosure UI around the viewer — right-panel
 * tabs, first-run onboarding, the stage hint, yarn appearance controls, and
 * plain-language summaries. Kept out of main.ts, which owns the workflow
 * wiring, so each stays a readable size.
 */

const ONBOARDING_KEY = "crochet-visualiser:onboarding-dismissed";

function byId<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element #${id}`);
  return el as T;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Renders label/value pairs as stat tiles. Each pair is wrapped in a div
 * (valid inside <dl>) so CSS can lay them out as a grid of cards. */
export function renderStatGrid(el: HTMLElement, rows: [string, string][]): void {
  el.innerHTML = rows
    .map(([k, v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`)
    .join("");
}

/** WAI-ARIA tabs for the right panel: click or arrow keys switch panels. */
export function wirePanelTabs(): void {
  const tablist = byId<HTMLElement>("panel-tabs");
  const tabs = [...tablist.querySelectorAll<HTMLButtonElement>("[role=tab]")];

  const select = (tab: HTMLButtonElement, focus: boolean): void => {
    for (const other of tabs) {
      const selected = other === tab;
      other.setAttribute("aria-selected", String(selected));
      other.tabIndex = selected ? 0 : -1;
      const panelId = other.getAttribute("aria-controls");
      if (panelId) byId<HTMLElement>(panelId).hidden = !selected;
    }
    if (focus) tab.focus();
  };

  tablist.addEventListener("click", (event) => {
    const tab = (event.target as HTMLElement).closest<HTMLButtonElement>("[role=tab]");
    if (tab) select(tab, false);
  });

  tablist.addEventListener("keydown", (event) => {
    const current = tabs.findIndex((t) => t.getAttribute("aria-selected") === "true");
    let next = -1;
    if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    event.preventDefault();
    select(tabs[next], true);
  });
}

function readDismissed(): boolean {
  try {
    return window.localStorage.getItem(ONBOARDING_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDismissed(): void {
  try {
    window.localStorage.setItem(ONBOARDING_KEY, "1");
  } catch {
    // Private mode or blocked storage: the card just shows again next visit.
  }
}

/** First-visit "how it works" card. Dismissal is remembered; the header's
 * "How it works" button brings it back. */
export function wireOnboarding(): void {
  const card = byId<HTMLElement>("onboarding");
  const dismiss = byId<HTMLButtonElement>("onboarding-dismiss");
  const help = byId<HTMLButtonElement>("help-button");

  card.hidden = readDismissed();
  dismiss.addEventListener("click", () => {
    card.hidden = true;
    writeDismissed();
    help.focus();
  });
  help.addEventListener("click", () => {
    card.hidden = !card.hidden;
    if (!card.hidden) dismiss.focus();
  });
}

/** Fades the "drag to rotate" chip once the user has interacted with the model. */
export function wireStageHint(canvas: HTMLCanvasElement): void {
  const hint = byId<HTMLElement>("stage-hint");
  const fade = (): void => {
    hint.dataset.faded = "true";
  };
  canvas.addEventListener("pointerdown", fade, { once: true });
  canvas.addEventListener("wheel", fade, { once: true, passive: true });
}

function toCssHex(hex: number): string {
  return `#${hex.toString(16).padStart(6, "0")}`;
}

/** Yarn colour swatches, shaping highlight and helper-grid toggles (Look tab). */
export function wireYarnAppearance(app: App): void {
  const swatches = byId<HTMLDivElement>("yarn-colour-swatches");
  const highlight = byId<HTMLInputElement>("highlight-shaping-toggle");
  const legend = byId<HTMLUListElement>("shaping-legend");
  const helpers = byId<HTMLInputElement>("helpers-toggle");

  let selected: YarnColourId = DEFAULT_YARN_COLOUR;
  const render = (): void => {
    swatches.innerHTML = YARN_COLOURS.map(
      (c) =>
        `<button type="button" role="radio" data-colour="${c.id}" aria-checked="${c.id === selected}" ` +
        `tabindex="${c.id === selected ? 0 : -1}" title="${c.label}" aria-label="${c.label}" ` +
        `style="background:${toCssHex(c.hex)}"></button>`,
    ).join("");
  };
  render();

  const choose = (id: YarnColourId): void => {
    selected = id;
    app.setYarnPalette({ main: yarnColourHex(id) });
    render();
    swatches.querySelector<HTMLButtonElement>(`[data-colour="${id}"]`)?.focus();
  };

  swatches.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-colour]");
    if (button) choose(button.dataset.colour as YarnColourId);
  });
  swatches.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const index = YARN_COLOURS.findIndex((c) => c.id === selected);
    const step = event.key === "ArrowRight" ? 1 : -1;
    choose(YARN_COLOURS[(index + step + YARN_COLOURS.length) % YARN_COLOURS.length].id);
  });

  highlight.checked = app.getYarnPalette().highlightShaping;
  legend.hidden = !highlight.checked;
  highlight.addEventListener("change", () => {
    app.setYarnPalette({ highlightShaping: highlight.checked });
    legend.hidden = !highlight.checked;
  });

  helpers.addEventListener("change", () => app.setHelpersVisible(helpers.checked));
}

/** Plain-language numbers about the loaded piece (Overview tab). */
export function renderPieceStats(doc: GeometryDocument): void {
  const rounds = new Set(doc.stitches.map((s) => `${s.component_id}:${s.round_index}`)).size;
  const parts = new Set(doc.stitches.map((s) => s.component_id)).size;
  const rows: [string, string][] = [
    ["Stitches", String(doc.stitches.length)],
    ["Rounds", String(rounds)],
    ["Height", `${doc.measurements.overall_height_cm.toFixed(1)} cm`],
    ["Width", `${(doc.measurements.max_radius_cm * 2).toFixed(1)} cm`],
  ];
  if (parts > 1) rows.push(["Parts", String(parts)]);
  renderStatGrid(byId<HTMLDListElement>("piece-stats"), rows);
}

const STITCH_TYPE_LABELS: Record<string, string> = {
  sc: "Single crochet",
  single_crochet: "Single crochet",
  hdc: "Half double crochet",
  half_double_crochet: "Half double crochet",
  dc: "Double crochet",
  double_crochet: "Double crochet",
  tr: "Treble crochet",
  ch: "Chain",
  chain: "Chain",
  sl_st: "Slip stitch",
  slst: "Slip stitch",
  slip_stitch: "Slip stitch",
  magic_ring: "Magic ring",
};

export function stitchTypeLabel(type: string): string {
  return STITCH_TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

/** One-line description of a stitch for the selection card, as HTML.
 * `sequence_index` counts across the whole piece, so the position within
 * the round is derived from the stitch's round-mates. */
export function stitchHeadlineHtml(stitch: StitchGeometry, doc: GeometryDocument): string {
  const positionInRound =
    doc.stitches.filter(
      (s) =>
        s.component_id === stitch.component_id &&
        s.round_index === stitch.round_index &&
        s.sequence_index < stitch.sequence_index,
    ).length + 1;
  const badges = [
    stitch.is_increase ? '<span class="badge increase">Increase</span>' : "",
    stitch.is_decrease ? '<span class="badge decrease">Decrease</span>' : "",
  ].join("");
  return (
    `<strong>${escapeHtml(stitchTypeLabel(stitch.stitch_type))}</strong>${badges}<br />` +
    `Round ${stitch.round_index} · stitch ${positionInRound}`
  );
}
