import type { CompileResponse } from "../types/compile";

export class CompileNetworkError extends Error {}

/** Reads VITE_API_BASE_URL at build time; falls back to the local dev backend. */
export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return configured?.replace(/\/$/, "") || "http://localhost:8000";
}

/**
 * Statuses a sleeping free-tier host (Render) can answer with while the
 * instance boots. Retrying is safe because every endpoint is stateless and
 * idempotent — nothing is persisted (docs/compile-api.md).
 */
const COLD_START_STATUSES = new Set([502, 503, 504]);
export const COLD_START_RETRY_DELAY_MS = 5000;

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("aborted", "AbortError"));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

/**
 * POSTs JSON, retrying once after a short delay when the failure looks like a
 * host waking from idle (fetch rejected, or a 502/503/504). A second failure
 * is reported as-is; an abort is never retried or wrapped.
 */
export async function postWithColdStartRetry(
  url: string,
  body: unknown,
  signal?: AbortSignal,
  retryDelayMs: number = COLD_START_RETRY_DELAY_MS,
): Promise<Response> {
  const init: RequestInit = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  };
  for (let attempt = 0; ; attempt++) {
    const isLastAttempt = attempt === 1;
    let response: Response;
    try {
      response = await fetch(url, init);
    } catch (err) {
      if (isAbortError(err)) throw err;
      if (isLastAttempt) {
        throw new CompileNetworkError(`Could not reach ${url}: ${(err as Error).message}`);
      }
      await delay(retryDelayMs, signal);
      continue;
    }
    if (!isLastAttempt && COLD_START_STATUSES.has(response.status)) {
      await delay(retryDelayMs, signal);
      continue;
    }
    return response;
  }
}

/**
 * Fire-and-forget request that starts waking a sleeping API host as soon as
 * the page loads, so the user's first compile does not pay the whole boot
 * time. `no-cors` because only the request matters, not the response — it
 * also keeps a CORS mismatch from logging an error for a request nobody
 * reads. Skipped for a local backend, which never sleeps.
 */
export function warmUpApi(): void {
  const base = getApiBaseUrl();
  let hostname: string;
  try {
    hostname = new URL(base).hostname;
  } catch {
    return;
  }
  if (hostname === "localhost" || hostname === "127.0.0.1") return;
  fetch(`${base}/healthz`, { mode: "no-cors" }).catch(() => {
    // A failed warm-up is harmless: the real request retries on its own.
  });
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
  const response = await postWithColdStartRetry(url, { source, options }, signal);
  if (!response.ok) {
    // A non-2xx here means our own request was malformed (e.g. bad
    // terminology value) or the server had a transport-level failure —
    // either way the body is not our CompileResponse envelope, so this is
    // a network/client error, not a pattern-compile failure.
    throw new CompileNetworkError(`Compile request failed: HTTP ${response.status}`);
  }
  return (await response.json()) as CompileResponse;
}
