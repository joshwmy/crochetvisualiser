# Diagram IR specification

The versioned intermediate representation between "parsed SVG" and
"StitchGraph" — see `src/crochet_reconstruction/diagram/ir.py` for the
authoritative Pydantic models and `schemas/diagram_ir.schema.json` /
`diagram_symbol.schema.json` / `diagram_relationship.schema.json` for the
committed JSON Schema. **Do not confuse this with `StitchGraph`** — the IR
carries spatial/provenance/confidence data (bounding boxes, classification
method, per-symbol evidence) that has no meaning once a pattern is
expressed as worked stitches; `diagram/compiler.py` is the one place that
translates from this IR into the existing graph.

Current version: `DIAGRAM_SCHEMA_VERSION = "1.0.0"` (`ir.py`).
Corrections carry their own independent version,
`CORRECTIONS_SCHEMA_VERSION = "1.0.0"` (`corrections.py`) — the API
contract itself (request/response shapes) is versioned separately again
as `API_CONTRACT_VERSION` (`api/schema_export.py`), matching the existing
written-pattern API's versioning split.

## Top-level shape

```json
{
  "schema_version": "1.0.0",
  "source": { "kind": "svg_diagram", "fingerprint": "...", "width": 800, "height": 800, "view_box": [0, 0, 800, 800] },
  "construction": { "mode": "circular", "centre": [400, 400], "centre_method": "explicit_symbol", "direction": "clockwise", "start_symbol_id": null, "round_tolerance": null },
  "symbols": [ /* DiagramSymbol[] */ ],
  "relationships": [ /* DiagramRelationship[] */ ],
  "rounds": [ /* DiagramRound[] */ ],
  "diagnostics": [ /* DiagramDiagnostic[] */ ],
  "fingerprint": "..."
}
```

## Coordinate system

All symbol positions in the IR are in one deterministic **normalised
coordinate system**: the root `<svg>`'s `viewBox` mapped onto its
`width`x`height` canvas (uniform scale, approximating `xMidYMid meet` —
see `transforms.py`'s module docstring for why full
`preserveAspectRatio` slicing isn't implemented), with every ancestor
`<g>`/element `transform` and every `<use>` instance's own transform/offset
composed in. Raw, untransformed element-local coordinates never leak into
the IR — see `transforms.py` and `svg_parser.py`'s `_walk`.

## `DiagramSource`

| Field | Meaning |
|---|---|
| `fingerprint` | SHA-256 of the raw SVG source bytes (not stored; only the hash). |
| `width`, `height` | Resolved canvas size (from `width`/`height` attrs, falling back to `viewBox`). |
| `view_box` | `(min_x, min_y, max_x, max_y)` in normalised units. |

## `DiagramConstruction`

| Field | Meaning |
|---|---|
| `mode` | `"circular"` (only supported value this slice) or `"row"` (reserved, always rejected — see `docs/diagram-topology-inference.md`). |
| `centre` | `(x, y)` in normalised units, or `null` before inference runs. |
| `centre_method` | Provenance: `explicit_metadata`, `explicit_symbol`, `user_specified`, `geometric_estimate`. |
| `direction` | `clockwise` or `counterclockwise` — the round-traversal order used for stitch sequencing. |
| `start_symbol_id` | Explicit round-1 starting stitch, if set. |
| `round_tolerance` | Radial-distance clustering tolerance override, in normalised units (not cm — a diagram has no gauge). |

## `DiagramSymbol`

One extracted-and-classified chart symbol. `symbol_id` is derived
deterministically from the source element's position in the document tree
(`f"svg-symbol-{index}"`, assigned in document order during extraction) —
**never a random UUID** — so re-analysing byte-identical SVG reproduces
identical IDs, a precondition for corrections keyed by `symbol_id` to
remain valid across re-analysis.

| Field | Meaning |
|---|---|
| `stitch_type` | Resolved canonical type, or `null` if unclassified/ambiguous. |
| `candidate_stitch_types` | Plausible types when `ambiguous`; the single resolved type otherwise. |
| `source_element_id` / `source_element_path` | The original SVG element's own `id` (if any) and a structural path (`svg/g[2]/use[0]`) for diagnostics — never used as the stable identity. |
| `source_metadata` | Raw `data-*`/`id`/`class`/`aria-label` values that were inspected, kept for audit. |
| `position`, `bbox`, `anchor` | Normalised-coordinate geometry. `position`/`anchor` are the bounding-box centre, or — for a metadata-only element with no drawn geometry — the element's own local origin under its composed transform (a documented fallback; see `extraction.py`'s `_make_symbol`). |
| `orientation_deg`, `scale` | Derived from the composed transform's rotation/scale components. |
| `round_index`, `sequence_index` | Assigned by topology inference (or an explicit `data-round` override). |
| `classification_method` | Which extraction stage won — see `docs/diagram-symbol-ontology.md`'s priority order. |
| `confidence`, `confidence_band` | See the confidence model in `docs/diagram-symbol-ontology.md`. |
| `user_override` | True once a manual correction has touched this symbol. |
| `ambiguous` / `unsupported` | Mutually informative with `stitch_type is None` — see the ontology doc. |
| `round_start` / `round_closure` | Explicit markers, settable via metadata or correction. |

## `DiagramRelationship`

| Field | Meaning |
|---|---|
| `relationship_type` | One of `parent_attachment`, `yarn_sequence`, `horizontal_neighbor`, `explicit_connector`, `round_closure`, `increase_group`, `decrease_group`, `centre_attachment`. |
| `inference_method` | `explicit_connector`, `explicit_metadata`, `manual_override`, `radial_projection`, `nearest_previous_round`. |
| `source_symbol_ids` / `target_symbol_ids` | Both lists for schema uniformity; a `parent_attachment` always has one source and one-or-more targets (multiple targets = a decrease). |
| `confidence`, `evidence` | Same confidence model as symbols; `evidence` is a short human-readable justification string. |

## `DiagramRound`

A resolved round: `round_index` (1-based; the foundation ring/chain is
conceptually round 0 and never appears here — see
`docs/diagram-topology-inference.md`), the ordered `symbol_ids` in working
order, the average radial distance from centre, the round's own starting
symbol, and whether it carries an explicit closure.

## `DiagramDiagnostic`

Structured, never a raw exception message — see
`diagram/diagnostics.py`'s `DiagramDiagnosticCode` for the full catalogue
(mirrors the written-pattern parser's `Diagnostic` shape philosophy, kept
as a separate type since the fields have diagram-specific meaning —
`symbol_id`/`element_path`/`round_index` have no equivalent in a text
source's `line`/`column`).

## Fingerprints

`diagram/fingerprint.py`'s `compute_diagram_fingerprint` uses the same
recipe as the existing `graph.fingerprint`/`geometry.layout` fingerprints:
canonical (key-sorted, whitespace-minimal) JSON, SHA-256 over the UTF-8
bytes, excluding the fingerprint field itself. A `DiagramDocument`'s
fingerprint changes whenever its content changes (including after
corrections are applied and topology is re-inferred) — `pipeline.py`
recomputes it on every `compile_svg_diagram` call.
