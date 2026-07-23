/**
 * Safe 2D diagram preview: builds an SVG scene entirely from the
 * structured `DiagramDocument` (positions, stitch types, confidence) using
 * `document.createElementNS`, one attribute at a time — the user's raw
 * uploaded SVG text is never parsed, injected, or rendered by the browser.
 * This is the frontend half of the security boundary described in
 * docs/svg-security.md ("render only the normalised Diagram IR, never the
 * uploaded source").
 */

import type { DiagramDocument, DiagramSymbol } from "../types/diagram";

const SVG_NS = "http://www.w3.org/2000/svg";

const CONFIDENCE_COLOUR: Record<string, string> = {
  high: "#2e7d32",
  medium: "#f9a825",
  low: "#c62828",
  manual: "#1565c0",
};

export const CONFIDENCE_LEGEND: { band: string; color: string; label: string }[] = [
  { band: "high", color: CONFIDENCE_COLOUR.high, label: "High confidence" },
  { band: "medium", color: CONFIDENCE_COLOUR.medium, label: "Medium confidence" },
  { band: "low", color: CONFIDENCE_COLOUR.low, label: "Low confidence — review" },
  { band: "manual", color: CONFIDENCE_COLOUR.manual, label: "Manually corrected" },
];

const RELATIONSHIP_COLOUR: Record<string, string> = {
  parent_attachment: "#616161",
  centre_attachment: "#616161",
  explicit_connector: "#00838f",
  horizontal_neighbor: "#bdbdbd",
  round_closure: "#8e24aa",
  yarn_sequence: "transparent", // structural bookkeeping only, not shown
  increase_group: "transparent",
  decrease_group: "transparent",
};

export interface OverlayFilters {
  visibleRounds: Set<number> | null; // null = all rounds visible
  showRelationships: boolean;
  onlyUnclassified: boolean;
  onlyLowConfidence: boolean;
}

export function defaultOverlayFilters(): OverlayFilters {
  return { visibleRounds: null, showRelationships: true, onlyUnclassified: false, onlyLowConfidence: false };
}

function el<K extends keyof SVGElementTagNameMap>(tag: K): SVGElementTagNameMap[K] {
  return document.createElementNS(SVG_NS, tag);
}

function symbolVisible(symbol: DiagramSymbol, filters: OverlayFilters): boolean {
  if (filters.visibleRounds && symbol.round_index !== null && !filters.visibleRounds.has(symbol.round_index)) {
    return false;
  }
  if (filters.onlyUnclassified && symbol.stitch_type !== null) return false;
  if (filters.onlyLowConfidence && symbol.confidence >= 0.5) return false;
  return true;
}

/**
 * Builds (or rebuilds into `container`) the safe SVG preview. Returns the
 * root `<svg>` element for further manipulation (e.g. pan/zoom transform).
 */
export function renderDiagramOverlay(
  container: HTMLElement,
  document_: DiagramDocument,
  filters: OverlayFilters,
  options: {
    selectedSymbolId: string | null;
    onSelectSymbol: (symbolId: string) => void;
  },
): SVGSVGElement {
  container.innerHTML = "";
  const svg = el("svg");
  const [minX, minY, maxX, maxY] = document_.source.view_box;
  svg.setAttribute("viewBox", `${minX} ${minY} ${maxX - minX} ${maxY - minY}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "100%");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Normalised diagram preview (symbols and inferred relationships)");

  const positionById = new Map(document_.symbols.map((s) => [s.symbol_id, s.position]));
  const visibleIds = new Set(
    document_.symbols.filter((s) => symbolVisible(s, filters)).map((s) => s.symbol_id),
  );

  if (filters.showRelationships) {
    const relGroup = el("g");
    relGroup.setAttribute("data-role", "relationships");
    for (const rel of document_.relationships) {
      const colour = RELATIONSHIP_COLOUR[rel.relationship_type] ?? "transparent";
      if (colour === "transparent") continue;
      const from = positionById.get(rel.source_symbol_ids[0]);
      const to = positionById.get(rel.target_symbol_ids[0]);
      if (!from || !to) continue;
      if (!visibleIds.has(rel.source_symbol_ids[0])) continue;
      const line = el("line");
      line.setAttribute("x1", String(from[0]));
      line.setAttribute("y1", String(from[1]));
      line.setAttribute("x2", String(to[0]));
      line.setAttribute("y2", String(to[1]));
      line.setAttribute("stroke", colour);
      line.setAttribute("stroke-width", rel.inference_method === "explicit_connector" ? "1.5" : "0.8");
      line.setAttribute("stroke-dasharray", rel.confidence < 0.6 ? "2,2" : "");
      line.setAttribute("data-relationship-id", rel.relationship_id);
      relGroup.appendChild(line);
    }
    svg.appendChild(relGroup);
  }

  const symbolGroup = el("g");
  symbolGroup.setAttribute("data-role", "symbols");
  for (const symbol of document_.symbols) {
    if (!symbolVisible(symbol, filters)) continue;
    const [x, y] = symbol.position;
    const radius = Math.max(3, 4 * symbol.scale);

    const g = el("g");
    g.setAttribute("data-symbol-id", symbol.symbol_id);
    g.setAttribute("tabindex", "0");
    g.setAttribute("role", "button");
    g.setAttribute(
      "aria-label",
      `Symbol ${symbol.symbol_id}: ${symbol.stitch_type ?? "unclassified"}, ` +
        `${symbol.confidence_band} confidence`,
    );
    g.style.cursor = "pointer";

    const circle = el("circle");
    circle.setAttribute("cx", String(x));
    circle.setAttribute("cy", String(y));
    circle.setAttribute("r", String(radius));
    circle.setAttribute("fill", CONFIDENCE_COLOUR[symbol.confidence_band] ?? "#9e9e9e");
    circle.setAttribute("fill-opacity", "0.85");
    const isSelected = symbol.symbol_id === options.selectedSymbolId;
    circle.setAttribute("stroke", isSelected ? "#000000" : "#ffffff");
    circle.setAttribute("stroke-width", isSelected ? "2" : "1");
    g.appendChild(circle);

    if (symbol.ambiguous || symbol.unsupported || symbol.stitch_type === null) {
      const marker = el("text");
      marker.setAttribute("x", String(x));
      marker.setAttribute("y", String(y + radius * 0.35));
      marker.setAttribute("text-anchor", "middle");
      marker.setAttribute("font-size", String(radius * 1.2));
      marker.setAttribute("fill", "#ffffff");
      marker.setAttribute("pointer-events", "none");
      marker.textContent = "?";
      g.appendChild(marker);
    }

    const activate = (): void => options.onSelectSymbol(symbol.symbol_id);
    g.addEventListener("click", activate);
    g.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });

    symbolGroup.appendChild(g);
  }
  svg.appendChild(symbolGroup);

  container.appendChild(svg);
  return svg;
}
