# Known limitations — scientific 3D visualiser (first milestone)

Honest accounting of what this milestone deliberately does not do. Each was
a scope decision to prove the graph→geometry→viewer pipeline end-to-end on
one category first, per the brief's explicit "narrow the first category,
prove the pipeline" instruction — none were discovered too late.

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
