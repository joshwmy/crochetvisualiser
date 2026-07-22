import * as THREE from "three";
import type { GeometryDocument } from "../types/geometry";
import type { Measurement } from "../state/store";

/** Point-to-point / stitch-to-stitch distance in the document's real-world
 * unit (`doc.units`, always "cm" today) — approximate, since it's derived
 * from analytically-placed stitch positions, not a physical measurement.
 * See docs/measurement-tools.md. */
export function measureDistance(doc: GeometryDocument, stitchIdA: string, stitchIdB: string): Measurement | null {
  const a = doc.stitches.find((s) => s.stitch_id === stitchIdA);
  const b = doc.stitches.find((s) => s.stitch_id === stitchIdB);
  if (!a || !b) return null;
  const dx = a.position[0] - b.position[0];
  const dy = a.position[1] - b.position[1];
  const dz = a.position[2] - b.position[2];
  const distanceCm = Math.sqrt(dx * dx + dy * dy + dz * dz);
  return {
    id: `${stitchIdA}__${stitchIdB}__${Date.now()}`,
    stitchIdA,
    stitchIdB,
    distanceCm,
  };
}

/** Approximate round circumference: sum of consecutive horizontal-neighbour
 * edge lengths within one round (an analytic estimate, not a measured
 * physical circumference — see docs/measurement-tools.md). */
export function measureRoundCircumference(
  doc: GeometryDocument,
  componentId: string,
  roundIndex: number,
): number {
  const ring = doc.stitches
    .filter((s) => s.component_id === componentId && s.round_index === roundIndex)
    .sort((a, b) => a.sequence_index - b.sequence_index);
  if (ring.length < 2) return 0;
  let total = 0;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i].position;
    const b = ring[(i + 1) % ring.length].position;
    total += Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  }
  return total;
}

export function buildMeasurementLine(doc: GeometryDocument, measurement: Measurement): THREE.Line | null {
  const a = doc.stitches.find((s) => s.stitch_id === measurement.stitchIdA);
  const b = doc.stitches.find((s) => s.stitch_id === measurement.stitchIdB);
  if (!a || !b) return null;
  const geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(...a.position),
    new THREE.Vector3(...b.position),
  ]);
  const material = new THREE.LineDashedMaterial({ color: 0x5fb0e6, dashSize: 0.15, gapSize: 0.08 });
  const line = new THREE.Line(geometry, material);
  line.computeLineDistances();
  line.name = `measurement-${measurement.id}`;
  return line;
}
