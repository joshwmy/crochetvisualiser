import { App } from "./app/App";
import { loadGeometry, GeometryLoadError } from "./geometry/load";
import type { ViewPreset } from "./camera/camera";
import type { ClippingState, ViewerState } from "./state/store";

const canvas = document.getElementById("viewport") as HTMLCanvasElement;
const errorBanner = document.getElementById("viewer-error") as HTMLDivElement;

// Held at module scope deliberately: a ResizeObserver with no surviving JS
// reference can be garbage-collected, silently stopping delivery after its
// first callback — this held a stale initial canvas size for exactly that
// reason before this was module-scoped.
let resizeObserver: ResizeObserver | null = null;

function showError(message: string): void {
  errorBanner.textContent = message;
  errorBanner.style.display = "block";
}

function qs<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing element #${id}`);
  return el as T;
}

async function main(): Promise<void> {
  const geometryUrl = "/geometry.json";
  let response: Response;
  try {
    response = await fetch(geometryUrl);
  } catch (err) {
    showError(`Could not reach ${geometryUrl}: ${(err as Error).message}`);
    return;
  }
  const jsonText = await response.clone().text();
  const jsonSizeBytes = new Blob([jsonText]).size;

  let doc;
  try {
    doc = await loadGeometry(geometryUrl);
  } catch (err) {
    if (err instanceof GeometryLoadError) {
      showError(`Geometry fixture is invalid: ${err.message}`);
    } else {
      showError(`Failed to load geometry: ${(err as Error).message}`);
    }
    return;
  }

  let app: App;
  try {
    app = new App(canvas, doc, jsonSizeBytes);
  } catch (err) {
    showError(`Failed to initialise the 3D viewer (WebGL may be unavailable): ${(err as Error).message}`);
    return;
  }

  wireInfoPanel(doc);
  wireViewControls(app);
  wireTimeline(app);
  wireVisibilityControls(app, doc);
  wireClippingControls(app);
  wireInspector(app);
  wirePerformancePanel(app);
  wireResize(app);
}

function wireInfoPanel(doc: ReturnType<App["getDoc"]>): void {
  const info = qs<HTMLDListElement>("info");
  const rows: [string, string][] = [
    ["Pattern fingerprint", doc.pattern_fingerprint ?? "n/a"],
    ["Graph fingerprint", doc.graph_fingerprint ?? "n/a"],
    ["Geometry fingerprint", doc.geometry_fingerprint ?? "n/a"],
    ["Stitches", String(doc.stitches.length)],
    ["Overall height", `${doc.measurements.overall_height_cm.toFixed(1)} cm (estimated)`],
    ["Max radius", `${doc.measurements.max_radius_cm.toFixed(1)} cm (estimated)`],
  ];
  info.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
}

function wireViewControls(app: App): void {
  const viewMode = qs<HTMLSelectElement>("view-mode");
  viewMode.addEventListener("change", () => {
    app.getStore().set({ viewMode: viewMode.value as ViewerState["viewMode"] });
  });

  const toggleProjection = qs<HTMLButtonElement>("toggle-projection");
  toggleProjection.addEventListener("click", () => {
    const mode = app.toggleProjection();
    app.getStore().set({ cameraMode: mode });
  });

  const presets = qs<HTMLDivElement>("view-presets");
  presets.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    const preset = target.dataset.preset as ViewPreset | undefined;
    if (preset) app.setViewPreset(preset);
  });
}

function wireTimeline(app: App): void {
  const timeline = app.getTimeline();
  const slider = qs<HTMLInputElement>("timeline-slider");
  const label = qs<HTMLSpanElement>("timeline-label");
  slider.max = String(timeline.length);
  slider.value = String(timeline.currentIndex);
  label.textContent = `${timeline.currentIndex} / ${timeline.length}`;

  app.getStore().subscribe((state) => {
    slider.value = String(state.animationIndex);
    label.textContent = `${state.animationIndex} / ${timeline.length}`;
  });

  slider.addEventListener("input", () => timeline.setIndex(Number(slider.value)));

  const playButton = qs<HTMLButtonElement>("anim-play");
  playButton.addEventListener("click", () => {
    if (timeline.isPlaying) {
      timeline.pause();
      playButton.textContent = "Play";
    } else {
      timeline.play();
      playButton.textContent = "Pause";
    }
  });
  qs<HTMLButtonElement>("anim-restart").addEventListener("click", () => {
    timeline.restart();
    playButton.textContent = "Pause";
  });
  qs<HTMLButtonElement>("anim-step-forward").addEventListener("click", () => timeline.stepForward());
  qs<HTMLButtonElement>("anim-step-back").addEventListener("click", () => timeline.stepBackward());

  const speed = qs<HTMLInputElement>("anim-speed");
  speed.addEventListener("input", () => timeline.setSpeed(Number(speed.value)));
}

