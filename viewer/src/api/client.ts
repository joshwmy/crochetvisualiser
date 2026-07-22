import type { CompileResponse } from "../types/compile";

export class CompileNetworkError extends Error {}

/** Reads VITE_API_BASE_URL at build time; falls back to the local dev backend. */
export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return configured?.replace(/\/$/, "") || "http://localhost:8000";
}

export async function compilePattern(
  source: string,
  signal: AbortSignal,
): Promise<CompileResponse> {
  const url = `${getApiBaseUrl()}/api/visualizer/compile`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }),
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
