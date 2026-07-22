# Scientific 3D viewer specification

Location: `viewer/` — Vite + TypeScript + Three.js (WebGL2 baseline, no
WebGPU dependency). No React: the first slice's interaction surface (a
handful of panels driven by one geometry document) didn't justify a
state-management framework — plain TypeScript with a small pub-sub `Store`
(`src/state/store.ts`) instead.

## Directory layout

```
viewer/src/
├── app/App.ts          orchestrator: owns scene/camera/renderer, wires state -> visuals
├── scene/scene.ts       lights, background, grid/axes helpers
├── camera/camera.ts     CameraRig: perspective+orthographic, OrbitControls, view presets, focus
├── rendering/renderer.ts  WebGLRenderer setup, colour management, context-loss handling
├── geometry/            load.ts (fetch+validate), build_meshes.ts (structural), build_yarn.ts (basic yarn)
├── selection/           picking.ts (raycast -> stitch_id), highlight.ts (colour-independent marker)
├── animation/           construction.ts (sequence-driven timeline)
├── clipping/            clipping.ts (bounds-relative clipping plane)
├── state/store.ts        plain pub-sub ViewerState
├── types/geometry.ts     mirrors geometry/models.py field-for-field
└── main.ts               DOM wiring for the control panel
```

`measurement/` and `annotations/` directories exist but are intentionally
empty in this slice — both are explicitly second-vertical-slice work per
the product roadmap, not omissions.

## Semantic identity, never inferred from position

Stitches render as `THREE.InstancedMesh` — one instanced mesh per
**component** (`crown`/`body`/`brim`), sharing one capsule geometry per
group. Every instance's index maps to exactly one `stitch_id` via
`StitchInstanceGroup.stitchIds[index]`; picking (`selection/picking.ts`)
raycasts against the instanced meshes and reads `intersection.instanceId`
back through that same array — the viewer never guesses identity from
world-space position.

**Known first-slice simplification**: all stitches share one capsule size
derived from gauge, regardless of `stitch_type` (sc vs hdc render at the
same size today). Per-stitch-type dimensions are deferred to the
"stitch-specific geometry strategies" slice (see
`docs/known-limitations.md`) — this is a placeholder shape, not a claim of
stitch-accurate rendering.

## Visualisation modes implemented this slice

- **Structural** (default): instanced capsules, coloured by component, with
  increase/decrease stitches tinted separately.
- **Basic yarn**: one straight tube per yarn segment, merged per component
  via `BufferGeometryUtils.mergeGeometries` for draw-call efficiency. This
  is explicitly a placeholder — no twist detail, no loop-specific curve
  shaping, no PBR fibre material. The "realistic yarn" target from the
  product spec is second-slice work.

Graph, symbol, and X-ray modes are **not** implemented this slice (all
explicitly second-vertical-slice items per the product roadmap).

## Interaction implemented this slice

- Orbit/pan/zoom (`OrbitControls`), perspective ⇄ orthographic toggle,
  front/back/left/right/top/bottom/reset camera presets.
- No `minDistance` floor on `OrbitControls` and a small near-plane (`0.01`)
  — the camera can move inside the hollow interior of the object, per the
  "inspect from inside" requirement.
- Click-to-select a stitch; inspector panel shows type, component, round,
  sequence index, loop placement, parents, increase/decrease flags, and
  source reference; "Focus camera here" recenters on the selection.
- Selection is **never colour-only**: a wireframe torus marker is placed at
  the selected stitch's position/orientation regardless of view mode
  (colour-blind-safe, and meaningful in yarn mode where instance colour
  isn't used).
- Round isolation (dropdown of every `component:round` pair), per-component
  show/hide, global opacity slider, one clipping plane (axis + position +
  invert).
- Construction animation strictly driven by `sequence_index` — never
  spatial proximity (`animation/construction.ts`): play/pause/restart/step,
  speed control, timeline slider.
- Hidden stitches use a zero-scale instance matrix rather than removing
  them from the `InstancedMesh` — cheap, and trivially reversible without
  rebuilding geometry.

## Accessibility

Visible `:focus-visible` outlines on every control, colour-independent
selection indicator (see above), `prefers-reduced-motion` respected for
`OrbitControls` damping, high-contrast dark theme, keyboard-reachable
controls (native `<select>`/`<button>`/`<input type="range">` throughout —
no custom widgets that would need extra ARIA work).

## Known environment caveat (not an application bug)

During development, the sandboxed browser-preview tool used for automated
verification reported `document.visibilityState === "hidden"` for its tab,
which suspends `requestAnimationFrame` and throttles `ResizeObserver`
per the HTML spec — this made the render loop and the initial canvas-resize
both silently no-op inside that tool specifically. Direct JavaScript
evaluation (bypassing the animation-frame pipeline) confirmed the
underlying logic is correct: manual `handleResize()`/render calls produced
the correct canvas size and a rendered frame. **A normal, foregrounded
browser tab (i.e. any real user opening `npm run dev`) does not have this
restriction.** Two defensive improvements were still made as a result: the
`ResizeObserver` instance is now held at module scope (an unreferenced
`ResizeObserver` is eligible for garbage collection, which would be a real
bug in any browser), and an explicit double-`requestAnimationFrame`
fallback re-measures the canvas after the report layout has painted.

## Performance (measured, not claimed — `viewer/tests/benchmark.test.ts`)

On the 1640-stitch `adult_beanie_hdc` fixture: structural instanced-scene
build ≈ 16–60 ms (3 draw calls, ~88,560 triangles), basic-yarn merged-mesh
build ≈ 155–200 ms (3 merged meshes), geometry-document validation ≈ 3–15
ms, fixture JSON size ≈ 3.2 MB. Production bundle ≈ 534 KB minified / 136 KB
gzipped (mostly Three.js itself) — noted as a candidate for code-splitting
if the viewer grows, not addressed in this slice.
