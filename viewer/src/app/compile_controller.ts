import type { App } from "./App";
import { compilePattern, CompileNetworkError } from "../api/client";
import { GeometryLoadError } from "../geometry/load";
import type { GeometryDocument } from "../types/geometry";
import { createCompileStore, type CompileStore } from "../state/compile_store";

/**
 * Owns the "paste pattern -> compile -> replace live model" workflow.
 *
 * A monotonically increasing `requestId` guards against a slow, stale
 * request overwriting the result of a newer one: only the response whose
 * request is still the latest gets applied to the store or the viewer.
 */
export class CompileController {
  readonly store: CompileStore = createCompileStore();
  private inFlight: AbortController | null = null;
  /** Sent as `options.strict` on the next request. Set by the UI toggle
   * (main.ts's wireStrictMode) rather than read from the viewer store, so
   * this controller keeps depending on `App` only for
   * `loadGeometryDocument` — the one thing it actually drives. */
  private strict = false;

  constructor(private app: App) {}

  setStrict(strict: boolean): void {
    this.strict = strict;
  }

  async submit(source: string): Promise<void> {
    if (!source.trim()) {
      this.store.set({
        status: "validation_error",
        diagnostics: [
          {
            severity: "error",
            code: "EMPTY_INPUT",
            message: "Pattern source is empty.",
            line: null,
            column: null,
            section: null,
            sourceText: null,
            expected: null,
            actual: null,
          },
        ],
        summary: null,
        errorMessage: null,
      });
      return;
    }

    this.inFlight?.abort();
    const controller = new AbortController();
    this.inFlight = controller;
    const requestId = this.store.get().requestId + 1;
    this.store.set({ status: "compiling", requestId, errorMessage: null });

    try {
      const response = await compilePattern(source, controller.signal, {
        strict: this.strict,
      });
      if (this.store.get().requestId !== requestId) return; // superseded

      if (!response.success) {
        this.store.set({
          status: "validation_error",
          diagnostics: response.diagnostics,
          summary: null,
        });
        return;
      }

      try {
        await this.app.loadGeometryDocument(response.geometry as GeometryDocument);
      } catch (err) {
        // A structurally valid compile response with geometry the viewer
        // itself rejects (bad schema version, missing fingerprints) must
        // not corrupt whatever model is currently on screen.
        if (this.store.get().requestId !== requestId) return;
        this.store.set({
          status: "internal_error",
          diagnostics: response.diagnostics,
          summary: null,
          errorMessage:
            err instanceof GeometryLoadError
              ? `Server returned geometry the viewer could not load: ${err.message}`
              : `Unexpected error loading the compiled model: ${(err as Error).message}`,
        });
        return;
      }

      this.store.set({
        status: "success",
        diagnostics: response.diagnostics,
        summary: response.summary,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return; // superseded
      if (this.store.get().requestId !== requestId) return;
      const message = err instanceof CompileNetworkError ? err.message : String(err);
      this.store.set({
        status: "network_error",
        diagnostics: [],
        summary: null,
        errorMessage: message,
      });
    }
  }
}
