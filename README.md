# crochet-reconstruction — deterministic engine and scientific 3D visualiser

**Live demo: <https://joshwmy.github.io/crochetvisualiser/>** — the viewer
running against its bundled example model. The compile API is not deployed
yet, so "Interpret and render" and the SVG-diagram workflow will fail there;
everything driven by the loaded model (orbit, clipping, round isolation,
construction animation, measurement, annotations, stitch inspection) works.
See [`docs/deployment.md`](docs/deployment.md).

A framework-independent Python engine that generates and validates
mathematically consistent crochet beanie patterns from typed measurements
and gauge, plus a scientific 3D viewer that turns a compiled pattern into an
interactive, stitch-inspectable model. **No AI, no image analysis, no
computer vision** — every stitch count comes from explicit, tested
arithmetic, and every rendered stitch is traceable back to that same
structured data.

## Project pivot

This project's direction changed. The original goal was reconstructing a
likely pattern from photographs of a finished crochet object. **That is no
longer the active goal.** The current goal is the reverse and more
tractable direction: given a supported crochet pattern (today: structured
JSON; later: written patterns and diagrams), generate an approximate,
interactive 3D structural preview — resembling anatomy/molecular-visualisation
software more than a decorative model viewer, with the underlying stitch
graph always inspectable, never a black-box mesh.

Nothing from the previous direction was deleted. The full pre-pivot state
(including the contributor submission portal built for that direction) is
preserved on the `main` branch; all visualiser work happens on
`pattern-to-scientific-3d-visualizer`. See
[`docs/previous-contributor-portal-status.md`](docs/previous-contributor-portal-status.md)
for exactly what was paused and why, and
[`docs/product-boundary.md`](docs/product-boundary.md) for the full scope
history and disclaimer.

**What the visualiser promises**: enter or upload a supported crochet
pattern and receive an approximate, interactive 3D structural preview of
what the finished object is expected to look like and how it's
constructed. It does **not** promise perfect physical simulation, exact
yarn drape or tension, exact dimensions without gauge, or perfect parsing
of ambiguous patterns — see
[`docs/known-limitations.md`](docs/known-limitations.md).

## Pipeline

```
Measurements + gauge + selected template
                  ↓
         Structured pattern model      (domain/)
                  ↓
       Deterministic calculations      (engine/sizing.py, crown.py, body.py, brim.py)
                  ↓
          Pattern compilation          (engine/compiler.py)
                  ↓
          Pattern validation           (validation/)
                  ↓
     Human-readable instructions       (rendering/text_renderer.py)
```

The structured `Pattern` object — not the rendered text — is the source of
truth. A pattern with any fatal validation result is never rendered.

## Supported scope (Phase 1)

- **One category:** adult top-down beanies, worked in continuous (spiral)
  rounds.
- **Two body stitches:** single crochet (`sc`), half-double crochet (`hdc`).
- **One optional brim:** simple, unshaped, back-loop-only in-round brim.
- **US crochet terminology.**
- Solid-colour yarn only.

## Explicitly out of scope (Phase 1)

Image upload/analysis, computer vision, stitch recognition, crochet-vs-knit
classification, multimodal AI, automatic gauge/hook inference, 3D
reconstruction, yarn simulation, authentication, payments, social features,
a polished frontend, a mobile app, PostgreSQL/cloud storage, double
crochet, joined rounds, folded/ribbed brims, colour stripes, garments other
than beanies. Full list and rationale in
[`docs/product-boundary.md`](docs/product-boundary.md).

## Installation

Requires Python 3.12+ (developed and tested on 3.13).

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
```

## CLI usage

```bash
python -m crochet_reconstruction.cli generate \
  --input examples/adult_beanie_hdc.json \
  --output build/adult_beanie_hdc/
```

Writes to the output directory:

- `pattern.json` — the full structured pattern (source of truth).
- `validation_report.json` — every validation result, with severity.
- `pattern.txt` — human-readable US-terminology instructions, **written
  only if validation produced no fatal result.**

Exit codes: `0` fully valid and rendered; `1` fatal validation results
(structured output still written, for inspection); `2` malformed input
JSON; `3` measurements/gauge/template combination cannot be sized at all
(e.g. requested height too short for the implied crown/brim).

See `examples/adult_beanie_hdc.json` for the input shape, or any file under
`tests/golden/inputs/` for further worked examples (small/large
circumference, no-brim, sc vs. hdc).

## Phase 1.5: physical validation

Phase 1's software tests prove the engine is internally consistent — they
do not prove a generated pattern produces a physically usable beanie. Phase
1.5 adds tooling to generate a controlled set of trial patterns, package
them for real crochet testers, and evaluate the results honestly (no
fabricated data, no single "accuracy" score, no automatic engine changes).
See [`docs/physical-validation-protocol.md`](docs/physical-validation-protocol.md)
for the full protocol.

```bash
# Generate the expert-review pack (10 trials stressing range boundaries):
python -m crochet_reconstruction.cli expert-review-pack --output build/expert_review/

