// Mirrors src/crochet_reconstruction/diagram/ir.py and corrections.py
// field-for-field. Deep domain payloads stay snake_case on the wire (see
// api/diagram_schemas.py's module docstring) — only the thin request/
// response wrapper shapes below use camelCase.

export type Vec2 = [number, number];
export type BBox = [number, number, number, number];

export type DiagramStitchType =
  | "magic_ring"
  | "chain"
  | "slip_stitch"
  | "single_crochet"
  | "half_double_crochet"
  | "double_crochet"
  | "increase"
  | "decrease"
  | "join";

export type ClassificationMethod =
  | "data_attribute"
  | "use_reference"
  | "element_id"
  | "css_class"
  | "title"
  | "aria_label"
  | "primitive_geometry"
  | "manual_override"
  | "unclassified";

export type ConfidenceBand = "high" | "medium" | "low" | "manual";

export interface DiagramSymbol {
  symbol_id: string;
  stitch_type: DiagramStitchType | null;
  candidate_stitch_types: DiagramStitchType[];
  source_element_id: string | null;
  source_element_path: string;
  source_metadata: Record<string, string>;
  position: Vec2;
  bbox: BBox;
  anchor: Vec2;
  orientation_deg: number;
  scale: number;
  round_index: number | null;
  sequence_index: number | null;
  classification_method: ClassificationMethod;
  confidence: number;
  confidence_band: ConfidenceBand;
  user_override: boolean;
  ambiguous: boolean;
  unsupported: boolean;
  round_start: boolean;
  round_closure: boolean;
  geometry_fingerprint: string | null;
}

export type RelationshipType =
  | "parent_attachment"
  | "yarn_sequence"
  | "horizontal_neighbor"
  | "explicit_connector"
  | "round_closure"
  | "increase_group"
  | "decrease_group"
  | "centre_attachment";

export type InferenceMethod =
  | "explicit_connector"
  | "explicit_metadata"
  | "manual_override"
  | "radial_projection"
  | "nearest_previous_round";

export interface DiagramRelationship {
  relationship_id: string;
  source_symbol_ids: string[];
  target_symbol_ids: string[];
  relationship_type: RelationshipType;
  inference_method: InferenceMethod;
  confidence: number;
  evidence: string;
  user_override: boolean;
}

export interface DiagramRound {
  round_index: number;
  symbol_ids: string[];
  centre_distance_avg: number | null;
  start_symbol_id: string | null;
  closure: boolean;
}

export type DiagramSeverity = "info" | "warning" | "error";

export interface DiagramDiagnostic {
  severity: DiagramSeverity;
  code: string;
  message: string;
  svg_element_id: string | null;
  symbol_id: string | null;
  element_path: string | null;
  round_index: number | null;
  confidence: number | null;
  suggested_action: string | null;
}

export interface DiagramSource {
  kind: "svg_diagram";
  fingerprint: string;
  width: number;
  height: number;
  view_box: BBox;
}

export interface DiagramConstruction {
  mode: "circular" | "row";
  centre: Vec2 | null;
  centre_method: "explicit_metadata" | "explicit_symbol" | "user_specified" | "geometric_estimate" | null;
  direction: "clockwise" | "counterclockwise" | null;
  start_symbol_id: string | null;
  round_tolerance: number | null;
}

export interface DiagramDocument {
  schema_version: string;
  source: DiagramSource;
  construction: DiagramConstruction;
  symbols: DiagramSymbol[];
  relationships: DiagramRelationship[];
  rounds: DiagramRound[];
  diagnostics: DiagramDiagnostic[];
  fingerprint: string | null;
}

export interface SymbolOverride {
  stitch_type?: DiagramStitchType | null;
  round_index?: number | null;
  sequence_index?: number | null;
  ignored?: boolean | null;
  round_start?: boolean | null;
  round_closure?: boolean | null;
}

export type RelationshipOverrideAction =
  | "set_parent"
  | "remove_parent"
  | "add_parent"
  | "set_children"
  | "confirm"
  | "restore_automatic";

export interface RelationshipOverride {
  symbol_id: string;
  action: RelationshipOverrideAction;
  parent_symbol_ids?: string[];
  child_symbol_ids?: string[];
}

export interface ConstructionOverrides {
  centre?: Vec2 | null;
  direction?: "clockwise" | "counterclockwise" | null;
  start_symbol_id?: string | null;
  round_tolerance?: number | null;
}

export interface DiagramCorrectionSet {
  schema_version?: string;
  symbol_overrides: Record<string, SymbolOverride>;
  relationship_overrides: RelationshipOverride[];
  construction_overrides?: ConstructionOverrides | null;
}

export function emptyCorrectionSet(): DiagramCorrectionSet {
  return { symbol_overrides: {}, relationship_overrides: [], construction_overrides: null };
}

// Mirrors diagram/ir.py's DIAGRAM_SCHEMA_VERSION. An exact-match check, not
// a semver-compatible range, matching geometry/load.ts's
// SUPPORTED_SCHEMA_VERSION precedent for this project's versioning
// strategy: a schema bump is a deliberate, coordinated frontend+backend
// change, never something a mismatched pair should silently limp through.
export const SUPPORTED_DIAGRAM_SCHEMA_VERSION = "1.0.0";
