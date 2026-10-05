# Known limitations — scientific 3D visualiser

Honest accounting of what this project deliberately does not do. Each was
a scope decision to prove the pipeline end-to-end on one category (and,
later, one input route) first — none were discovered too late.

## Written-pattern parser (this slice)

- **US terminology only.** No UK-terminology mapping (`dc` means different
  stitches in each system) — the compile API's `terminology` field is
  currently `Literal["US"]` for exactly this reason, not a placeholder.
- **`chain`/`slip stitch` are recognised but not convertible.** The grammar
  tokenises them (so they don't silently fail as gibberish); semantic
  conversion explicitly rejects them as `UNSUPPORTED_SYNTAX` because the
  domain model has no turning-chain/join operation type yet.
- **No row/turning semantics.** `row`/`rows` are accepted syntactically and
  compile to the same `Round`/`Component` structure as `round`/`rounds` —
  there is no turning-chain, no "wrong side"/"right side," and no directional
  reversal. A `row`-labelled section behaves identically to a `round` one.
- **Free-text phrases are not understood, by design.** "Work even," "repeat
  from *," "increase evenly," "shape as established," etc. all fail as
  `INVALID_SYNTAX` rather than being guessed — exactly as specified.
- **Only one component per pattern.** Every written pattern compiles to a
  single `ComponentKind.PIECE`; multi-piece patterns (a body plus a
  separately-worked head) have no join/assembly syntax yet.
- **Increase/decrease stitch type is inferred, not stated.** `inc`/`dec`
  don't name a stitch family in real written patterns; this parser defaults
  to the pattern's first plain stitch (`sc` if none exists) — see
  `docs/written-pattern-grammar.md`'s deterministic-assumptions list.

## SVG diagram ingestion (this slice)

See `docs/svg-diagram-ingestion.md` for the full supported-profile
statement; this section is the honest "what's deliberately not attempted"
accounting for that slice.

- **Vector SVG only, and only clean/machine-exported vector SVG.** No
  raster images, no scans, no photographs, no OCR, no computer vision
  anywhere in this pipeline — `<image>` elements are rejected outright by
  the security layer, not merely unsupported.
- **Circular/radial construction only.** `ConstructionMode.ROW` exists in
  the schema (forward-compatible slot) but is always rejected with
  `UNSUPPORTED_CHART_CONSTRUCTION` — no row/flat-panel chart interpretation
  exists yet.
- **One primary connected component, by model, not just by convention.**
  Centre detection has no concept of "multiple charts in one file" — two
  separate motifs (e.g. two magic rings) trigger `AMBIGUOUS_CENTRE` and
  the first one found wins; the second motif's stitches get incorrectly
  projected relative to the first motif's centre rather than being
  recognised as a separate component. `compiler.py`'s
  `_find_unreachable`/`DISCONNECTED_COMPONENT` check exists as a defensive
  backstop (and is unit-tested directly,
  `tests/diagram/test_compiler.py::test_find_unreachable_detects_orphaned_parent_chain`)
  but this slice's own proportional-projection topology algorithm always
  guarantees reachability by construction for a genuinely single-centre
  chart — it cannot, by itself, detect "this SVG actually contains two
  unrelated motifs" the way a human looking at the image would.
- **Bounded symbol vocabulary.** magic ring, chain, slip stitch, single/
  half-double/double crochet, increase, decrease, join — see
  `docs/diagram-symbol-ontology.md`. Treble crochet, picot, puff stitch,
  bobble, cluster, front/back post, and complex lace symbols are reserved
  vocabulary slots that always produce `UNSUPPORTED_SYMBOL`, never a
  guessed mapping.
- **`chain`/`slip_stitch`/`join` never become their own `StitchNode`.**
  They're converted into the existing `into_ring`/`round_closure`
  mechanisms. A chart symbol using `chain` or `slip_stitch` as an ordinary
  mid-round worked stitch (not a foundation or closure) is filtered out by
  `is_worked_stitch()` and simply doesn't appear in the compiled graph —
  no diagnostic currently flags this specific case, since it's outside the
  bounded circular-chart profile this slice targets.
- **Text-label association is implemented, but deliberately conservative.**
  A free-standing `<text>` naming a stitch type now classifies the symbol it
  is unambiguously nearest to (`diagram/text_labels.py`,
  `docs/diagram-symbol-ontology.md`). It only fires when the label is within
  1.5 symbol-diagonals *and* symbol and label are mutually nearest by a 1.5×
  margin — a label sitting midway between two symbols classifies neither,
  and every rejection falls through to the geometry heuristic or to
  unclassified rather than guessing. Charts whose labels sit further away
  than that, or in a dense layout where several labels compete, still get
  unclassified symbols requiring a correction.
- **A chart's own printed round labels are still not parsed.** Text that
  doesn't name a stitch type (`3`, `18 sts`, `Round 4`) is ignored by the
  association above rather than used to seed or validate round numbering —
  see the separate bullet on `data-round` metadata below.
- **Primitive-geometry classification is calibrated to this project's own
  synthetic fixture convention** (symbols authored on roughly a
  10-local-unit box), not a general shape recognizer — a chart using
  differently-proportioned artwork with no metadata will get more
  `unclassified`/`ambiguous` results than one using this project's
  convention or explicit metadata. This is documented, bounded behaviour,
  not a bug to fix by loosening thresholds and guessing harder.
- **Magic-ring/chain-ring centre detection by shape alone is not
  attempted.** Distinguishing a centre ring from an ordinary chain loop by
  geometry would require already knowing the centre — circular reasoning.
  A chart with no explicit centre metadata gets a geometric-centroid
  estimate instead (lower confidence, `centre_method: geometric_estimate`),
  which works for typical charts but is not equivalent to true centre
  detection.
- **`SymbolOverride.sequence_index` reorders within a round, not across
  rounds.** It's applied as a bounded reinsertion into the symbol's
  already-inferred round order (`topology._apply_sequence_pins`), clamped
  to that round's valid index range — moving a symbol to a different round
  is `round_index`'s job, not `sequence_index`'s. This is the safe, bounded
  version of the correction (round membership and angular ordering stay
  governed by topology inference; only within-round position is
  user-overridable) rather than an unconstrained global ordinal, which
  would let a correction silently violate round clustering. See
  `docs/diagram-corrections.md`.
- **`NON_ADJACENT_DECREASE_PARENTS` is a warning, not a blocking error** —
  an explicit connector or correction can legitimately produce a
  non-contiguous decrease (e.g. an unusual stitch pattern); this slice
  flags it for review rather than assuming it's always wrong.
- **Round labels/stitch counts in the SVG are not yet used to validate or
  seed round numbering** beyond per-symbol `data-round` metadata — a
  chart's own printed "Round 3 (18 sts)" text label is not parsed.
- **No garment schematics, no freeform lace, no arbitrary hand-drawn
  charts** — explicitly excluded by the brief, not attempted.

## Compile API and viewer integration (this slice)

- **No raster image input.** Written patterns and clean vector SVG charts
  are supported (see "SVG diagram ingestion" above); photos, scans and PDFs
  of charts are not.
- **No persistence.** The API never writes submitted patterns to disk and
  has no database; closing the tab loses the current pattern text (the
  textarea itself has no autosave).
- **Single clipping plane (numeric entry + reset added).** Five measurement
  kinds are now implemented (`docs/measurement-tools.md`) and free-text
  annotations are now implemented (`docs/annotations.md`) — both halves of
  this limitation are resolved; only the single-clipping-plane restriction
  remains. Annotations are in-memory only: no persistence, no export, no
  backend representation, cleared on recompile.
- **`options.strict` defaults to `false`.** The API honours it on all three
  endpoints (`docs/compile-api.md`'s "Strict mode") and the viewer exposes it
  as a single toggle shared by both input modes. Its default was **changed
  from `true` to `false`** when it was implemented, so that turning a
  documented no-op into real behaviour could not silently start failing
  existing callers; a client that previously sent `strict: true` expecting
  nothing to happen now gets strict blocking.
- **E2E coverage is 16 tests across four files**, not a full interaction
  matrix — `viewer/e2e/compile-workflow.spec.ts` (2 tests: the original
  compile scenario, plus an extended scenario covering yarn mode, path
  inspection, X-ray, clipping, all five measurement kinds, quality change,
  and recompile-disposal), `viewer/e2e/lifecycle-stress.spec.ts` (2 tests:
  repeated-recompile resource-leak checks),
  `viewer/e2e/diagram-workflow.spec.ts` (3 tests: analyse/correct/compile/
  select through the real backend, malicious-SVG rejection preserving the
  last valid model, and written-pattern-mode non-interference), and
  `viewer/e2e/visual-regression.spec.ts` (see
  `docs/performance-benchmarks.md` and this file's "Viewer" section
  below for its own documented scope reduction). Some camera-preset and
  animation-timeline interactions during a live compile session are still
  covered only by Vitest unit tests and manual verification, not by
  Playwright.
- **This project's dev machine has been measured with under 1GB free
  physical memory even at idle** (8GB total RAM; `Get-CimInstance
  Win32_OperatingSystem` showed ~370-650MB `FreePhysicalMemory` across
  several full-suite runs, with zero leaked `node`/`python`/Chromium
  processes after each run — confirmed via `tasklist`). Under this
  constraint, a full serial (`workers: 1`) Playwright run has been observed
  to intermittently exceed a 15s backend-response wait on real
  compile/analyse round trips — not a hang, not a code defect, and not
  always the same test each run (observed hitting
  `compile-workflow.spec.ts`, `diagram-workflow.spec.ts`,
  `lifecycle-stress.spec.ts`, and `visual-regression.spec.ts` on different
  runs). The response-wait timeout for every real backend round trip in
  e2e specs was raised from 15s to 45s (`BACKEND_ROUND_TRIP_TIMEOUT`,
  documented inline in each spec) to absorb this — a bounded, justified
  increase, not blind timeout inflation, since the assertions themselves
  are unchanged and the wait is for a real network response with no
  cheaper deterministic readiness signal available. Two of
  `viewer/tests/benchmark.test.ts`'s hard-coded timing-threshold
  assertions (raycast elapsed-ms budgets) have also been observed to fail
  under the same memory pressure; these are pre-existing performance
  budgets, not diagram-slice code, and were not loosened — a full green
  Playwright/Vitest run on this machine is not fully reproducible on
  demand, and re-running individual suites in isolation (rather than
  everything concurrently) reliably passes.

## Geometry accuracy

- **Stitch dimensions are stitch-type-specific in yarn mode only.**
  `geometry/stitch_paths/` (see `docs/stitch-geometry-strategies.md`) gives
  sc/hdc/dc visibly different post height and wrap count in yarn mode.
  **Structural mode still renders every stitch at one capsule size**
  regardless of `stitch_type` — this was a deliberate choice to keep
  structural mode as a fast, uniform overview (see
  `docs/scientific-viewer-spec.md`'s "Known simplification, structural mode
  only"), not an oversight.
- **Stitch position is now stitch-type-specific vertically, but only
  vertically, and on a provisional ratio.** A round's spacing is scaled by
  its dominant stitch family relative to `Gauge.stitch_family`
  (`geometry/stitch_heights.py`), so a `dc` round is spaced further than an
  `sc` round at the same round gauge — the previous "a `dc`-heavy round is
  not spaced any further apart than an `sc`-heavy one" limitation is
  resolved. Three real caveats remain:
  - **The ratios are the standard turning-chain convention (`sc` 1 / `hdc`
    2 / `dc` 3), not measured fabric proportions, and await crochet-expert
    approval** in the sense of `docs/decision-gates.md`. Real worked `dc` is
    commonly shorter than three times an `sc`. Every document whose spacing
    they actually affect carries a warning saying so.
  - **A round is placed at one `z`, characterised by its dominant family.**
    A round genuinely mixing `sc` and `dc` gets one height, not per-stitch
    heights — within-round vertical variation is not modelled at all.
  - **Radius and angular placement are still family-independent.** Only
    height responds to stitch type; a `dc` round's radius still comes from
    stitch count and stitch gauge alone.
  Yarn mode's per-type visual differences (post height, wrap count) remain
  separate and still cosmetic: a locally-varying curve between a visually-
  lowered "attach" point and the stitch's real, backend-computed position.
- **Crown dome shape is a visual heuristic** (hemispherical cap sized at
  60% of crown radius), not derived from the actual increase schedule's
  curvature. It looks like a crown; it is not a claim about the real one.
- **No constraint relaxation.** Positions come from closed-form trigonometry
  only — no spring/curve-length constraints, no collision avoidance, no
  position-based dynamics. Yarn-mode tubes can visibly self-intersect at
  tight increase/decrease points for exactly this reason (no collision
  avoidance pass runs over the generated tube geometry) — this is a known,
  unfixed visual artifact, not something the strategy system attempts to
  prevent. The data model doesn't preclude adding a relaxation pass later
  as a refinement over the same positions.
- **Yarn diameter is a visual default** (half a stitch width from gauge),
  not a measured or user-entered yarn property.
- **Loop placement (front/back loop only) is an approximate lateral offset**
  in yarn mode, not an anatomically modelled loop — no strategy in this
  codebase has ever modelled two anatomically distinct loops, so every
  non-`both` request is a fallback by construction. This is now tracked
  as structured data, not just a warning string:
  `StitchPathResult.loopAttachment` (`{ requested, resolved, exact }`,
  completion-audit addition) records `exact: false` for every such case,
  surfaced in the inspector's "Resolved attachment"/"Exact attachment"
  rows in addition to the existing `#yarn-warnings` free-text warning — see
  `docs/stitch-geometry-strategies.md`.
- All dimensional outputs are **estimates**, and are labelled as such in the
  viewer — never presented as measurements of a physical object. This now
  explicitly includes the measurement tool's own readings (labelled
  `"cm (approx.)"` in the UI) — see `docs/measurement-tools.md`.
- **Geometry floats are not bit-identical across operating systems; the
  geometry fingerprint is stabilised, not exact.** Windows UCRT and glibc
  libm disagree by one ulp on some `sin`/`hypot` results (≈1e-15 cm), so the
  raw `geometry.json` payload differs in a few last digits between Windows
  and the Linux API image. `geometry_fingerprint` hashes floats rounded to
  9 decimal places (1e-9 cm) to absorb this, so it matches across platforms
  in every tested case — but a value lying within one ulp of a rounding
  boundary could still split it. Clients recomputing the fingerprint must
  apply the same quantisation. See `docs/canonical-json-audit.md`,
  "Cross-platform float stability".

## Category and vocabulary

- **Only rotationally symmetric round-based structures** (the existing
  top-down beanie's crown/body/brim) have a layout strategy. Flat
  rectangles, tubes, spheres, amigurumi, granny squares, motifs, and
  assembly/seams are explicitly future work — the architecture separates
  generic graph/geometry schemas from category-specific layout strategies
  precisely so a new strategy module can be added without touching this one.
- **Stitch vocabulary**: magic ring, chain-free continuous rounds, sc, hdc,
  increase, decrease, front/back/both loop placement. No dc, no slip
  stitch, no turning chains, no colour changes (Phase 1's engine doesn't
  generate any of these yet either — this milestone didn't add graph/
  geometry support beyond what the engine can already produce).

## Input routes

Three input routes now exist: structured JSON fixtures (the original
static `viewer/public/geometry.json`), written-pattern text
(`POST /api/visualizer/compile`), and SVG diagram charts
(`POST /api/visualizer/diagram/analyse` + `.../compile`, this slice — see
`docs/svg-diagram-ingestion.md`). Raster/photograph/PDF/OCR input remains
entirely unimplemented — see the "SVG diagram ingestion" section above for
the diagram route's own bounded scope.

## Viewer

- **Visualisation modes**: structural, crochet-specific yarn (procedural
  per-stitch geometry, not the earlier straight-tube placeholder), X-ray,
  a one-hop graph overlay, and a semantic path-inspection mode (role-
  coloured yarn segments, focus-by-role — `selection/path_inspection.ts`,
  completion-audit addition) are all implemented. A full symbol-chart mode
  remains unimplemented — out of scope for this slice (chart rendering is a
  distinct pipeline stage, see `docs/open-source-resource-adoption.md`'s
  "Crochet Charts" entry).
- **Measurement tools are implemented**: arbitrary point-to-point, stitch-
  to-stitch, object width, object height, and selected-round circumference
  (see `docs/measurement-tools.md`), including disposal on recompile and
  across a repeated-recompile stress test
  (`viewer/e2e/lifecycle-stress.spec.ts`). **Free-text annotations are now
  implemented** (`docs/annotations.md`): stitch- or point-anchored notes with
  create/edit/remove, wireframe scene markers, and the same
  clear-on-recompile disposal — in-memory only, with no persistence or
  export.
- **No level-of-detail system** — one fixed geometry resolution per quality
  preset, regardless of camera distance or selection state. Quality presets
  (`docs/yarn-material-and-lighting.md`) are a coarse, user-chosen global
  knob, not an automatic LOD system.
- **Yarn-mode tube meshes can self-intersect** at tight increase/decrease
  points — no collision-avoidance or relaxation pass runs over the
  generated geometry (see "Geometry accuracy" above).
- **Yarn-mode raycasting cost is fixed (SVG diagram ingestion slice)**:
  previously measured at ~35-45x structural mode's raycast cost on the
  reference fixture; `App.pickStitch` now raycasts against invisible
  low-poly hit-proxy spheres (`selection/hit_proxies.ts`) in every view
  mode instead, measured at ~9-11ms per sweep — faster than even the
  structural-mode raycast, and no longer dependent on yarn tube triangle
  count at all. See `docs/open-source-resource-adoption.md`'s "Three.js
  raycasting" entry for the full before/after numbers. `three-mesh-bvh`
  remains deferred, now because the measured problem was already solved
  by a simpler mechanism, not just because it wasn't measured yet. Proxies
  are sized slightly larger than the visible geometry for a comfortable
  click target, so in densely packed regions the picked stitch can
  occasionally be an angularly adjacent one rather than bit-for-bit what a
  pixel-exact raycast would report — a deliberate UX trade-off, not a bug.
- **Yarn fuzz was evaluated and explicitly not implemented** — see
  `docs/yarn-material-and-lighting.md`'s "Yarn fuzz" section for the
  five-option comparison and the reasoning (every geometry-based option
  would compound the raycast-cost limitation above).
- **Single clipping plane**, not multiple — evaluated and deferred, see
  `docs/clipping-and-section-views.md`. No visible clip-plane helper mesh,
  same document.
- **Production bundle is now one ~572 KB chunk / 146 KB gzipped**
  (`npm run build`, re-measured after the completion audit; was ~534 KB/136 KB
  before the original stitch-geometry slice, ~562 KB/144 KB after it). Still
  one chunk, not code-split; the growth across both slices is this
  project's own new code (path-inspection, measurement types, clipping
  UI), not a new dependency (no runtime dependency was added — see
  `docs/open-source-resource-adoption.md`).
- **Desktop-first.** A responsive CSS breakpoint exists, but touch-specific
  interaction (pinch-zoom, touch-drag orbit) has not been tuned or tested.

## Verification caveat

Automated visual verification in this session ran inside a sandboxed
browser-preview tool whose tab reported `document.visibilityState ===
"hidden"`, which suspends `requestAnimationFrame` and throttles
`ResizeObserver` — see `docs/scientific-viewer-spec.md`'s "Known
environment caveat" section for the full explanation and how correctness
was instead confirmed via direct JavaScript evaluation, `tsc`/`vite build`,
and the Vitest suite. A real, foregrounded browser tab does not have this
restriction; a human should still confirm the interactive experience via
`npm run dev` before treating this as fully visually verified.

## What was intentionally not built (per the brief's scope exclusions)

Photograph-to-pattern reconstruction, stitch recognition from photos,
crochet-vs-knitting image classification, contributor image-dataset
collection, web scraping, measurement estimation from photos, hidden-stitch
reconstruction, large image-recognition model training, the contributor
submission portal (paused, not deleted — see
`docs/previous-contributor-portal-status.md`), Supabase/Vercel migration,
full finite-element or fibre simulation, every crochet stitch, complex
garments/lace/assembly, mobile apps, VR, multiplayer, AI-generated final
geometry without deterministic structure, and automatic redistribution of
uploaded patterns.

Additionally excluded from the written-pattern compile slice: raster image
parsing, OCR, machine learning of any kind, full yarn physics, XPBD
relaxation, path tracing, WebGPU-specific rendering, a redesign of the
existing graph/geometry architecture (the existing `StitchGraph`/
`GeometryDocument` schemas were reused unmodified — only their
producer-function signatures were narrowed to drop an unnecessary
beanie-`Pattern` dependency), user accounts, a pattern marketplace, and
cloud storage.

**Update (SVG diagram ingestion slice)**: clean vector SVG diagram
recognition is now implemented (see the "SVG diagram ingestion" section
above and `docs/svg-diagram-ingestion.md`) — the "future diagram pipeline"
note below is superseded for the vector-SVG half; the raster half remains
exactly as deferred as before:
`raster preprocessing with OpenCV -> optional learned symbol detection
(Detectron2/MMDetection, only once a licensed annotated dataset exists) ->
canonical Diagram IR -> existing StitchGraph pipeline` — see
`docs/open-source-resource-adoption.md` for the OpenCV/Detectron2
evaluation and why both remain deferred.
