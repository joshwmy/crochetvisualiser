import { describe, expect, it, vi } from "vitest";
import { renderDiagramOverlay, defaultOverlayFilters } from "../src/diagram/svg_overlay";
import type { DiagramDocument, DiagramSymbol } from "../src/types/diagram";

function makeSymbol(overrides: Partial<DiagramSymbol>): DiagramSymbol {
  return {
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
    round_start: false,
    round_closure: false,
    geometry_fingerprint: null,
    ...overrides,
  };
}

function makeDocument(symbols: DiagramSymbol[]): DiagramDocument {
  return {
    schema_version: "1.0.0",
    source: { kind: "svg_diagram", fingerprint: "f", width: 100, height: 100, view_box: [0, 0, 100, 100] },
    construction: {
      mode: "circular",
      centre: [50, 50],
      centre_method: "explicit_symbol",
      direction: "clockwise",
      start_symbol_id: null,
      round_tolerance: null,
    },
    symbols,
    relationships: [],
    rounds: [],
    diagnostics: [],
    fingerprint: null,
  };
}

describe("renderDiagramOverlay", () => {
  it("never contains a <script> tag or embeds the raw source text, regardless of symbol content", () => {
    const container = document.createElement("div");
    const malicious = makeSymbol({
      symbol_id: "evil",
      source_element_id: "<script>alert(1)</script>",
      source_metadata: { "data-stitch-type": "<img src=x onerror=alert(1)>" },
    });
    renderDiagramOverlay(container, makeDocument([malicious]), defaultOverlayFilters(), {
      selectedSymbolId: null,
      onSelectSymbol: vi.fn(),
    });

    expect(container.querySelector("script")).toBeNull();
    // Built via createElementNS + setAttribute/textContent only — never
    // innerHTML with untrusted content — so a value containing "<script>"
    // can only ever end up as inert text/attribute data, never parsed as
    // markup. Confirm no element in the tree interprets it as a tag.
    expect(container.innerHTML).not.toContain("<script>alert");
  });

  it("renders one circle per symbol", () => {
    const container = document.createElement("div");
    const doc = makeDocument([makeSymbol({ symbol_id: "a" }), makeSymbol({ symbol_id: "b", position: [20, 20] })]);
    renderDiagramOverlay(container, doc, defaultOverlayFilters(), {
      selectedSymbolId: null,
      onSelectSymbol: vi.fn(),
    });
    expect(container.querySelectorAll("circle").length).toBe(2);
  });

  it("colours symbols by confidence band", () => {
    const container = document.createElement("div");
    const doc = makeDocument([makeSymbol({ symbol_id: "a", confidence_band: "low" })]);
    renderDiagramOverlay(container, doc, defaultOverlayFilters(), {
      selectedSymbolId: null,
      onSelectSymbol: vi.fn(),
    });
    const circle = container.querySelector("circle")!;
    expect(circle.getAttribute("fill")).toBe("#c62828");
  });

  it("marks unclassified/ambiguous symbols with a visible non-colour indicator", () => {
    const container = document.createElement("div");
    const doc = makeDocument([makeSymbol({ symbol_id: "a", stitch_type: null, confidence_band: "low" })]);
    renderDiagramOverlay(container, doc, defaultOverlayFilters(), {
      selectedSymbolId: null,
      onSelectSymbol: vi.fn(),
    });
    // Colour alone must not be the only signal (brief: "Do not rely only on
    // colour") — a text marker must also be present.
    expect(container.querySelector("text")?.textContent).toBe("?");
  });

  it("invokes onSelectSymbol when a symbol is clicked", () => {
    const container = document.createElement("div");
    const onSelectSymbol = vi.fn();
    const doc = makeDocument([makeSymbol({ symbol_id: "clickable" })]);
    renderDiagramOverlay(container, doc, defaultOverlayFilters(), {
      selectedSymbolId: null,
      onSelectSymbol,
    });
    const group = container.querySelector('[data-symbol-id="clickable"]') as SVGGElement;
    group.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(onSelectSymbol).toHaveBeenCalledWith("clickable");
  });

  it("filters out symbols outside the visible-rounds set", () => {
    const container = document.createElement("div");
    const doc = makeDocument([
      makeSymbol({ symbol_id: "r1", round_index: 1 }),
      makeSymbol({ symbol_id: "r2", round_index: 2, position: [30, 30] }),
    ]);
    renderDiagramOverlay(
      container,
      doc,
      { ...defaultOverlayFilters(), visibleRounds: new Set([1]) },
      { selectedSymbolId: null, onSelectSymbol: vi.fn() },
    );
    expect(container.querySelector('[data-symbol-id="r1"]')).not.toBeNull();
    expect(container.querySelector('[data-symbol-id="r2"]')).toBeNull();
  });

  it("onlyUnclassified filter shows only symbols with no resolved stitch type", () => {
    const container = document.createElement("div");
    const doc = makeDocument([
      makeSymbol({ symbol_id: "classified" }),
      makeSymbol({ symbol_id: "unclassified", stitch_type: null }),
    ]);
    renderDiagramOverlay(
      container,
      doc,
      { ...defaultOverlayFilters(), onlyUnclassified: true },
      { selectedSymbolId: null, onSelectSymbol: vi.fn() },
    );
    expect(container.querySelector('[data-symbol-id="classified"]')).toBeNull();
    expect(container.querySelector('[data-symbol-id="unclassified"]')).not.toBeNull();
  });

  it("hides relationship lines when showRelationships is false", () => {
    const container = document.createElement("div");
    const symbols = [makeSymbol({ symbol_id: "a" }), makeSymbol({ symbol_id: "b", position: [40, 40] })];
    const doc: DiagramDocument = {
      ...makeDocument(symbols),
      relationships: [
        {
          relationship_id: "rel-1",
          source_symbol_ids: ["a"],
          target_symbol_ids: ["b"],
          relationship_type: "parent_attachment",
          inference_method: "radial_projection",
          confidence: 0.5,
          evidence: "test",
          user_override: false,
        },
      ],
    };
    renderDiagramOverlay(container, doc, { ...defaultOverlayFilters(), showRelationships: true }, {
      selectedSymbolId: null,
      onSelectSymbol: vi.fn(),
    });
    expect(container.querySelectorAll("line").length).toBe(1);

    renderDiagramOverlay(container, doc, { ...defaultOverlayFilters(), showRelationships: false }, {
      selectedSymbolId: null,
      onSelectSymbol: vi.fn(),
    });
    expect(container.querySelectorAll("line").length).toBe(0);
  });

  it("marks the selected symbol with a distinct stroke", () => {
    const container = document.createElement("div");
    const doc = makeDocument([makeSymbol({ symbol_id: "a" }), makeSymbol({ symbol_id: "b", position: [40, 40] })]);
    renderDiagramOverlay(container, doc, defaultOverlayFilters(), {
      selectedSymbolId: "a",
      onSelectSymbol: vi.fn(),
    });
    const selectedCircle = container.querySelector('[data-symbol-id="a"] circle')!;
    const otherCircle = container.querySelector('[data-symbol-id="b"] circle')!;
    expect(selectedCircle.getAttribute("stroke")).toBe("#000000");
    expect(otherCircle.getAttribute("stroke")).toBe("#ffffff");
  });
});
