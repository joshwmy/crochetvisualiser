import type { GeometryDocument } from "../types/geometry";
import { SUPPORTED_SCHEMA_VERSION } from "../types/geometry";

export class GeometryLoadError extends Error {}

export async function loadGeometry(url: string): Promise<GeometryDocument> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new GeometryLoadError(`failed to fetch ${url}: HTTP ${response.status}`);
  }
  const data = (await response.json()) as GeometryDocument;
  validateGeometry(data);
  return data;
}

export function validateGeometry(data: GeometryDocument): void {
  if (data.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    throw new GeometryLoadError(
      `unsupported geometry schema_version ${data.schema_version}, expected ${SUPPORTED_SCHEMA_VERSION}`,
    );
  }
  // pattern_fingerprint may legitimately be null (a written-pattern compile
  // has no beanie Pattern to fingerprint), but graph_fingerprint and
  // geometry_fingerprint are always computed internally and must be present
  // — their absence means the document was hand-built or corrupted, not a
  // real pipeline output.
  if (!data.graph_fingerprint || !data.geometry_fingerprint) {
    throw new GeometryLoadError(
      "geometry document is missing graph_fingerprint or geometry_fingerprint",
    );
  }
  if (!Array.isArray(data.stitches) || data.stitches.length === 0) {
    throw new GeometryLoadError("geometry document has no stitches");
  }
  const ids = new Set(data.stitches.map((s) => s.stitch_id));
  if (ids.size !== data.stitches.length) {
    throw new GeometryLoadError("geometry document has duplicate stitch_id values");
  }
  for (const stitch of data.stitches) {
    for (const value of [...stitch.position, ...stitch.orientation]) {
      if (!Number.isFinite(value)) {
        throw new GeometryLoadError(`stitch ${stitch.stitch_id} has a non-finite coordinate`);
      }
    }
  }
}
