# Measurement tools

Location: `viewer/src/measurement/types.ts` (data model),
`viewer/src/measurement/measurement.ts` (computation),
`viewer/src/main.ts`'s `wireMeasurements()` (UI wiring), `#measurement-*`
elements in `viewer/index.html`.

## What these measurements are, and are not

Every value reported here is **derived from analytically-placed stitch
positions or the model's bounding box** (the same closed-form trigonometry
that places every stitch — see `docs/known-limitations.md`'s "Geometry
accuracy" section), **never a physical measurement of a real object**.
Every `Measurement` record carries an explicit `approximate: boolean` field
(currently always `true`) rather than a hardcoded display string, so a
future measurement source that *is* exact could set it to `false` without
any caller needing to change. The number is only as accurate as the
underlying analytical layout, which does not model yarn tension, fibre
compression, gauge variance across a real swatch, or any constraint
relaxation (no position-based dynamics exists in this pipeline yet). Treat
these as **structural estimates for inspection**, not as a substitute for
measuring a physical piece.

## The `Measurement` data model (`measurement/types.ts`)

A tagged union, one variant per measurement kind:

```ts
type Measurement =
  | PointDistanceMeasurement
  | StitchDistanceMeasurement
  | ObjectWidthMeasurement
  | ObjectHeightMeasurement
  | RoundCircumferenceMeasurement;
```

Every variant shares: `id` (stable, unique), `type` (the discriminant),
`label` (a ready-to-display string), `valueCm`, `unit` (`doc.units`),
`approximate`, `createdAtMs` (creation timestamp), and
`geometryFingerprint` (`doc.geometry_fingerprint` at creation time, a
belt-and-suspenders association — `loadGeometryDocument` already clears all
measurements on recompile, so this field is not the only thing preventing
a measurement from outliving its model, but records the association
regardless). `main.ts`'s `formatMeasurement()` renders any variant
identically via these shared fields — no per-type branching needed in the
UI layer.

## Measurement kinds

### Point-to-point distance (arbitrary, not stitch-snapped)

`createPointDistanceMeasurement(doc, pointA, pointB)` — straight-line
distance between two raw 3D points, which need not correspond to any
stitch. `App.raycastPoint` casts a ray from the click position against
whichever mesh set is visible (structural or yarn) and uses the raw
`hits[0].point`, never resolving it to a `stitch_id` the way `pickStitch`
does — this is the one raycast path in the app that deliberately skips
identity resolution.

### Stitch-to-stitch distance

`createStitchDistanceMeasurement(doc, stitchIdA, stitchIdB)` (aliased as
`measureDistance` for the pre-refactor call sites/tests) — straight-line
distance between two stitches' `position` fields.

### Object width (approximate)

`createObjectWidthMeasurement(doc)` — the larger of `doc.bounds`' X and Y
extents. The geometry pipeline only produces rotationally symmetric shapes
today (`docs/known-limitations.md`), so X and Y extents should be near-equal
in practice; the max is used rather than assuming X specifically, so this
stays correct if that assumption ever loosens.

### Object height (approximate)

`createObjectHeightMeasurement(doc)` — `doc.bounds`' Z extent. Z is the
vertical/round-progression axis in this pipeline's layout convention
(`geometry/rotational_rounds.py` builds each round at a decreasing Z as
rounds progress) — not a fresh assumption made in the frontend.

### Round circumference (approximate)

`createRoundCircumferenceMeasurement(doc, componentId, roundIndex)` — sums
consecutive horizontal-neighbour edge lengths within one round (stitches
sorted by `sequence_index`, distance wrapped back to the first stitch to
close the loop): the **round anchor polyline** method, specifically — not
the analytical crown radius (`doc.measurements.max_radius_cm`, a different,
coarser backend-computed estimate) and not the stitch-path centreline
(yarn-mode's per-stitch geometry, which would give a longer number because
it follows the yarn's actual curve rather than a straight polyline between
stitch centres). The polyline method was chosen because it needs only
`GeometryDocument.stitches`, working identically in structural and yarn
view modes and requiring no dependency on the yarn-mode-only
`StitchPathResult` data. Returns `null` for a round with fewer than 2
stitches (`measureRoundCircumference`, the legacy pure-number wrapper,
returns `0` in the same case for backward compatibility with its existing
callers/tests).

