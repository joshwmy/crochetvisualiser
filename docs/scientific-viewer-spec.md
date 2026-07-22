# Scientific 3D viewer specification

Location: `viewer/` — Vite + TypeScript + Three.js (WebGL2 baseline, no
WebGPU dependency). No React: the first slice's interaction surface (a
handful of panels driven by one geometry document) didn't justify a
state-management framework — plain TypeScript with a small pub-sub `Store`
(`src/state/store.ts`) instead.

## Directory layout

```
viewer/src/
├── app/App.ts             orchestrator: owns scene/camera/renderer, wires state -> visuals,
│                           picking dispatch (structural vs. yarn), measurement click flow
├── scene/scene.ts          lights, background, grid/axes helpers, 3 lighting presets
├── camera/camera.ts        CameraRig: perspective+orthographic, OrbitControls, view presets, focus
├── rendering/renderer.ts   WebGLRenderer setup, colour management, context-loss handling
├── geometry/
│   ├── load.ts             fetch + validate GeometryDocument
│   ├── build_meshes.ts     structural mode: one InstancedMesh per component
│   ├── build_yarn_paths.ts yarn mode: per-stitch strategy dispatch -> tube geometry -> merge
│   ├── parallel_transport_tube.ts  rotation-minimizing frames + tube mesh builder
│   └── stitch_paths/       StitchPathStrategy system — see docs/stitch-geometry-strategies.md
├── materials/yarn_material.ts   MeshPhysicalMaterial preset, semantic colors, x-ray opacity
├── selection/
│   ├── picking.ts          structural raycast -> instanceId -> stitch_id
│   ├── highlight.ts        colour-independent selection marker (wireframe torus)
│   ├── graph_overlay.ts    one-hop StitchGraph edge overlay for the selected stitch
│   └── path_inspection.ts  role-coloured semantic path-inspection render (yarn mode)
├── measurement/
│   ├── types.ts             Measurement tagged union (5 kinds) — see docs/measurement-tools.md
│   └── measurement.ts       one create*Measurement() function per kind + line-overlay builder
├── animation/construction.ts    sequence-driven construction timeline
├── clipping/clipping.ts    bounds-relative clipping plane (THREE.Plane + material.clippingPlanes) — see docs/clipping-and-section-views.md
├── state/store.ts          plain pub-sub ViewerState (measurements, clipping, path-mode/role-focus, quality, xray, ...)
├── types/geometry.ts       mirrors geometry/models.py field-for-field
└── main.ts                 DOM wiring for the control panel
```

`annotations/` remains intentionally empty — free-text annotations (as
opposed to structured measurements, which are now implemented) are still
explicitly future work.

## Pipeline diagrams

### 1. Data pipeline: pattern text to rendered scene

```
Written pattern text
        |
        v   Lark grammar (parsing/written/grammar.lark)
Parsed syntax tree
        |
        v   semantic conversion (parsing/written/parser.py)
Pattern (domain IR)  <-------------------- structured JSON input (alternate route)
        |
        v   graph/builder.py
StitchGraph (nodes, edges, fingerprinted)
        |
        v   geometry/layout.py, rotational_rounds.py
GeometryDocument (positions, orientations, radius; fingerprinted)
        |
        +---------------------------------------+
        |                                        |
        v  structural mode                       v  yarn mode
  build_meshes.ts                          stitch_paths/ (per-stitch strategy
  InstancedMesh per component               dispatch — see stitch-geometry-
        |                                    strategies.md)
        |                                          |
        |                                          v
        |                                    StitchPathResult
        |                                    (segments, roles, warnings)
        |                                          |
        |                                          v  parallel_transport_tube.ts
        |                                    tube geometry per segment,
        |                                    swept at the active quality preset
        |                                          |
        |                                          v
        |                                    merged mesh per component
        |                                          |
        +--------------------+--------------------+
                              v
                    THREE.Scene: materials (yarn_material.ts),
                    lighting preset (scene.ts), clipping planes
                    (clipping.ts), x-ray opacity (applyYarnMaterialState)
                              |
                              v
                    WebGLRenderer -> canvas
```

