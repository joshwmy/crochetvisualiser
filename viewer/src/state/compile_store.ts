import { Store } from "./store";
import type { CompileSummary, Diagnostic } from "../types/compile";

export type CompileStatus =
  | "idle"
  | "compiling"
  | "success"
  | "validation_error"
  | "network_error"
  | "internal_error";

export interface CompileState {
  status: CompileStatus;
  diagnostics: Diagnostic[];
  summary: CompileSummary | null;
  errorMessage: string | null;
  /** Incremented on every submitted request; used to discard stale in-flight responses. */
  requestId: number;
}

export function createInitialCompileState(): CompileState {
  return {
    status: "idle",
    diagnostics: [],
    summary: null,
    errorMessage: null,
    requestId: 0,
  };
}

export type CompileStore = Store<CompileState>;

export function createCompileStore(): CompileStore {
  return new Store<CompileState>(createInitialCompileState());
}
