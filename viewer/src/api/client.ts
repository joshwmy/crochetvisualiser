import type { CompileResponse } from "../types/compile";

export class CompileNetworkError extends Error {}

/** Reads VITE_API_BASE_URL at build time; falls back to the local dev backend. */
export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return configured?.replace(/\/$/, "") || "http://localhost:8000";
}

/**
 * Request options shared by both compile paths.
 *
 * `strict` blocks a compile that only succeeded because something was assumed
 * or flagged — see docs/compile-api.md's "Strict mode". The backend defaults
 * it to `false`; this client sends it explicitly so a captured request says
 * which mode produced a given response, rather than leaving it to be inferred
 * from a default.
 */
export interface RequestOptions {
  strict: boolean;
}

export const DEFAULT_REQUEST_OPTIONS: RequestOptions = { strict: false };

export async function compilePattern(
  source: string,
  signal: AbortSignal,
  options: RequestOptions = DEFAULT_REQUEST_OPTIONS,
): Promise<CompileResponse> {
  const url = `${getApiBaseUrl()}/api/visualizer/compile`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, options }),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new CompileNetworkError(`Could not reach ${url}: ${(err as Error).message}`);
  }
  if (!response.ok) {
    // A non-2xx here means our own request was malformed (e.g. bad
    // terminology value) or the server had a transport-level failure —
    // either way the body is not our CompileResponse envelope, so this is
    // a network/client error, not a pattern-compile failure.
    throw new CompileNetworkError(`Compile request failed: HTTP ${response.status}`);
  }
  return (await response.json()) as CompileResponse;
}
