import type { CompileResponse } from "../types/compile";
import type { DiagramCorrectionSet, DiagramDiagnostic, DiagramDocument } from "../types/diagram";
import { CompileNetworkError, DEFAULT_REQUEST_OPTIONS, getApiBaseUrl } from "./client";
import type { RequestOptions } from "./client";

export interface DiagramAnalyseSummary {
  symbolCount: number;
  classifiedCount: number;
  unclassifiedCount: number;
  roundCount: number;
  lowConfidenceCount: number;
  readyToCompile: boolean;
}

export interface DiagramAnalyseResponse {
  success: boolean;
  diagram: DiagramDocument | null;
  diagnostics: DiagramDiagnostic[];
  summary: DiagramAnalyseSummary | null;
}

// The compile response reuses the written-pattern CompileResponse's
// summary shape (see api/diagram_schemas.py's docstring) but carries a
// DiagramDocument instead of a ComponentsPayload, and an extra
// `sourceKind`/`diagram` field — a small, separate interface rather than
// forcing CompileResponse's `pattern` field into a shape it was never
// designed for.
export interface DiagramCompileResponse {
  success: boolean;
  sourceKind: "svg_diagram";
  diagram: DiagramDocument | null;
  stitchGraph: CompileResponse["stitchGraph"];
  geometry: CompileResponse["geometry"];
  diagnostics: DiagramDiagnostic[];
  summary: {
    sectionCount: number;
    stitchCount: number;
    componentCount: number;
    graphFingerprint: string | null;
    geometryFingerprint: string | null;
  } | null;
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const url = `${getApiBaseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new CompileNetworkError(`Could not reach ${url}: ${(err as Error).message}`);
  }
  if (!response.ok) {
    throw new CompileNetworkError(`Request failed: HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Strict analysis withholds `summary.readyToCompile` when the chart produced
 * warnings; unlike the compile endpoints it never turns a parsed chart into a
 * failure, so the 2D review step always has something to show. See
 * docs/compile-api.md's "Strict mode". */
export function analyseDiagram(
  svgSource: string,
  signal?: AbortSignal,
  options: RequestOptions = DEFAULT_REQUEST_OPTIONS,
): Promise<DiagramAnalyseResponse> {
  return postJson<DiagramAnalyseResponse>(
    "/api/visualizer/diagram/analyse",
    { svgSource, options },
    signal,
  );
}

export function compileDiagram(
  diagram: DiagramDocument,
  corrections: DiagramCorrectionSet,
  signal?: AbortSignal,
  options: RequestOptions = DEFAULT_REQUEST_OPTIONS,
): Promise<DiagramCompileResponse> {
  return postJson<DiagramCompileResponse>(
    "/api/visualizer/diagram/compile",
    { diagram, corrections, options },
    signal,
  );
}