function wireVisibilityControls(app: App, doc: ReturnType<App["getDoc"]>): void {
  const componentIds = [...new Set(doc.stitches.map((s) => s.component_id))];
  const container = qs<HTMLDivElement>("component-toggles");
  container.innerHTML = componentIds
    .map((id) => `<label><input type="checkbox" checked data-component="${id}" /> ${id}</label>`)
    .join("");
  container.addEventListener("change", (event) => {
    const target = event.target as HTMLInputElement;
    const componentId = target.dataset.component;
    if (!componentId) return;
    const state = app.getStore().get();
    const hidden = new Set(state.hiddenComponentIds);
    if (target.checked) hidden.delete(componentId);
    else hidden.add(componentId);
    app.getStore().set({ hiddenComponentIds: hidden });
  });

  const roundSelect = qs<HTMLSelectElement>("isolate-round");
  const roundKeys = new Set<string>();
  const options: string[] = ['<option value="">All rounds</option>'];
  for (const stitch of [...doc.stitches].sort((a, b) => a.sequence_index - b.sequence_index)) {
    const key = `${stitch.component_id}:${stitch.round_index}`;
    if (roundKeys.has(key)) continue;
    roundKeys.add(key);
    options.push(`<option value="${key}">${stitch.component_id} round ${stitch.round_index}</option>`);
  }
  roundSelect.innerHTML = options.join("");
  roundSelect.addEventListener("change", () => {
    app.getStore().set({ isolatedRoundKey: roundSelect.value || null });
  });

  const opacitySlider = qs<HTMLInputElement>("opacity-slider");
  opacitySlider.addEventListener("input", () => {
    app.getStore().set({ opacity: Number(opacitySlider.value) / 100 });
  });
}

function wireClippingControls(app: App): void {
  const enabled = qs<HTMLInputElement>("clip-enabled");
  const axis = qs<HTMLSelectElement>("clip-axis");
  const offset = qs<HTMLInputElement>("clip-offset");
  const invert = qs<HTMLInputElement>("clip-invert");

  function pushState(): void {
    const clipping: ClippingState = {
      enabled: enabled.checked,
      axis: axis.value as ClippingState["axis"],
      offset: Number(offset.value) / 100,
      invert: invert.checked,
    };
    app.getStore().set({ clipping });
  }

  for (const el of [enabled, axis, offset, invert]) {
    el.addEventListener("input", pushState);
    el.addEventListener("change", pushState);
  }
}

function wireInspector(app: App): void {
  const empty = qs<HTMLParagraphElement>("inspector-empty");
  const content = qs<HTMLDListElement>("inspector-content");

  app.getStore().subscribe((state) => {
    if (!state.selectedStitchId) {
      empty.hidden = false;
      content.hidden = true;
      return;
    }
    const stitch = app.getStitch(state.selectedStitchId);
    if (!stitch) return;
    empty.hidden = true;
    content.hidden = false;
    const rows: [string, string][] = [
      ["Stitch ID", stitch.stitch_id],
      ["Type", stitch.stitch_type],
      ["Component", stitch.component_id],
      ["Round", String(stitch.round_index)],
      ["Sequence index", String(stitch.sequence_index)],
      ["Loop placement", stitch.loop_placement],
      ["Parents", stitch.parent_stitch_ids.join(", ") || "(magic ring)"],
      ["Increase", String(stitch.is_increase)],
      ["Decrease", String(stitch.is_decrease)],
      ["Source", stitch.source_reference],
    ];
    content.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");

    const focusButton = document.createElement("button");
    focusButton.type = "button";
    focusButton.textContent = "Focus camera here";
    focusButton.addEventListener("click", () => app.focusOnStitch(stitch.stitch_id));
    content.appendChild(focusButton);
  });
}

function wirePerformancePanel(app: App): void {
  const perf = qs<HTMLDListElement>("perf");
  const stats = app.getStats();
  const rows: [string, string][] = [
    ["Stitches", String(stats.stitchCount)],
    ["Yarn segments", String(stats.yarnSegmentCount)],
    ["Triangles (approx.)", stats.triangleCount.toLocaleString()],
    ["Draw calls (structural)", String(stats.drawCalls)],
    ["Geometry build time", `${stats.geometryGenerationMs.toFixed(1)} ms`],
    ["Fixture JSON size", `${(stats.jsonSizeBytes / 1024).toFixed(0)} KB`],
  ];
  perf.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
}

function wireResize(app: App): void {
  // A single resize() call at construction time can race the CSS grid
  // layout (canvas.clientWidth/Height briefly reads a transitional value
  // before the panel/grid settles). A ResizeObserver re-measures whenever
  // the canvas's actual box changes, including that first layout pass, and
  // also covers container resizes a window "resize" event would miss.
  resizeObserver = new ResizeObserver(() => app.handleResize());
  resizeObserver.observe(canvas);
  window.addEventListener("resize", () => app.handleResize());

  // Defense in depth: a ResizeObserver's first callback can fire before the
  // stylesheet-driven grid layout has painted (observed: canvas still at
  // its 300x150 intrinsic default at that instant), and it won't fire again
  // on its own since nothing subsequently changes the box size. Two nested
  // rAFs guarantee at least one full layout/paint has happened before this
  // explicit re-measure.
  requestAnimationFrame(() => requestAnimationFrame(() => app.handleResize()));
}

main().catch((err) => {
  showError(`Unexpected viewer error: ${(err as Error).message}`);
  // eslint-disable-next-line no-console
  console.error(err);
});