# After testers submit PhysicalTrialResult JSON files:
python -m crochet_reconstruction.cli evaluate \
  --trials build/expert_review/ \
  --results physical-results/ \
  --output build/physical_evaluation/
```

See [`docs/measurement-guide.md`](docs/measurement-guide.md) and
[`docs/expert-evaluation-rubric.md`](docs/expert-evaluation-rubric.md) for
what a tester fills in, and
[`docs/decision-gates.md`](docs/decision-gates.md) for how results map to a
continue/narrow/redesign recommendation (always for human review — nothing
here changes engine code automatically).

## Stitch graph, geometry, and the scientific 3D viewer

Given a compiled component list, `crochet_reconstruction.graph` expands its
aggregate operations into an explicit per-stitch graph (stable IDs,
insertion targets, sequence order), and `crochet_reconstruction.geometry`
places every stitch in approximate 3D space using gauge-driven analytical
formulas. A Vite + TypeScript + Three.js viewer (`viewer/`) renders the
result with scientific-inspection interactions (orbit, clipping planes,
round isolation, construction animation, stitch-level selection).

```text
Written pattern
  -> parsing.written (Lark grammar + deterministic semantic expansion)
  -> domain.rounds.Component / domain.operations.Operation   (existing, unmodified)
  -> graph.builder.build_stitch_graph                          (existing, unmodified)
  -> geometry.layout.build_geometry                            (existing, unmodified)
  -> api: POST /api/visualizer/compile
  -> viewer: pasted pattern -> live 3D model (no manual fixture regeneration)
```

**SVG diagram parsing is now implemented** as a third producer feeding the
same `StitchGraph`/`GeometryDocument` boundary, alongside the existing
structured-JSON path and the written-pattern path:

```text
SVG crochet chart
  -> diagram.svg_parser (defusedxml, safety limits, transform normalisation)
  -> diagram.ir.DiagramDocument                                (versioned, distinct from StitchGraph)
  -> diagram.extraction / classification / topology              (symbol classification, circular topology inference)
  -> diagram.compiler.DiagramTopologyCompiler                     (-> existing StitchGraph, directly — see docs/svg-diagram-ingestion.md)
  -> geometry.layout.build_geometry                               (existing, unmodified)
  -> api: POST /api/visualizer/diagram/{analyse,compile}
  -> viewer: SVG diagram mode -> safe 2D review/correction -> live 3D model
```

Clean vector SVG, primarily circular/radial charts, only — see
[`docs/svg-diagram-ingestion.md`](docs/svg-diagram-ingestion.md) for the
exact supported profile and
[`docs/known-limitations.md`](docs/known-limitations.md) for what's
deliberately excluded. Raster images, photographs, and OCR remain entirely
out of scope (see `docs/written-pattern-grammar.md`'s original note, still
accurate for the raster half).

```bash
# Backend (compile API):
pip install -e ".[dev,api]"
uvicorn crochet_reconstruction.api.app:create_app --factory --reload --port 8000

# Frontend (viewer, with a live "paste pattern -> compile -> render" editor):
cd viewer
npm install
npm run dev      # http://localhost:5173
```

Paste a pattern (an example is preloaded) into the left panel and click
"Interpret and render" — no fixture file to regenerate or copy by hand.
Switch to the "SVG diagram" tab to upload or paste a clean vector SVG
crochet chart instead, review/correct the extracted symbols in the safe 2D
preview, and click "Compile to 3D." The
static `viewer/public/geometry.json` fixture still loads on startup as a
zero-backend-required demo/fallback (see
[frontend-to-backend setup](docs/frontend-backend-setup.md)) and remains
useful standalone via:

```bash
python -m crochet_reconstruction.cli generate-geometry \
  --input examples/adult_beanie_hdc.json \
  --output build/geometry_fixtures/adult_beanie_hdc/