### 2. Interaction pipeline: click to inspection/measurement

```
pointer click on canvas
        |
        v
App.pickStitch()
   structural -> Picker.pick(): raycast InstancedMesh, read instance.instanceId
   yarn       -> App.pickYarn(): raycast merged component mesh, stitchIdForFace()
        |
        v
stitchId (or null if the raycast missed)
        |
        +-- measurement mode inactive --> store.set({ selectedStitchId: stitchId })
        |
        +-- measurement mode active
                 |
                 +-- no stitch pending yet --> store.set({
                 |         pendingMeasurementStitchId: stitchId,
                 |         selectedStitchId: stitchId })       (inspector still updates)
                 |
                 +-- a different stitch is pending --> measureDistance(doc, pending, stitchId)
                           store.set({ measurements: [...prev, result],
                                       pendingMeasurementStitchId: null })
        |
        v
store notifies subscribers
        |
        +--> highlighter.select(...)          wireframe torus at the selected stitch
        +--> wireInspector() DOM update        #inspector-content <dl> (type, parents, ...)
        +--> graph_overlay rebuild (if on)     one-hop StitchGraph edges from the selection
        +--> measurement list + line rebuild   #measurement-list <li> + dashed THREE.Line
        +--> path-inspection rebuild (if on)   role-coloured segments for the selection
```

Diagram simplified for readability — two details not drawn above: (1) when
`measurementPointMode` is true, the flow skips `pickStitch()` entirely and
uses `App.raycastPoint()`'s raw hit point instead, recording a
`point_distance` measurement rather than a `stitch_distance` one; (2)
`applyClipping` runs once more after every one of the four `-->` rebuilds
above, since the graph overlay/measurement line objects are rebuilt fresh
on every store update and need clipping (re-)applied to the new objects,
not the disposed previous ones — see
`docs/clipping-and-section-views.md`.

## Semantic identity, never inferred from position

Stitches render as `THREE.InstancedMesh` — one instanced mesh per
**component** (`crown`/`body`/`brim`), sharing one capsule geometry per
group. Every instance's index maps to exactly one `stitch_id` via
`StitchInstanceGroup.stitchIds[index]`; picking (`selection/picking.ts`)
raycasts against the instanced meshes and reads `intersection.instanceId`
back through that same array — the viewer never guesses identity from
world-space position.

**Known simplification, structural mode only**: all stitches share one
capsule size derived from gauge, regardless of `stitch_type` (sc vs hdc
render at the same size today) — this is a placeholder shape, not a claim
of stitch-accurate rendering. The "stitch-specific geometry strategies"
work this simplification was originally deferred to has since landed, but
**in yarn mode only** (`geometry/stitch_paths/`, see
`docs/stitch-geometry-strategies.md`) — sc/hdc/dc do render with visibly
different post height and wrap count there. Structural mode was left
unchanged deliberately: it exists specifically as a fast, uniform overview
representation, and giving it per-stitch-type capsule shapes would blur
that distinction from yarn mode's detailed rendering without a measured
need for it.

## Visualisation modes

- **Structural** (default): instanced capsules, coloured by component, with
  increase/decrease stitches tinted separately. One fixed capsule size per
  gauge — still not stitch-type-specific (see "Known first-slice
  simplification" above; unchanged by the yarn-mode work below, since that
  work is entirely additive in a separate mode).
- **Yarn (crochet-specific)**: per-stitch procedural yarn-path geometry —
  see `docs/stitch-geometry-strategies.md` for the strategy system and
  `docs/yarn-material-and-lighting.md` for the material/quality-preset
  details. Replaces the earlier "basic yarn" placeholder (straight tubes
  with no loop-specific shaping) entirely; the old `build_yarn.ts` module
  was deleted rather than kept alongside the new `build_yarn_paths.ts`, per
  this project's "no half-finished/duplicate implementations" convention.
- **X-ray mode**: caps yarn-material opacity at 0.22 regardless of the
  opacity slider (`applyYarnMaterialState`), letting internal structure
  (e.g. a hidden decrease bridge) show through the surrounding yarn.
