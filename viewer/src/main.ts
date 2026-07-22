import { App } from "./app/App";
import { CompileController } from "./app/compile_controller";
import { loadGeometry, GeometryLoadError } from "./geometry/load";
import type { ViewPreset } from "./camera/camera";
import type { ClippingState, ViewerState } from "./state/store";
import type { CompileState } from "./state/compile_store";
import { AMIGURUMI_EXAMPLE } from "./examples";

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
    showError(
      `Failed to initialise the 3D viewer (WebGL may be unavailable): ${(err as Error).message}`,
    );
    return;
  }

  const controller = new CompileController(app);

  // Test-only hook consumed by e2e/compile-workflow.spec.ts (see
  // App.getRendererInfo's docstring) — never read by application code.
  (window as unknown as { __app: App }).__app = app;

  wireViewControls(app);
  wireTimeline(app);
  wireClippingControls(app);
  wireInspector(app);
  wireResize(app);
  wireCompileWorkflow(app, controller);
  refreshDocDependentUI(app);
}

/** Re-renders everything derived from `app.getDoc()` — called on startup and
 * after every successful compile, since a recompile can change the round
 * list, component list, stitch count, and performance numbers entirely. */
function refreshDocDependentUI(app: App): void {
  wireInfoPanel(app);
  wireVisibilityControls(app);
  wirePerformancePanel(app);
  const timeline = app.getTimeline();
  const slider = qs<HTMLInputElement>("timeline-slider");
  slider.max = String(timeline.length);
  slider.value = String(timeline.currentIndex);
  qs<HTMLSpanElement>("timeline-label").textContent = `${timeline.currentIndex} / ${timeline.length}`;
}

function wireInfoPanel(app: App): void {
  const doc = app.getDoc();
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
  const slider = qs<HTMLInputElement>("timeline-slider");
  const label = qs<HTMLSpanElement>("timeline-label");

  app.getStore().subscribe((state) => {
    slider.value = String(state.animationIndex);
    label.textContent = `${state.animationIndex} / ${app.getTimeline().length}`;
  });

  slider.addEventListener("input", () => app.getTimeline().setIndex(Number(slider.value)));

  const playButton = qs<HTMLButtonElement>("anim-play");
  playButton.addEventListener("click", () => {
    const timeline = app.getTimeline();
    if (timeline.isPlaying) {
      timeline.pause();
      playButton.textContent = "Play";
    } else {
      timeline.play();
      playButton.textContent = "Pause";
    }
  });
  qs<HTMLButtonElement>("anim-restart").addEventListener("click", () => {
    app.getTimeline().restart();
    playButton.textContent = "Pause";
  });
  qs<HTMLButtonElement>("anim-step-forward").addEventListener("click", () =>
    app.getTimeline().stepForward(),
  );
  qs<HTMLButtonElement>("anim-step-back").addEventListener("click", () =>
    app.getTimeline().stepBackward(),
  );

  const speed = qs<HTMLInputElement>("anim-speed");
  speed.addEventListener("input", () => app.getTimeline().setSpeed(Number(speed.value)));
}