cp build/geometry_fixtures/adult_beanie_hdc/geometry.json viewer/public/geometry.json
```

See: [Crochet IR](docs/crochet-ir-spec.md) ·
[stitch graph](docs/stitch-graph-spec.md) ·
[geometry transfer](docs/geometry-transfer-spec.md) ·
[scientific viewer](docs/scientific-viewer-spec.md) ·
[stitch geometry strategies](docs/stitch-geometry-strategies.md) ·
[yarn material and lighting](docs/yarn-material-and-lighting.md) ·
[measurement tools](docs/measurement-tools.md) ·
[annotations](docs/annotations.md) ·
[clipping and section views](docs/clipping-and-section-views.md) ·
[performance benchmarks](docs/performance-benchmarks.md) ·
[JSON Schema artefacts](docs/schema-artifacts.md) ·
[procedural-yarn milestone audit](docs/procedural-yarn-milestone-audit.md) ·
[written-pattern grammar](docs/written-pattern-grammar.md) ·
[diagnostic codes](docs/diagnostic-codes.md) ·
[compile API](docs/compile-api.md) ·
[frontend-to-backend setup](docs/frontend-backend-setup.md) ·
[open-source resource adoption](docs/open-source-resource-adoption.md) ·
[canonical JSON / RFC 8785 audit](docs/canonical-json-audit.md) ·
[known limitations](docs/known-limitations.md) ·
[**SVG diagram ingestion**](docs/svg-diagram-ingestion.md) ·
[diagram IR spec](docs/diagram-ir-spec.md) ·
[diagram symbol ontology](docs/diagram-symbol-ontology.md) ·
[diagram topology inference](docs/diagram-topology-inference.md) ·
[diagram corrections](docs/diagram-corrections.md) ·
[SVG security](docs/svg-security.md).

## Contributor submission portal (paused, not deleted)

A small, server-rendered FastAPI application that let invited crochet
contributors submit project photographs and metadata, and let an
administrator review, approve, and export the approved dataset — built for
the *previous* photo-reconstruction direction. It is no longer the active
priority (see "Project pivot" above), but nothing was deleted: the code,
tests, and docs are unchanged, and the deterministic pattern engine has
**zero dependency** on it (FastAPI, SQLAlchemy, and Pillow are behind the
`portal` extra, not the core install, and nothing in `graph`/`geometry`/
`viewer` imports from it either). See
[`docs/previous-contributor-portal-status.md`](docs/previous-contributor-portal-status.md)
for exactly what changed and why, and, if reviving it:
[portal architecture](docs/portal-architecture.md) ·
[contributor workflow](docs/portal-contributor-workflow.md) ·
[administrator workflow](docs/portal-admin-workflow.md) ·
[consent and privacy](docs/portal-consent-and-privacy.md) ·
[image storage](docs/portal-image-storage.md) ·
[deployment, backup, and production checklist](docs/portal-deployment.md) ·
[dataset export](docs/portal-dataset-export.md) ·
[known limitations](docs/portal-known-limitations.md).

## Test commands

```bash
pytest                              # full suite: engine + physical validation + portal + graph + geometry
pytest tests/unit                   # fast unit tests
pytest tests/property               # Hypothesis property-based tests
pytest tests/golden                 # reviewed example inputs/outputs (regression)
pytest tests/mutation_cases         # deliberately invalid patterns must be rejected
pytest tests/physical_validation    # trial matrix, review pack, ingestion, metrics, reporting
pytest tests/portal                 # portal domain/service/image/API tests (paused feature, still passing)
pytest tests/graph                  # stitch-graph builder + invariant tests
pytest tests/geometry               # geometry-layout tests
pytest tests/parsing                # written-pattern parser + semantic-conversion tests
pytest tests/api                    # compile API tests (written-pattern + SVG diagram)
pytest tests/diagram                # SVG diagram ingestion: security, transforms, extraction, topology, corrections, compiler, fixtures

ruff check .                    # lint
ruff format --check .           # formatting check
mypy                             # type check (strict)
```

```bash
cd viewer
npm run typecheck    # tsc --noEmit
npm run build        # production build (tsc -b && vite build)
npm test             # vitest run — unit tests + benchmark measurements (build time, raycast, interaction ops)
npm run e2e          # Playwright: compile workflow, SVG diagram workflow, lifecycle/leak stress, visual regression — real browser + backend (starts both servers itself)
```

```bash
python -m crochet_reconstruction.api.schema_export   # regenerate schemas/*.schema.json after changing StitchGraph/GeometryDocument/CompileRequest/CompileResponse/Diagnostic/Diagram*

