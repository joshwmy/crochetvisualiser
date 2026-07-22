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

## Compile API and viewer integration (this slice)

- **No diagram/image input.** Text only — SVG/raster chart parsing remains
  fully deferred (see the "future diagram pipeline" section below).
- **No persistence.** The API never writes submitted patterns to disk and
  has no database; closing the tab loses the current pattern text (the
  textarea itself has no autosave).
- **Single clipping plane, no annotation tools.** Point-to-point measurement
  is now implemented (`docs/measurement-tools.md`) — the "no measurement"
  half of this limitation is resolved; free-text annotations remain
  unbuilt (`annotations/` is still an empty placeholder directory).
- **`options.strict` has no effect yet** — accepted by the API and typed in
  the schema, reserved for a future stricter-diagnostics mode, not silently
  dropped but also not yet implemented.
- **E2E coverage is two workflow tests**, not a full interaction matrix —
  `viewer/e2e/compile-workflow.spec.ts` covers the original 11-step compile
  scenario plus a second 12-step scenario (yarn mode, X-ray, clipping,
  measurement, quality change, recompile-disposal — see
  `docs/scientific-viewer-spec.md`'s interaction pipeline diagram); some
  camera-preset and animation-timeline interactions during a live compile
  session are still covered only by Vitest unit tests and manual
  verification, not by Playwright.

## Geometry accuracy

- **Stitch dimensions are stitch-type-specific in yarn mode only.**
  `geometry/stitch_paths/` (see `docs/stitch-geometry-strategies.md`) gives
  sc/hdc/dc visibly different post height and wrap count in yarn mode.
  **Structural mode still renders every stitch at one capsule size**
  regardless of `stitch_type` — this was a deliberate choice to keep
  structural mode as a fast, uniform overview (see
  `docs/scientific-viewer-spec.md`'s "Known simplification, structural mode
  only"), not an oversight.
- **Stitch position itself is still not stitch-type-specific.** Yarn mode's
  per-type visual differences (post height, wrap count) are drawn as a
  locally-varying curve between a visually-lowered "attach" point and the
  stitch's real, backend-computed position — the position itself still
  comes from the same uniform-row-height layout regardless of `sc`/`hdc`/
  `dc`. A `dc`-heavy round is not spaced any further apart than an
  `sc`-heavy one of the same stitch count. This is a real geometric
  simplification, not resolved by the new yarn-mode visuals, which are
  cosmetic curve shape only.
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
  in yarn mode, not an anatomically modelled loop — see
  `docs/stitch-geometry-strategies.md`'s sc/hdc/dc section. Each such stitch
  carries a warning to this effect, surfaced in `#yarn-warnings`, rather
  than silently rendering as if it were exact.
- All dimensional outputs are **estimates**, and are labelled as such in the
  viewer — never presented as measurements of a physical object. This now
  explicitly includes the measurement tool's own readings (labelled
  `"cm (approx.)"` in the UI) — see `docs/measurement-tools.md`.

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

- **Structured JSON only.** Written-pattern parsing and diagram recognition
  are unimplemented — explicitly excluded from this milestone per the
  brief ("Do not begin with broad natural-language parsing or computer
  vision").
- **No backend API endpoint.** The viewer loads a static geometry JSON
  fixture (`viewer/public/geometry.json`, generated via the CLI). A
  `/api/render/compile` endpoint is second-slice-adjacent work, not
  required by this milestone's completion criteria.

## Viewer

- **Visualisation modes**: structural, crochet-specific yarn (procedural
  per-stitch geometry, not the earlier straight-tube placeholder), X-ray,
  and a one-hop graph overlay are all implemented. A full symbol-chart mode
  remains unimplemented — out of scope for this slice (chart rendering is a
  distinct pipeline stage, see `docs/open-source-resource-adoption.md`'s
  "Crochet Charts" entry).
- **Measurement tools are implemented** (point-to-point / stitch-to-stitch
  distance; see `docs/measurement-tools.md`), including disposal on
  recompile. **Free-text annotations remain unbuilt** —
  `annotations/` is still an empty placeholder directory.
- **No level-of-detail system** — one fixed geometry resolution per quality
  preset, regardless of camera distance or selection state. Quality presets
  (`docs/yarn-material-and-lighting.md`) are a coarse, user-chosen global
  knob, not an automatic LOD system.
- **Yarn-mode tube meshes can self-intersect** at tight increase/decrease
  points — no collision-avoidance or relaxation pass runs over the
  generated geometry (see "Geometry accuracy" above).
- **No raycast-time benchmark for yarn mode** — only build time and
  triangle count are measured (`docs/yarn-material-and-lighting.md`); if
  picking latency is ever reported as a problem, `three-mesh-bvh` is the
  natural next step (see `docs/open-source-resource-adoption.md`'s
  re-evaluation).
- **Single clipping plane**, not multiple.
- **Production bundle is now one ~562 KB chunk / 144 KB gzipped**
  (`npm run build`, re-measured this slice; was ~534 KB/136 KB before the
  new materials/geometry/measurement/selection code). Still one chunk, not
  code-split; the ~28 KB/8 KB gzipped growth is this slice's new code, not
  a new dependency (no runtime dependency was added — see
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

Additionally excluded from the written-pattern compile slice: crochet
diagram/chart recognition, raster image parsing, OCR, machine learning of
any kind, full yarn physics, XPBD relaxation, path tracing, WebGPU-specific
rendering, a redesign of the existing graph/geometry architecture (the
existing `StitchGraph`/`GeometryDocument` schemas were reused unmodified —
only their producer-function signatures were narrowed to drop an
unnecessary beanie-`Pattern` dependency), user accounts, a pattern
marketplace, and cloud storage. The future diagram pipeline remains:
`SVG diagram parsing -> raster preprocessing with OpenCV -> optional learned
symbol detection -> canonical Component/StitchGraph -> existing geometry
pipeline` — see `docs/open-source-resource-adoption.md` for the OpenCV/
Detectron2 evaluation and why both remain deferred.