function wireVisibilityControls(app: App): void {
  const doc = app.getDoc();
  const componentIds = [...new Set(doc.stitches.map((s) => s.component_id))];
  const container = qs<HTMLDivElement>("component-toggles");
  container.innerHTML = componentIds
    .map((id) => `<label><input type="checkbox" checked data-component="${id}" /> ${id}</label>`)
    .join("");

  const roundSelect = qs<HTMLSelectElement>("isolate-round");
  const roundKeys = new Set<string>();
  const options: string[] = ['<option value="">All rounds</option>'];
  for (const stitch of [...doc.stitches].sort((a, b) => a.sequence_index - b.sequence_index)) {
    const key = `${stitch.component_id}:${stitch.round_index}`;
    if (roundKeys.has(key)) continue;
    roundKeys.add(key);
    options.push(
      `<option value="${key}">${stitch.component_id} round ${stitch.round_index}</option>`,
    );
  }
  roundSelect.innerHTML = options.join("");
  app.getStore().set({ hiddenComponentIds: new Set(), isolatedRoundKey: null });
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

  qs<HTMLDivElement>("component-toggles").addEventListener("change", (event) => {
    const target = event.target as HTMLInputElement;
    const componentId = target.dataset.component;
    if (!componentId) return;
    const state = app.getStore().get();
    const hidden = new Set(state.hiddenComponentIds);
    if (target.checked) hidden.delete(componentId);
    else hidden.add(componentId);
    app.getStore().set({ hiddenComponentIds: hidden });
  });

  qs<HTMLSelectElement>("isolate-round").addEventListener("change", (event) => {
    const select = event.target as HTMLSelectElement;
    app.getStore().set({ isolatedRoundKey: select.value || null });
  });

  qs<HTMLInputElement>("opacity-slider").addEventListener("input", (event) => {
    const input = event.target as HTMLInputElement;
    app.getStore().set({ opacity: Number(input.value) / 100 });
  });
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

const STATUS_LABELS: Record<CompileState["status"], string> = {
  idle: "",
  compiling: "Compiling…",
  success: "Compiled successfully.",
  validation_error: "Pattern could not be compiled — see diagnostics below.",
  network_error: "Could not reach the compile server.",
  internal_error: "The compiled result could not be loaded.",
};

const SEVERITY_LABEL: Record<string, string> = {
  error: "Error",
  warning: "Warning",
  info: "Info",
};

function wireCompileWorkflow(app: App, controller: CompileController): void {
  const form = qs<HTMLFormElement>("compile-form");
  const source = qs<HTMLTextAreaElement>("pattern-source");
  const compileButton = qs<HTMLButtonElement>("compile-button");
  const exampleButton = qs<HTMLButtonElement>("example-button");
  const clearButton = qs<HTMLButtonElement>("clear-button");
  const status = qs<HTMLParagraphElement>("compile-status");
  const summaryEl = qs<HTMLDListElement>("compile-summary");
  const diagnosticsEl = qs<HTMLUListElement>("diagnostics-list");

  source.value = AMIGURUMI_EXAMPLE;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void controller.submit(source.value);
  });

  // Ctrl+Enter (or Cmd+Enter on macOS) compiles without leaving the textarea.
  source.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      void controller.submit(source.value);
    }
  });

  exampleButton.addEventListener("click", () => {
    source.value = AMIGURUMI_EXAMPLE;
  });

  clearButton.addEventListener("click", () => {
    source.value = "";
    source.focus();
  });

  controller.store.subscribe((state) => {
    status.textContent = STATUS_LABELS[state.status];
    status.dataset.status = state.status;
    compileButton.disabled = state.status === "compiling";

    if (state.status === "success" && state.summary) {
      summaryEl.hidden = false;
      const rows: [string, string][] = [
        ["Sections", String(state.summary.sectionCount)],
        ["Stitches", String(state.summary.stitchCount)],
        ["Components", String(state.summary.componentCount)],
      ];
      summaryEl.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
      refreshDocDependentUI(app);
    } else if (state.status !== "compiling") {
      summaryEl.hidden = true;
    }

    if (state.errorMessage) {
      diagnosticsEl.innerHTML = `<li data-severity="error">${SEVERITY_LABEL.error}: ${state.errorMessage}</li>`;
      return;
    }

    diagnosticsEl.innerHTML = state.diagnostics
      .map((d) => {
        const location =
          d.line !== null
            ? `<div class="diagnostic-location">Line ${d.line}${d.sourceText ? `: ${escapeHtml(d.sourceText)}` : ""}</div>`
            : "";
        return `<li data-severity="${d.severity}">${SEVERITY_LABEL[d.severity] ?? d.severity}: ${escapeHtml(d.message)}${location}</li>`;
      })
      .join("");
  });
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

main().catch((err) => {
  showError(`Unexpected viewer error: ${(err as Error).message}`);
  // eslint-disable-next-line no-console
  console.error(err);
});
