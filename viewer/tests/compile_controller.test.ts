import { beforeEach, describe, expect, it, vi } from "vitest";
import type { App } from "../src/app/App";
import { CompileNetworkError } from "../src/api/client";
import { GeometryLoadError } from "../src/geometry/load";

const compilePatternMock = vi.hoisted(() => vi.fn());
vi.mock("../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/api/client")>();
  return { ...actual, compilePattern: compilePatternMock };
});

const { CompileController } = await import("../src/app/compile_controller");

function makeFakeApp(overrides: Partial<App> = {}): App {
  return { loadGeometryDocument: vi.fn().mockResolvedValue(undefined), ...overrides } as App;
}

const successResponse = {
  success: true,
  pattern: { components: [] },
  stitchGraph: {},
  geometry: { schema_version: "0.1.0" },
  diagnostics: [],
  summary: {
    sectionCount: 1,
    stitchCount: 6,
    componentCount: 1,
    graphFingerprint: "g",
    geometryFingerprint: "geo",
  },
};

const failureResponse = {
  success: false,
  pattern: null,
  stitchGraph: null,
  geometry: null,
  diagnostics: [
    {
      severity: "error",
      code: "INVALID_SYNTAX",
      message: "bad",
      line: 1,
      column: null,
      section: null,
      sourceText: null,
      expected: null,
      actual: null,
    },
  ],
  summary: null,
};

describe("CompileController", () => {
  beforeEach(() => {
    compilePatternMock.mockReset();
  });

  it("rejects empty input without calling the API", async () => {
    const app = makeFakeApp();
    const controller = new CompileController(app);
    await controller.submit("   ");
    expect(compilePatternMock).not.toHaveBeenCalled();
    expect(controller.store.get().status).toBe("validation_error");
    expect(controller.store.get().diagnostics[0].code).toBe("EMPTY_INPUT");
  });

  it("loads the geometry and reports success on a successful compile", async () => {
    compilePatternMock.mockResolvedValue(successResponse);
    const app = makeFakeApp();
    const controller = new CompileController(app);

    await controller.submit("Round 1: 6 sc in magic ring [6]\n");

    expect(app.loadGeometryDocument).toHaveBeenCalledWith(successResponse.geometry);
    expect(controller.store.get().status).toBe("success");
    expect(controller.store.get().summary?.stitchCount).toBe(6);
  });

  it("reports validation_error with diagnostics on a failed compile, without touching the viewer", async () => {
    compilePatternMock.mockResolvedValue(failureResponse);
    const app = makeFakeApp();
    const controller = new CompileController(app);

    await controller.submit("Round 1: 6 xyz in magic ring [6]\n");

    expect(app.loadGeometryDocument).not.toHaveBeenCalled();
    expect(controller.store.get().status).toBe("validation_error");
    expect(controller.store.get().diagnostics).toEqual(failureResponse.diagnostics);
  });

  it("reports internal_error when the viewer rejects the returned geometry", async () => {
    compilePatternMock.mockResolvedValue(successResponse);
    const app = makeFakeApp({
      loadGeometryDocument: vi.fn().mockRejectedValue(new GeometryLoadError("bad schema")),
    });
    const controller = new CompileController(app);

    await controller.submit("Round 1: 6 sc in magic ring [6]\n");

    expect(controller.store.get().status).toBe("internal_error");
    expect(controller.store.get().errorMessage).toMatch(/bad schema/);
  });

  it("reports network_error when the request fails", async () => {
    compilePatternMock.mockRejectedValue(new CompileNetworkError("offline"));
    const app = makeFakeApp();
    const controller = new CompileController(app);

    await controller.submit("Round 1: 6 sc in magic ring [6]\n");

    expect(controller.store.get().status).toBe("network_error");
    expect(controller.store.get().errorMessage).toBe("offline");
  });

  it("a slower first request cannot overwrite a faster second request's result", async () => {
    let resolveFirst!: (value: unknown) => void;
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve;
    });
    compilePatternMock
      .mockImplementationOnce(() => firstPromise)
      .mockImplementationOnce(async () => successResponse);

    const app = makeFakeApp();
    const controller = new CompileController(app);

    const firstSubmit = controller.submit("Round 1: 6 sc in magic ring [6]\n");
    const secondSubmit = controller.submit("Round 1: 12 sc in magic ring [12]\n");

    await secondSubmit;
    expect(controller.store.get().status).toBe("success");

    // The first (slower) request resolves after the second — it must not
    // be allowed to overwrite the already-applied second result.
    resolveFirst(failureResponse);
    await firstSubmit;
    expect(controller.store.get().status).toBe("success");
    expect(app.loadGeometryDocument).toHaveBeenCalledTimes(1);
  });

  it("aborts an in-flight request when a new one is submitted", async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, "abort");
    let capturedSignal: AbortSignal | undefined;
    compilePatternMock.mockImplementationOnce((_source: string, signal: AbortSignal) => {
      capturedSignal = signal;
      return new Promise(() => {}); // never resolves
    });
    compilePatternMock.mockImplementationOnce(async () => successResponse);

    const app = makeFakeApp();
    const controller = new CompileController(app);

    void controller.submit("Round 1: 6 sc in magic ring [6]\n");
    await Promise.resolve();
    void controller.submit("Round 1: 12 sc in magic ring [12]\n");

    expect(abortSpy).toHaveBeenCalled();
    expect(capturedSignal?.aborted).toBe(true);
    abortSpy.mockRestore();
  });
});
