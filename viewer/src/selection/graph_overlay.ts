import * as THREE from "three";
import type { GeometryDocument } from "../types/geometry";

const EDGE_COLORS: Record<string, number> = {
  insertion: 0xf5e642,
  horizontal_neighbor: 0x5fb0e6,
  yarn_sequence: 0x9a6fd1,
  round_closure: 0xe85d5d,
};

/**
 * Builds a thin-line overlay of the selected stitch's *local* graph
 * relationships only (its own edges, one hop) — never the whole graph, per
 * the brief's explicit "do not draw the entire graph by default" instruction.
 */
export function buildGraphOverlay(doc: GeometryDocument, selectedStitchId: string): THREE.LineSegments {
  const positionById = new Map(doc.stitches.map((s) => [s.stitch_id, s.position]));
  const relevant = doc.edges.filter(
    (e) => e.source_id === selectedStitchId || e.target_id === selectedStitchId,
  );

  const positions: number[] = [];
  const colors: number[] = [];
  for (const edge of relevant) {
    const from = positionById.get(edge.source_id);
    const to = positionById.get(edge.target_id);
    if (!from || !to) continue;
    positions.push(...from, ...to);
    const color = new THREE.Color(EDGE_COLORS[edge.edge_type] ?? 0xffffff);
    colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  const material = new THREE.LineBasicMaterial({ vertexColors: true, linewidth: 2 });
  const lines = new THREE.LineSegments(geometry, material);
  lines.name = "graph-overlay";
  return lines;
}

export const GRAPH_OVERLAY_LEGEND: { type: string; color: string; label: string }[] = [
  { type: "insertion", color: "#f5e642", label: "Insertion (parent/child)" },
  { type: "horizontal_neighbor", color: "#5fb0e6", label: "Horizontal neighbour" },
  { type: "yarn_sequence", color: "#9a6fd1", label: "Yarn sequence" },
  { type: "round_closure", color: "#e85d5d", label: "Round closure" },
];
