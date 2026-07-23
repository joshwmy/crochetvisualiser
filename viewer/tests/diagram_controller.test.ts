import { beforeEach, describe, expect, it, vi } from "vitest";
import type { App } from "../src/app/App";
import { CompileNetworkError } from "../src/api/client";
import { GeometryLoadError } from "../src/geometry/load";
import type { DiagramDocument } from "../src/types/diagram";

const analyseDiagramMock = vi.hoisted(() => vi.fn());
const compileDiagramMock = vi.hoisted(() => vi.fn());
vi.mock("../src/api/diagram_client", () => ({
  analyseDiagram: analyseDiagramMock,
  compileDiagram: compileDiagramMock,
}));

const { DiagramController } = await import("../src/app/diagram_controller");

function makeFakeApp(overrides: Partial<App> = {}): App {
  return { loadGeometryDocument: vi.fn().mockResolvedValue(undefined), ...overrides } as App;
}

const sampleDocument: DiagramDocument = {
  schema_version: "1.0.0",
  source: { kind: "svg_diagram", fingerprint: "abc", width: 100, height: 100, view_box: [0, 0, 100, 100] },
  construction: {
    mode: "circular",
    centre: [50, 50],
    centre_method: "explicit_symbol",
    direction: "clockwise",
    start_symbol_id: null,
    round_tolerance: null,
  },
  symbols: [
    {
      symbol_id: "svg-symbol-0",
      stitch_type: "single_crochet",
      candidate_stitch_types: ["single_crochet"],
      source_element_id: null,
      source_element_path: "svg/g[0]",
      source_metadata: {},
      position: [10, 10],
      bbox: [8, 8, 12, 12],
      anchor: [10, 10],
      orientation_deg: 0,
      scale: 1,
      round_index: 1,
      sequence_index: 0,
      classification_method: "data_attribute",
      confidence: 1.0,
      confidence_band: "high",
      user_override: false,
      ambiguous: false,
      unsupported: false,
      round_start: true,
      round_closure: false,
      geometry_fingerprint: null,
    },
  ],
  relationships: [],
  rounds: [{ round_index: 1, symbol_ids: ["svg-symbol-0"], centre_distance_avg: 1, start_symbol_id: "svg-symbol-0", closure: false }],
  diagnostics: [],
  fingerprint: "doc-fingerprint",
};

const analyseSuccess = {
  success: true,
  diagram: sampleDocument,
  diagnostics: [],
  summary: {
    symbolCount: 1,
    classifiedCount: 1,
    unclassifiedCount: 0,
    roundCount: 1,
    lowConfidenceCount: 0,
    readyToCompile: true,
  },
};

const compileSuccess = {
  success: true,
  sourceKind: "svg_diagram" as const,
  diagram: sampleDocument,
  stitchGraph: {},
  geometry: { schema_version: "0.1.0" },
  diagnostics: [],
  summary: {
    sectionCount: 1,
    stitchCount: 1,
    componentCount: 1,
    graphFingerprint: "g",
    geometryFingerprint: "geo",
  },
};

const compileFailure = {
  success: false,
  sourceKind: "svg_diagram" as const,
  diagram: sampleDocument,
  stitchGraph: null,
  geometry: null,
  diagnostics: [
    {
      severity: "error",
      code: "UNCLASSIFIED_SYMBOL",
      message: "still unresolved",
      svg_element_id: null,
      symbol_id: "svg-symbol-0",
      element_path: null,
      round_index: null,
      confidence: null,
      suggested_action: null,
    },
  ],
  summary: null,
};

