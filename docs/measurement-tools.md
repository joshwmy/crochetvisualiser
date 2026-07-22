# Measurement tools

Location: `viewer/src/measurement/measurement.ts` (computation),
`viewer/src/main.ts`'s `wireMeasurements()` (UI wiring), `#measurement-*`
elements in `viewer/index.html`.

## What these measurements are, and are not

Every distance reported here is **derived from analytically-placed stitch
positions** (the same closed-form trigonometry that places every stitch —
see `docs/known-limitations.md`'s "Geometry accuracy" section), **never a
physical measurement of a real object**. The viewer labels every recorded
measurement `"cm (approx.)"` for exactly this reason — the number is only
as accurate as the underlying analytical layout, which does not model yarn
tension, fibre compression, gauge variance across a real swatch, or any
constraint relaxation (no position-based dynamics exists in this pipeline
yet). Treat these as **structural estimates for inspection**, not as a
substitute for measuring a physical piece.

## Point-to-point / stitch-to-stitch distance

`measureDistance(doc, stitchIdA, stitchIdB)` — straight-line Euclidean
distance between two stitches' `position` fields, in the document's real
unit (`doc.units`, always `"cm"` today).

### Interaction flow

1. Check `#measurement-mode-toggle`. `#measurement-status` shows
   "Click a stitch…" (see `wireMeasurements()`).
2. Click a stitch. `App.handlePointerDown` sets
   `pendingMeasurementStitchId` **and** `selectedStitchId` to that stitch —
   the inspector panel updates on this first click too, since selection and
   measurement-pending state are independent fields in the store, not
   mutually exclusive modes.
3. Click a **different** stitch. `App` calls `measureDistance` between the
   pending stitch and the new one, appends the resulting `Measurement` to
   the store, and resets `pendingMeasurementStitchId` to `null`. Clicking
   the *same* stitch twice does nothing — the pending state is left
   unchanged until a genuinely different stitch is clicked, so a measurement
   can never be recorded as "a stitch's distance from itself."
4. `#measurement-list` renders one `<li>` per recorded measurement:
   `${stitchIdA} ↔ ${stitchIdB}: ${distanceCm.toFixed(2)} cm (approx.)`,
   plus a "Remove" button.
5. Uncheck `#measurement-mode-toggle` to stop recording; existing
   measurements remain visible and clickable-to-remove regardless of
   whether measurement mode is currently active.

### Disposal on recompile

`loadGeometryDocument` clears all recorded measurements (and the pending
stitch id) whenever a new pattern is compiled and loaded — a measurement
between two stitch ids from the *previous* model would be meaningless (and
likely reference ids that no longer exist) against the new one. This is
covered by `viewer/e2e/compile-workflow.spec.ts`'s scientific-viewer test,
which records a measurement, recompiles, and asserts `#measurement-list`
returns to zero items.

## Round circumference (approximate)

`measureRoundCircumference(doc, componentId, roundIndex)` — sums
consecutive horizontal-neighbour edge lengths within one round (stitches
sorted by `sequence_index`, distance wrapped back to the first stitch to
close the loop). Same "approximate, derived from analytical layout" caveat
applies. Not currently wired to a UI control — it exists as a tested
utility function (see `tests/measurement.test.ts`) for use by a future
per-round summary panel, not yet exposed to the user this slice.

## Rendering

`buildMeasurementLine(doc, measurement)` draws a dashed line
(`THREE.LineDashedMaterial`, matching the existing selection/graph-overlay
convention of never relying on color alone to distinguish an overlay from
the underlying model) between the two measured stitches' positions, named
`measurement-${measurement.id}` so it can be found and disposed
individually when a measurement is removed.

## Known limitations

- No angle measurements, no area/volume estimates, no path-length-along-yarn
  measurement (only straight-line point-to-point).
- No persistence — measurements live only in the in-memory viewer store
  (`state/store.ts`); reloading the page or recompiling clears them (the
  latter is deliberate, see "Disposal on recompile" above; the former is
  simply because there is no save/load mechanism for viewer session state
  at all yet).
- Round circumference has no UI control yet (see above).
- Never sent to or validated by the backend — see
  `docs/open-source-resource-adoption.md`'s JSON Schema re-evaluation for
  why no schema was generated for the `Measurement` type.
