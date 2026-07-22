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
- **Single clipping plane, no measurement/annotation tools** — unchanged
  from the previous milestone; this slice didn't touch viewer features
  beyond the compile/load/dispose path.
- **`options.strict` has no effect yet** — accepted by the API and typed in
  the schema, reserved for a future stricter-diagnostics mode, not silently
  dropped but also not yet implemented.
- **E2E coverage is one workflow test**, not a full interaction matrix —
  `viewer/e2e/compile-workflow.spec.ts` covers the brief's specific 11-step
  scenario; camera/clipping/animation interactions during a live compile
  session are covered by Vitest unit tests and the previous milestone's
  manual verification, not by Playwright.

## Geometry accuracy

- **Stitch dimensions are not stitch-type-specific.** `sc` and `hdc` render
  at the same capsule size today; only a coarse `short`/`medium` height
  *category* exists on the graph node, unused by the geometry layer yet.
  Deferred to the "stitch-specific geometry strategies" slice.
- **Crown dome shape is a visual heuristic** (hemispherical cap sized at
  60% of crown radius), not derived from the actual increase schedule's
  curvature. It looks like a crown; it is not a claim about the real one.
- **No constraint relaxation.** Positions come from closed-form trigonometry
  only — no spring/curve-length constraints, no collision avoidance, no
  position-based dynamics. The data model doesn't preclude adding this
  later as a refinement pass over the same positions.
- **Yarn diameter is a visual default** (half a stitch width from gauge),
  not a measured or user-entered yarn property.
- All dimensional outputs are **estimates**, and are labelled as such in the
  viewer — never presented as measurements of a physical object.

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

- **Visualisation modes**: only structural and basic yarn are implemented.
  Graph, symbol, and X-ray modes are unimplemented (all explicitly listed
  as second-vertical-slice work in the product roadmap).
- **No measurement or annotation tools yet** — both directories exist as
  placeholders; both are second-slice items per the roadmap.
- **No level-of-detail system** — one fixed geometry resolution regardless
  of camera distance or selection state.
- **Single clipping plane**, not multiple.
- **Production bundle is one ~534 KB chunk** (mostly Three.js). Not
  code-split; fine for a local single-page tool, would want
  `manualChunks`/dynamic import if the viewer grows.
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