describe("DiagramController", () => {
  beforeEach(() => {
    analyseDiagramMock.mockReset();
    compileDiagramMock.mockReset();
  });

  it("stores the analysed document and marks status analysed on success", async () => {
    analyseDiagramMock.mockResolvedValue(analyseSuccess);
    const app = makeFakeApp();
    const controller = new DiagramController(app);

    await controller.analyse("<svg></svg>");

    expect(controller.store.get().status).toBe("analysed");
    expect(controller.store.get().document).toEqual(sampleDocument);
    expect(controller.store.get().viewStage).toBe("review");
  });

  it("compiles successfully and loads the geometry into the existing viewer", async () => {
    analyseDiagramMock.mockResolvedValue(analyseSuccess);
    compileDiagramMock.mockResolvedValue(compileSuccess);
    const app = makeFakeApp();
    const controller = new DiagramController(app);

    await controller.analyse("<svg></svg>");
    await controller.compile();

    expect(app.loadGeometryDocument).toHaveBeenCalledWith(compileSuccess.geometry);
    expect(controller.store.get().status).toBe("compiled");
    expect(controller.store.get().viewStage).toBe("compiled");
  });

  it("a failed compile never touches the viewer and preserves the document for correction", async () => {
    analyseDiagramMock.mockResolvedValue(analyseSuccess);
    compileDiagramMock.mockResolvedValue(compileFailure);
    const app = makeFakeApp();
    const controller = new DiagramController(app);

    await controller.analyse("<svg></svg>");
    await controller.compile();

    expect(app.loadGeometryDocument).not.toHaveBeenCalled();
    expect(controller.store.get().status).toBe("network_error");
    expect(controller.store.get().document).toEqual(sampleDocument);
    expect(controller.store.get().viewStage).toBe("review");
  });

  it("a compile the viewer itself rejects reports internal_error without touching prior state", async () => {
    analyseDiagramMock.mockResolvedValue(analyseSuccess);
    compileDiagramMock.mockResolvedValue(compileSuccess);
    const app = makeFakeApp({
      loadGeometryDocument: vi.fn().mockRejectedValue(new GeometryLoadError("bad schema")),
    });
    const controller = new DiagramController(app);

    await controller.analyse("<svg></svg>");
    await controller.compile();

    expect(controller.store.get().status).toBe("internal_error");
    expect(controller.store.get().errorMessage).toMatch(/bad schema/);
  });

  it("reports network_error when analyse cannot reach the server", async () => {
    analyseDiagramMock.mockRejectedValue(new CompileNetworkError("offline"));
    const app = makeFakeApp();
    const controller = new DiagramController(app);

    await controller.analyse("<svg></svg>");

    expect(controller.store.get().status).toBe("network_error");
    expect(controller.store.get().errorMessage).toBe("offline");
  });

  it("setSymbolOverride merges into the correction set and is included in the next compile call", async () => {
    analyseDiagramMock.mockResolvedValue(analyseSuccess);
    compileDiagramMock.mockResolvedValue(compileSuccess);
    const app = makeFakeApp();
    const controller = new DiagramController(app);

    await controller.analyse("<svg></svg>");
    controller.setSymbolOverride("svg-symbol-0", { stitch_type: "double_crochet" });
    expect(controller.store.get().corrections.symbol_overrides["svg-symbol-0"]).toEqual({
      stitch_type: "double_crochet",
    });

    await controller.compile();
    expect(compileDiagramMock).toHaveBeenCalledWith(
      sampleDocument,
      controller.store.get().corrections,
      expect.anything(),
    );
  });

  it("resetCorrections clears all overrides", async () => {
    analyseDiagramMock.mockResolvedValue(analyseSuccess);
    const app = makeFakeApp();
    const controller = new DiagramController(app);
    await controller.analyse("<svg></svg>");

    controller.setSymbolOverride("svg-symbol-0", { stitch_type: "double_crochet" });
    controller.resetCorrections();

    expect(controller.store.get().corrections.symbol_overrides).toEqual({});
    expect(controller.store.get().corrections.relationship_overrides).toEqual([]);
  });

  it("a slower analyse response cannot overwrite a faster later one", async () => {
    let resolveFirst!: (value: unknown) => void;
    const firstPromise = new Promise((resolve) => {
      resolveFirst = resolve;
    });
    analyseDiagramMock.mockImplementationOnce(() => firstPromise).mockImplementationOnce(async () => analyseSuccess);

    const app = makeFakeApp();
    const controller = new DiagramController(app);

    const firstAnalyse = controller.analyse("<svg>first</svg>");
    const secondAnalyse = controller.analyse("<svg>second</svg>");

    await secondAnalyse;
    expect(controller.store.get().status).toBe("analysed");

    resolveFirst({ success: false, diagram: null, diagnostics: [], summary: null });
    await firstAnalyse;
    expect(controller.store.get().status).toBe("analysed");
    expect(controller.store.get().document).toEqual(sampleDocument);
  });
});
