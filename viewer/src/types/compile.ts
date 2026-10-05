// Mirrors src/crochet_reconstruction/api/schemas.py and
// parsing/written/diagnostics.py field-for-field (camelCase on the wire).

export type Severity = "info" | "warning" | "error";

export interface Diagnostic {
  severity: Severity;
  code: string;
  message: string;
  line: number | null;
  column: number | null;
  section: number | null;
  sourceText: string | null;
  expected: number | null;
  actual: number | null;
}

export interface CompileSummary {
  sectionCount: number;
  stitchCount: number;
  componentCount: number;
  graphFingerprint: string | null;
  geometryFingerprint: string | null;
}

export interface CompileResponse {
  success: boolean;
  pattern: { components: Record<string, unknown>[] } | null;
  stitchGraph: Record<string, unknown> | null;
  // `geometry` is intentionally typed as the real GeometryDocument at the
  // call site (see api/client.ts) — kept as unknown here to avoid an
  // import cycle with types/geometry.ts's own consumers.
  geometry: unknown | null;
  diagnostics: Diagnostic[];
  summary: CompileSummary | null;
}
