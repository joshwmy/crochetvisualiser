import { afterEach, describe, expect, it, vi } from "vitest";
import { compilePattern, CompileNetworkError, getApiBaseUrl } from "../src/api/client";

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

  it("throws CompileNetworkError when fetch itself fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("network down")),
    );
    const controller = new AbortController();
    await expect(
      compilePattern("Round 1: 6 sc in magic ring [6]\n", controller.signal),
    ).rejects.toThrow(CompileNetworkError);
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
