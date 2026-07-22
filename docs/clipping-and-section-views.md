# Clipping and section views

Location: `viewer/src/clipping/clipping.ts` (plane math), `App.applyClipping`
(`viewer/src/app/App.ts`, application to materials), `#clipping-heading`
section of `index.html` (controls).

## Controls

| Control | Element | Notes |
|---|---|---|
| Enable/disable | `#clip-enabled` checkbox | |
| Axis | `#clip-axis` select | X / Y / Z |
| Position (slider) | `#clip-offset` range, `-100..100` | mapped to `-1..1`, a fraction of the model's bounding-box extent along the chosen axis |
| Position (numeric) | `#clip-offset-number` number input | mirrors the slider exactly — either control can drive the value, and both always show the same number (see `main.ts`'s `wireClippingControls`) |
| Invert | `#clip-invert` checkbox | flips which half-space is kept |
| Reset | `#clip-reset` button | restores `{ enabled: false, axis: "z", offset: 0, invert: false }` in one click |

All five value controls (`enabled`/`axis`/`offset`/`offsetNumber`/`invert`)
are kept in sync with the store in *both* directions: user input pushes to
the store as before, and a store subscription now writes the DOM controls
back to match whenever `state.clipping` changes for a reason other than the
user directly touching one of these inputs — the reset button, and a
recompile (`loadGeometryDocument` resets clipping on every new model, see
below). Before this fix, the checkbox/select/slider were write-only: a
recompile silently reset clipping internally while the checkbox stayed
visually checked, which is exactly the kind of "geometry does something
the visible controls don't explain" confusion this document's policy
section exists to avoid.

## What gets clipped — the policy, explicitly

`App.applyClipping`'s own docstring is the source of truth; summarised here:

- **Structural and yarn geometry are clipped.** They represent the actual
  model, so a clip plane should hide what it geometrically cuts away.
- **The graph overlay and measurement lines are also clipped.** They
  represent real edges/distances *of* that geometry, so they should track
  what's actually visible rather than floating through a clipped-away
  region as if unaffected by the same plane that hid the geometry they
  describe.
- **The selection marker and the selected-stitch/path-inspection overlay
  are deliberately exempt from clipping.** They exist so the user never
  loses track of *where* their current selection is, even if the clip
  plane currently hides that region of the model — an "always know where
  you are" indicator, not part of the model itself. Before this audit,
  this exemption existed by accident (nothing ever added these materials
  to the clipping call) and was inconsistent: the structural mode's
  instance-colour highlight *did* get clipped away with its triangles
  (it's baked into the same per-instance geometry), while the wireframe
  torus marker never did. The exemption is now uniform and intentional
  across both view modes, and verified directly — see "Verification" below.

X-ray mode and clipping are independent material-property mutations
(`applyOpacityAndXray`, `applyClipping`) applied on every state change —
no interaction bug exists between the two; combined use is exercised in
`viewer/e2e/compile-workflow.spec.ts`.

## Verification

`App.getClippingDebugInfo()` is a test-only hook (mirrors the existing
`getRendererInfo()` precedent) that reports whether the graph-overlay and
first measurement-line materials currently have a non-empty
`clippingPlanes` array, and whether the selection marker does — proving the
policy above from actual Three.js material state, not from reading the
code and trusting it. Exercised in `viewer/e2e/compile-workflow.spec.ts`.

## Bounds-relative, not absolute-world-coordinate

The offset is expressed as a fraction of the model's own bounding-box
extent along the chosen axis (`buildClippingPlane`, `clipping/clipping.ts`),
not an absolute world-space coordinate — this is a deliberate VTK.js-style
convention carried over from the previous milestone (see
`docs/open-source-resource-adoption.md`'s VTK.js entry): a clip widget
re-derives its handle position from the current data's bounds rather than
keeping a stale absolute position. `loadGeometryDocument` resets clipping
to disabled/`offset: 0` on every recompile for exactly this reason — a
`0.25` fraction from the *previous* model's bounds could land anywhere
(including entirely outside) the new model's bounds.

## Deferred, with reasons

- **Visible clip-plane helper mesh.** Not implemented. Three.js's
  `material.clippingPlanes` clips per-material with no visual plane
  indicator by default; a helper would need its own bounds-relative
  sizing/rotation logic duplicating `buildClippingPlane`'s axis math, for a
  problem (predicting where the plane is) the axis/offset/invert controls
  already state unambiguously in text. No user confusion has been observed
  that a helper would fix. Revisit if that changes.
- **Second clipping plane.** Not implemented. The current architecture
  threads exactly one `THREE.Plane | null` through
  `applyClippingToMaterials`; a second plane multiplies UI surface (a
  second axis/offset/invert/enabled group) and forces an interaction-
  semantics decision (union vs. intersection of the two half-spaces) for a
  cross-section-wedge use case that hasn't been requested or measured as
  needed this milestone. Revisit if a future requirement needs to isolate
  a slab/wedge rather than a single half-space.

## Testing

- `viewer/tests/clipping.test.ts` — `buildClippingPlane` axis/invert/bounds
  math, `applyClippingToMaterials` generic material handling.
- `viewer/e2e/compile-workflow.spec.ts` — slider ↔ numeric-input sync,
  reset button, the clipping-vs-overlay policy (via
  `getClippingDebugInfo`), and clipping state resetting (both internally
  and in the visible DOM controls) across a recompile.
