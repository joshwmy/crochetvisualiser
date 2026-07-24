import { Store } from "./store";
import type { DiagramAnalyseSummary, DiagramCompileResponse } from "../api/diagram_client";
import type { DiagramCorrectionSet, DiagramDiagnostic, DiagramDocument } from "../types/diagram";
import { emptyCorrectionSet } from "../types/diagram";
import type { DiagramViewport, OverlayFilters } from "../diagram/svg_overlay";
import { defaultOverlayFilters } from "../diagram/svg_overlay";

export type DiagramStatus =
  | "idle"
  | "analysing"
  | "analysed"
  | "compiling"
  | "compiled"
  | "network_error"
  | "internal_error";

/** Which panel the diagram workflow is currently showing — the 3D model
 * stays loaded in the existing viewer even while reviewing in 2D, so this
 * is purely a "what's the diagram sidebar showing" flag, not a scene
 * switch (brief: "Preserve the Diagram IR and corrections when returning
 * to review"). */
export type DiagramViewStage = "review" | "compiled";

export interface DiagramState {
  status: DiagramStatus;
  viewStage: DiagramViewStage;
  svgSourceDraft: string;
  document: DiagramDocument | null;
  corrections: DiagramCorrectionSet;
  selectedSymbolId: string | null;
  selectedRelationshipId: string | null;
  filters: OverlayFilters;
  viewport: DiagramViewport | null; // null = fit to the document's native viewBox
  diagnostics: DiagramDiagnostic[];
  summary: DiagramAnalyseSummary | null;
  lastCompileSummary: DiagramCompileResponse["summary"] | null;
  errorMessage: string | null;
  requestId: number;
}

export function createInitialDiagramState(): DiagramState {
  return {
    status: "idle",
    viewStage: "review",
    svgSourceDraft: "",
    document: null,
    corrections: emptyCorrectionSet(),
    selectedSymbolId: null,
    selectedRelationshipId: null,
    filters: defaultOverlayFilters(),
    viewport: null,
    diagnostics: [],
    summary: null,
    lastCompileSummary: null,
    errorMessage: null,
    requestId: 0,
  };
}

export type DiagramStore = Store<DiagramState>;

export function createDiagramStore(): DiagramStore {
  return new Store<DiagramState>(createInitialDiagramState());
}
