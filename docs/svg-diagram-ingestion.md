# SVG diagram ingestion

The first diagram-ingestion vertical slice: a clean vector SVG crochet
chart in, an interactive 3D model out, reusing the existing
written-pattern pipeline's `StitchGraph`, geometry, and viewer end to end.

```text
Written pattern → Lark parser ─┐
                                ├→ Pattern domain model → deterministic StitchGraph → GeometryDocument → FastAPI compile API → Three.js viewer
SVG crochet chart → this slice ┘
```

Both input paths converge on the same `StitchGraph`/`GeometryDocument`
types and the same viewer — this document describes only the SVG-specific
half:

```text
SVG crochet chart
→ secure SVG parsing and normalisation      (svg_parser.py, security.py, transforms.py)
→ Diagram IR                                (ir.py)
→ symbol classification                     (ontology.py, extraction.py, classification.py)
→ spatial and topological inference         (topology.py)
→ user review or correction                 (corrections.py, viewer/src/diagram/, viewer/src/app/diagram_controller.ts)
→ existing StitchGraph                      (compiler.py — DiagramTopologyCompiler)
→ existing GeometryDocument                 (geometry/layout.py, unmodified)
→ existing Three.js viewer                  (App.loadGeometryDocument, unmodified)
```

## Supported SVG profile — read this before uploading a chart

This is a deliberately bounded first slice, not a general SVG-chart reader.

**Supported:**

- Clean, machine-exported vector SVG (not a scan, not a screenshot embedded
  in SVG, not hand-traced strokes with wobbly coordinates).
- Primarily circular or radial construction — a chart worked outward from
  a centre in rounds. Row/flat-panel construction is explicitly rejected
  (`UNSUPPORTED_CHART_CONSTRUCTION`) this slice.
- **One** primary connected crochet component. Multiple unrelated
  motifs in one file will confuse centre detection (see
  `docs/known-limitations.md`).
- Consistent scale and orientation across the chart.
- Symbols represented as any of: `<use href="#...">` references to symbol
  definitions; groups/elements with semantic ids or classes; elements with
  `data-*` metadata (`data-stitch-type`, `data-round`); elements with
  `<title>` or `aria-label` accessible names; symbols named by an adjacent
  free-standing `<text>` label ("dc", "sc") with no metadata of their own; or,
  as a last resort, clean vector primitives within the small supported shape
  vocabulary (see `docs/diagram-symbol-ontology.md`).
- Nested `<g>` transforms, `<use>` with local `x`/`y` offsets, non-zero
  `viewBox` origins — all correctly normalised (`docs/diagram-ir-spec.md`
  covers the coordinate system; `transforms.py` implements it).
- Optional explicit attachment/connector lines (a `<line>` or `<path>`
  tagged `class="connector"` or `data-connector="true"`).
- Optional round labels (captured for diagnostics; not yet used to seed
  round numbering beyond `data-round` metadata on individual symbols).

**Not supported this slice** (see `docs/known-limitations.md` for the full
list and rationale):

- Raster images, scans, photographs, OCR — no computer vision anywhere in
  this pipeline.
- PDF extraction.
- Garment schematics, freeform lace, arbitrary hand-drawn charts.
- Full coverage of every crochet symbol — see the bounded ontology.
- Automatic interpretation of highly ambiguous charts — ambiguity is
  surfaced as a diagnostic requiring a manual correction, never guessed.

## Preferred metadata profile for chart authors/exporters

Highest classification confidence and zero geometry-heuristic risk comes
from explicit metadata:

```xml
<use href="#symbol-sc" data-stitch-type="single_crochet" data-round="2"/>
```

or:

```xml
<g id="round-2-stitch-5" class="crochet-symbol single-crochet">...</g>
```

See `docs/diagram-symbol-ontology.md` for the full canonical vocabulary and
the extraction priority order metadata is checked in.

## Architecture decision: Diagram IR → StitchGraph directly, not through Pattern

The brief asks this to be decided and documented explicitly. Two options
were available:

- **Option A** (chosen): `Diagram IR → DiagramTopologyCompiler → StitchGraph`
  directly.
- **Option B**: `Diagram IR → Pattern → StitchGraph`, reusing
  `graph.builder.build_stitch_graph`.