## UI interaction

- **`#measurement-mode-toggle`**: enables a two-click measurement flow.
  `#measurement-kind-select` chooses which kind the clicks record —
  `"stitch"` (default, snaps to the clicked stitch) or `"point"` (raw
  raycast hit, `App.measurementPointMode`). `#measurement-status` reflects
  which kind is active and whether a first click is already pending.
  Clicking the same stitch twice in stitch mode is a no-op (the pending
  state is left unchanged until a genuinely different stitch is clicked),
  so a measurement can never be recorded as "a stitch's distance from
  itself."
- **`#measure-width`** / **`#measure-height`**: one-click, immediate —
  no pending-click state, since these summarise the whole model rather
  than two chosen points.
- **`#measure-round-circumference`**: one-click, uses the *currently
  selected* stitch's `(component_id, round_index)`. Disabled
  (`roundButton.disabled = !state.selectedStitchId`) when nothing is
  selected, rather than silently failing on click.
- **`#measurement-list`**: one `<li>` per recorded measurement, rendered via
  `formatMeasurement()`, plus a "Remove" button per item.
- Selecting a stitch while in stitch-mode measurement also updates
  `selectedStitchId` — the inspector panel updates on that same click,
  since selection and measurement-pending state are independent store
  fields, not mutually exclusive modes. Point-mode clicks do **not** touch
  selection at all (there is no stitch to select).

### Disposal on recompile

`loadGeometryDocument` clears `measurements`, `pendingMeasurementStitchId`,
and `pendingMeasurementPoint` whenever a new pattern is compiled and
loaded — a measurement referencing the *previous* model's stitch ids or
bounds would be meaningless (and likely reference ids that no longer
exist) against the new one. Covered by
`viewer/e2e/compile-workflow.spec.ts`'s scientific-viewer test (records
measurements of multiple kinds, recompiles, asserts `#measurement-list`
returns to zero) and `viewer/e2e/lifecycle-stress.spec.ts` (asserts the
same reset holds across every iteration of a repeated-recompile loop, not
just the first).

## Rendering

`buildMeasurementLine(doc, measurement)` draws a dashed line
(`THREE.LineDashedMaterial`, matching the existing selection/graph-overlay
convention of never relying on colour alone to distinguish an overlay from
the underlying model) between the measurement's two endpoints — for
`point_distance` these are the stored raw points directly; for
`stitch_distance` they're looked up from `doc.stitches`. **Object
width/height/round-circumference measurements render only in the
measurement list, not as a scene overlay** — they're scalar summaries of
the whole model or a whole round, with no single natural line segment to
draw. The line is named `measurement-${measurement.id}` so it can be found
and disposed individually when a measurement is removed, and now also
respects clipping like the rest of the model's real geometry (see
`docs/clipping-and-section-views.md`'s policy section) — the selection
marker is the one thing in the scene that deliberately does not.

## Known limitations

- No angle measurements, no area/volume estimates, no path-length-along-yarn
  measurement (only straight-line point-to-point/stitch-to-stitch).
- No persistence — measurements live only in the in-memory viewer store
  (`state/store.ts`); reloading the page or recompiling clears them (the
  latter is deliberate, see "Disposal on recompile" above; the former is
  simply because there is no save/load mechanism for viewer session state
  at all yet).
- Never sent to or validated by the backend, and has no JSON Schema — see
  `docs/schema-artifacts.md`'s "Frontend-only types are not included, on
  purpose" section.
