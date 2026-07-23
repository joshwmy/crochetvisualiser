import type { App } from "./App";
import { analyseDiagram, compileDiagram } from "../api/diagram_client";
import { CompileNetworkError } from "../api/client";
import { GeometryLoadError } from "../geometry/load";
import type { GeometryDocument } from "../types/geometry";
import {
  createDiagramStore,
  type DiagramStore,
} from "../state/diagram_store";
import type {
  DiagramCorrectionSet,
  RelationshipOverride,
  SymbolOverride,
} from "../types/diagram";

/**
 * Owns the "paste/upload SVG -> analyse -> review/correct -> compile to 3D"
 * workflow — the diagram-mode counterpart of `CompileController`. A failed
 * compile leaves whatever 3D model is currently loaded in `app` completely
 * untouched (brief: "A failed diagram compile must not destroy the last
 * valid 3D model"), since `App.loadGeometryDocument` itself only swaps
 * scene state after the new document has already validated successfully.
 */
export class DiagramController {
  readonly store: DiagramStore = createDiagramStore();
  private inFlight: AbortController | null = null;

  constructor(private app: App) {}

  async analyse(svgSource: string): Promise<void> {
    this.inFlight?.abort();
    const controller = new AbortController();
    this.inFlight = controller;
    const requestId = this.store.get().requestId + 1;
    this.store.set({
      status: "analysing",
      requestId,
      svgSourceDraft: svgSource,
      errorMessage: null,
    });

    try {
      const response = await analyseDiagram(svgSource, controller.signal);
      if (this.store.get().requestId !== requestId) return; // superseded

      this.store.set({
        status: response.success ? "analysed" : "network_error",
        document: response.diagram,
        diagnostics: response.diagnostics,
        summary: response.summary,
        selectedSymbolId: null,
        viewStage: "review",
        errorMessage: response.success
          ? null
          : "The SVG could not be analysed — see diagnostics below.",
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (this.store.get().requestId !== requestId) return;
      const message = err instanceof CompileNetworkError ? err.message : String(err);
      this.store.set({ status: "network_error", errorMessage: message });
    }
  }

  async compile(): Promise<void> {
    const state = this.store.get();
    if (!state.document) return;

    this.inFlight?.abort();
    const controller = new AbortController();
    this.inFlight = controller;
    const requestId = state.requestId + 1;
    this.store.set({ status: "compiling", requestId, errorMessage: null });

    try {
      const response = await compileDiagram(state.document, state.corrections, controller.signal);
      if (this.store.get().requestId !== requestId) return;

      if (!response.success || !response.geometry) {
        this.store.set({
          status: "network_error",
          diagnostics: response.diagnostics,
          document: response.diagram ?? this.store.get().document,
          errorMessage: "Compile failed — the previous 3D model (if any) is unchanged.",
        });
        return;
      }

      try {
        await this.app.loadGeometryDocument(response.geometry as GeometryDocument);
      } catch (err) {
        if (this.store.get().requestId !== requestId) return;
        this.store.set({
          status: "internal_error",
          diagnostics: response.diagnostics,
          errorMessage:
            err instanceof GeometryLoadError
              ? `Server returned geometry the viewer could not load: ${err.message}`
              : `Unexpected error loading the compiled model: ${(err as Error).message}`,
        });
        return;
      }

      this.store.set({
        status: "compiled",
        viewStage: "compiled",
        document: response.diagram ?? this.store.get().document,
        diagnostics: response.diagnostics,
        lastCompileSummary: response.summary,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (this.store.get().requestId !== requestId) return;
      const message = err instanceof CompileNetworkError ? err.message : String(err);
      this.store.set({
        status: "network_error",
        errorMessage: `Compile failed — the previous 3D model (if any) is unchanged: ${message}`,
      });
    }
  }

  returnToReview(): void {
    this.store.set({ viewStage: "review" });
  }

  selectSymbol(symbolId: string | null): void {
    this.store.set({ selectedSymbolId: symbolId });
  }

  setSymbolOverride(symbolId: string, override: SymbolOverride | null): void {
    const corrections = this.store.get().corrections;
    const nextOverrides = { ...corrections.symbol_overrides };
    if (override === null) delete nextOverrides[symbolId];
    else nextOverrides[symbolId] = { ...nextOverrides[symbolId], ...override };
    this.setCorrections({ ...corrections, symbol_overrides: nextOverrides });
  }

  addRelationshipOverride(override: RelationshipOverride): void {
    const corrections = this.store.get().corrections;
    this.setCorrections({
      ...corrections,
      relationship_overrides: [...corrections.relationship_overrides, override],
    });
  }

  setConstructionOverride(update: DiagramCorrectionSet["construction_overrides"]): void {
    const corrections = this.store.get().corrections;
    this.setCorrections({ ...corrections, construction_overrides: update });
  }

  resetCorrections(): void {
    this.setCorrections({ symbol_overrides: {}, relationship_overrides: [], construction_overrides: null });
  }

  private setCorrections(corrections: DiagramCorrectionSet): void {
    this.store.set({ corrections });
  }
}