pytest tests/test_schema_export.py          # committed schemas match the live models
pytest tests/test_frontend_type_mirror.py   # viewer/src/types/*.ts unions match the Python enums
```

## Architecture summary

```
src/crochet_reconstruction/
├── domain/               # Pydantic models: the typed vocabulary. No calculation logic.
├── templates/             # Whitelists: what a template permits (stitches, ranges, schedules).
├── engine/                # Pure Decimal math + orchestration. No I/O, no Pydantic validation logic beyond models.
├── validation/            # Rule catalogue over an already-compiled Pattern. Severity-ranked.
├── rendering/             # Pattern -> text. Reads structured fields only; no arithmetic.
├── graph/                 # Components -> explicit per-stitch StitchGraph (stable IDs, insertion targets, sequence order).
├── geometry/              # StitchGraph -> approximate 3D positions/frames (analytical, no simulation).
├── parsing/written/       # Written pattern text -> domain.rounds.Component (Lark grammar, deterministic).
├── diagram/               # SVG chart -> Diagram IR -> StitchGraph (secure parsing, ontology, topology inference, corrections).
├── api/                   # POST /api/visualizer/{compile,diagram/analyse,diagram/compile} — stateless FastAPI app, separate from portal/.
├── physical_validation/   # Phase 1.5: trial matrix, review-pack generation, result ingestion, metrics, reporting.
├── portal/                # Contributor submission portal — paused (FastAPI/SQLAlchemy/Pillow, `portal` extra).
└── cli.py                # Thin I/O wrapper: JSON in, files out.

viewer/                    # Vite + TypeScript + Three.js scientific 3D viewer (separate npm project).
├── e2e/                   # Playwright: compile-workflow, diagram-workflow, lifecycle/leak stress, visual regression.
└── tests/                 # Vitest: unit/module tests + build/raycast/interaction benchmarks.

schemas/                   # Committed, versioned JSON Schema artefacts — see docs/schema-artifacts.md.
```

The domain engine has **zero dependency** on FastAPI, a database, a
frontend framework, cloud services, or an AI provider. A web API can be
added later as a thin wrapper around `engine.compiler.compile_pattern` and
`rendering.text_renderer.render_text` without changing either.

Full formula-by-formula documentation, including every rounding policy,
tie-break rule, and supported-range decision, is in
[`docs/mathematical-assumptions.md`](docs/mathematical-assumptions.md).
Structured-format and versioning details are in
[`docs/pattern-format.md`](docs/pattern-format.md).

## Development status

**Phase 1 (deterministic engine) and Phase 1.5 (physical-validation
tooling) are complete; physical trials themselves have not been run yet.**
The engine's software tests all pass and its tooling can generate a
reviewable trial pack and evaluate submitted results — but until real
crocheters submit real results, the engine's supported ranges, crown
schedule, and tolerances remain **unvalidated against physical reality**.
See [`docs/decision-gates.md`](docs/decision-gates.md).

**The scientific 3D visualiser's first milestone is complete**: a known-valid
structured beanie pattern compiles, builds a validated stitch graph,
produces renderer-ready geometry with no invalid numeric values, and loads
in an interactive viewer supporting orbit/pan/zoom, perspective/orthographic
cameras, interior navigation, stitch selection with metadata, round
isolation, hide/opacity/clipping, and sequence-driven construction
animation, in both structural and basic-yarn modes. See
[`docs/known-limitations.md`](docs/known-limitations.md) for exactly what
that milestone does and does not cover, and
[`docs/scientific-viewer-spec.md`](docs/scientific-viewer-spec.md) for the
full design.

**Not yet done:** any category beyond rotationally-symmetric round-based
structures, constraint-relaxation geometry refinement, persistence or
export for the free-text annotations (the annotation tools themselves *are*
implemented — see [`docs/annotations.md`](docs/annotations.md) — but live
only in the browser session), the physical trials for the deterministic engine itself,
raster/photograph/OCR diagram ingestion (vector-SVG diagram ingestion *is*
implemented — see above), and anything from the original image-analysis
direction (paused — see
[`docs/previous-contributor-portal-status.md`](docs/previous-contributor-portal-status.md)).
Written-pattern parsing, a backend compile API, and graph/X-ray/path-
inspection viewer modes are all implemented (see "Stitch graph, geometry,
and the scientific 3D viewer" above) — this list is not fully current
elsewhere in this README either; treat `docs/known-limitations.md` as the
authoritative, actively maintained scope statement.

See [`docs/product-boundary.md`](docs/product-boundary.md) for review
status detail and known limitations.
