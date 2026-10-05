import { afterEach, describe, expect, it, vi } from "vitest";
import {
  compilePattern,
  CompileNetworkError,
  COLD_START_RETRY_DELAY_MS,
  getApiBaseUrl,
  postWithColdStartRetry,
  warmUpApi,
} from "../src/api/client";

describe("getApiBaseUrl", () => {
  it("falls back to the local dev backend when unset", () => {
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
  });
});

describe("compilePattern", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the source and returns the parsed response on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, diagnostics: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const controller = new AbortController();
    const result = await compilePattern("Round 1: 6 sc in magic ring [6]\n", controller.signal);

    expect(result.success).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/visualizer/compile",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("throws CompileNetworkError when fetch fails on both attempts", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network down"));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const assertion = expect(
      compilePattern("Round 1: 6 sc in magic ring [6]\n", controller.signal),
    ).rejects.toThrow(CompileNetworkError);
    await vi.advanceTimersByTimeAsync(COLD_START_RETRY_DELAY_MS);
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("throws CompileNetworkError on a non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    const controller = new AbortController();
    await expect(
      compilePattern("Round 1: 6 sc in magic ring [6]\n", controller.signal),
    ).rejects.toThrow(CompileNetworkError);
  });

  it("propagates AbortError without wrapping it", async () => {
    const abortError = new DOMException("aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));
    const controller = new AbortController();
    await expect(
      compilePattern("Round 1: 6 sc in magic ring [6]\n", controller.signal),
    ).rejects.toBe(abortError);
  });
});

describe("postWithColdStartRetry", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  const ok = { ok: true, status: 200, json: async () => ({}) };

  it("retries once after a rejected fetch and returns the second response", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce(ok);
    vi.stubGlobal("fetch", fetchMock);

    const response = await postWithColdStartRetry("http://api/x", {}, undefined, 0);

    expect(response).toBe(ok);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([502, 503, 504])("retries once on HTTP %i", async (status) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status })
      .mockResolvedValueOnce(ok);
    vi.stubGlobal("fetch", fetchMock);

    const response = await postWithColdStartRetry("http://api/x", {}, undefined, 0);

    expect(response).toBe(ok);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("returns a second 503 rather than retrying again", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    vi.stubGlobal("fetch", fetchMock);

    const response = await postWithColdStartRetry("http://api/x", {}, undefined, 0);

    expect(response.status).toBe(503);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a non-cold-start error status", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 422 });
    vi.stubGlobal("fetch", fetchMock);

    const response = await postWithColdStartRetry("http://api/x", {}, undefined, 0);

    expect(response.status).toBe(422);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects with AbortError when aborted during the retry delay", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network down"));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    const assertion = expect(
      postWithColdStartRetry("http://api/x", {}, controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(10);
    controller.abort();
    await assertion;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("warmUpApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("skips the request for a local backend", () => {
    const fetchMock = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("fetch", fetchMock);

    warmUpApi();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("pings /healthz without CORS for a remote backend", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com/");
    const fetchMock = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("fetch", fetchMock);

    warmUpApi();

    expect(fetchMock).toHaveBeenCalledWith("https://api.example.com/healthz", {
      mode: "no-cors",
    });
  });

  it("swallows a failed warm-up", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    expect(() => warmUpApi()).not.toThrow();
    await Promise.resolve();
  });
});