- **Graph overlay**: a one-hop `StitchGraph` edge overlay
  (`selection/graph_overlay.ts`) for the currently selected stitch only —
  never the whole graph — colour-coded by edge type (insertion, horizontal
  neighbour, yarn sequence, round closure), with a text legend
  (`#graph-overlay-legend`) so the colours are never the only way to tell
  edge types apart. Toggled independently of view mode and X-ray.
- **Path-inspection mode** (`selection/path_inspection.ts`, completion-audit
  addition): shows only the selected stitch's semantic yarn-path segments,
  coloured per role, with an optional dimmed render of the immediate
  parent/next-in-sequence stitch for context — never every stitch in the
  model. `#path-role-select` doubles as "highlight all" (blank option) and
  "focus one role"; `#path-clear-focus` resets to highlight-all. The
  inspector's "Path role in focus" row and `#path-role-legend`'s text
  labels mean no part of this mode communicates a role by colour alone. See
  `docs/stitch-geometry-strategies.md` for the role vocabulary.

Symbol-chart mode remains unimplemented (out of this slice's scope — see
`docs/known-limitations.md`).

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
  show/hide, global opacity slider, one clipping plane (axis, slider *and*
  numeric-entry position kept mirrored, invert, reset button) — the
  clipping plane applies to structural/yarn geometry and to the graph
  overlay/measurement lines; the selection marker and path-inspection
  overlay deliberately do not, so the current selection is never hidden by
  a clip plane — see `docs/clipping-and-section-views.md` for the full,
  explicit policy and its verification hook.
- Construction animation strictly driven by `sequence_index` — never
  spatial proximity (`animation/construction.ts`): play/pause/restart/step,
  speed control, timeline slider.
- Hidden stitches use a zero-scale instance matrix rather than removing
  them from the `InstancedMesh` — cheap, and trivially reversible without
  rebuilding geometry.
- **Measurement tools**: five kinds — arbitrary point-to-point, stitch-to-
  stitch, object width, object height, and selected-round circumference —
  each a `Measurement` union record (`measurement/types.ts`) with a
  `label`/`valueCm`/`unit`/`approximate` flag rather than a hardcoded
  display string. Point/stitch distances render as a dashed line; the three
  whole-model/whole-round summaries render only in the measurement list.
  See `docs/measurement-tools.md`.
- **Quality presets** (`low`/`medium`/`high`): trade yarn-mode tube fidelity
  for build time; defaults to a stitch-count-based deterministic choice,
  never an automatic "always high" default — see
  `docs/yarn-material-and-lighting.md`.
- **Lighting presets** (`neutral_laboratory`/`soft_studio`/
  `high_contrast_inspection`): switch the scene's four-light rig in place —
  see `docs/yarn-material-and-lighting.md`.
- Inspector panel now also shows geometry strategy name and path roles for
  the selected stitch (from `StitchPathResult`, yarn mode only) alongside
  the pre-existing type/component/round/parents/children fields, plus
  per-stitch geometry warnings surfaced in a dedicated `#yarn-warnings` list
  rather than silently dropped.

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
build ≈ 20–34 ms (3 draw calls, ~88,560 triangles), geometry-document
validation ≈ 3–4 ms, fixture JSON size ≈ 3.2 MB. Production bundle ≈ 572 KB
minified / 146 KB gzipped (`npm run build`, re-measured after the
completion audit; mostly
Three.js itself, ~28 KB/8 KB gzipped over the previous milestone's figure
from this slice's own new code) — still a candidate for code-splitting if
the viewer grows, not addressed in this slice.

Crochet-specific yarn-mode geometry (per-stitch strategy dispatch +
parallel-transport tubes, replacing the old straight-tube placeholder) is
substantially more expensive to build — 684 ms to 1.57 s across the three
quality presets on the same fixture, still 3 draw calls but 342K–987K
triangles depending on quality. Full numbers, the quality-preset tradeoff
table, and why this cost was judged acceptable (adjustable via quality
presets rather than fixed) are in
`docs/yarn-material-and-lighting.md`, not duplicated here.