**Option A was chosen** because `graph/builder.py`'s own docstring
documents that its left-to-right "consume the next unconsumed
previous-round stitch" resolution strategy is safe *only* because every
written-pattern `Operation` carries an aggregate count, never an explicit
target — and explicitly warns that "a future written-pattern or diagram
parser producing ambiguous or out-of-order instructions would need a
different resolution strategy... must not be silently reused for that case
without re-examining this assumption." A diagram's topology inference
(`topology.py`) *does* name an explicit parent for every stitch (via
connectors, metadata, or radial projection) — strictly richer information
than an `Operation`'s aggregate count can carry without loss; forcing it
through `Operation`/`RepeatOp` would either lose that explicit binding or
require inventing an operation vocabulary that doesn't fit written
patterns' semantics.

Further evidence this was the intended extension point:
`graph.models.StitchNode` already has `diagram_symbol_reference: str | None`
and `target_rule: Literal["explicit", "deterministic_left_to_right"]`
fields with no other producer anywhere in this codebase before this slice.

`DiagramTopologyCompiler` (`diagram/compiler.py`) still builds a
`list[Component]` alongside the `StitchGraph`, but only as the minimum
adapter shape `geometry.layout.build_geometry`'s existing, *unmodified*
signature requires — `geometry.rotational_rounds._round_placements` reads
exactly `Component.kind`/`Round.number`/`Round.stated_total` and nothing
else (verified by inspection). This is not a second geometry engine or a
disguised route through `Pattern` — no `ProjectInput`, no
`CalculatedParameters`, no beanie-sizing semantics anywhere in the diagram
path.

## What is reused unchanged

- `graph.models.StitchGraph`, `StitchNode`, `Edge`, `YarnSegment`.
- `graph.validation.validate_graph` — every diagram-derived graph passes
  through the exact same invariant checks as a written-pattern graph.
- `graph.fingerprint.compute_graph_fingerprint`.
- `geometry.layout.build_geometry`, `geometry.rotational_rounds`,
  `geometry.frames` — zero changes.
- The entire Three.js viewer: `App.loadGeometryDocument`, structural/yarn
  mesh building, selection, clipping, measurement, path inspection, graph
  overlay.
- The compile API's response shape philosophy (`CompileSummary`-equivalent
  fields, structured diagnostics, no raw tracebacks).

## What is new

- `src/crochet_reconstruction/diagram/` — the entire ingestion package
  (parsing, IR, ontology, extraction, classification, topology,
  corrections, compiler, pipeline, fingerprint).
- `POST /api/visualizer/diagram/analyse` and `.../compile`
  (`api/routers/diagram.py`, `api/diagram_service.py`,
  `api/diagram_schemas.py`).
- Eight new committed JSON Schema artefacts (`schemas/diagram_*.json`).
- The SVG-diagram input mode in the viewer (`viewer/src/diagram/`,
  `viewer/src/app/diagram_controller.ts`, `viewer/src/state/diagram_store.ts`,
  `viewer/src/types/diagram.ts`, `viewer/src/api/diagram_client.ts`).
- Structural hit-proxy picking (`viewer/src/selection/hit_proxies.ts`),
  which happens to benefit the written-pattern path too (see
  `docs/open-source-resource-adoption.md`).

## Diagram diagrams (the required three, per the brief)

```text
Untrusted SVG
→ secure parser
→ sanitisation and limits
→ transform normalisation
→ Diagram IR
```

```text
Diagram symbols
→ round clustering
→ sequence ordering
→ parent inference
→ existing StitchGraph
```

```text
Automatic interpretation
→ confidence and diagnostics
→ user corrections
→ deterministic corrected Diagram IR
→ 3D compilation
```

See `docs/svg-security.md`, `docs/diagram-topology-inference.md`, and
`docs/diagram-corrections.md` respectively for the detail behind each.

## Related documents

- `docs/diagram-ir-spec.md` — the IR schema and coordinate system.
- `docs/diagram-symbol-ontology.md` — the bounded symbol vocabulary and
  classification priority/confidence model.
- `docs/diagram-topology-inference.md` — centre detection, round
  clustering, parent attachment, increase/decrease inference.
- `docs/diagram-corrections.md` — the correction model and its
  deterministic application order.
- `docs/svg-security.md` — the full threat model and controls.
- `docs/known-limitations.md` — what this slice does not attempt, and why.
- `docs/schema-artifacts.md` — the JSON Schema generation/versioning policy
  (unchanged mechanism, extended with the new diagram schemas).
