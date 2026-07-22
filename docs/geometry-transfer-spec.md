# Geometry-transfer specification

Package: `src/crochet_reconstruction/geometry/` (`models.py`, `frames.py`,
`layout.py`, `rotational_rounds.py`, `export.py`).

## What this layer is and is not

| Layer | What it is |
|---|---|
| Deterministic crochet topology | `graph` package — who connects to whom. Not touched here. |
| **Analytical shape approximation** | **This package.** Closed-form trigonometric placement from gauge + stitch counts. No simulation. |
| Constraint relaxation | Not implemented. The schema doesn't preclude a later position-based-dynamics pass over these same positions, but nothing here does that yet. |
| Visual rendering | The TypeScript viewer's job, not this package's. |
| Physical simulation | Not attempted anywhere in this codebase. |

## Rotational layout algorithm (`rotational_rounds.py`)

Applies to any pattern made of rounds worked in a circle — crown/body/brim
are the first three instances of that shape, not a hardcoded special case.
Documented assumptions (all analytical, none measured or simulated):

1. **Radius**: `circumference_cm = stitch_count / stitches_per_cm`,
   `radius_cm = circumference_cm / 2π`. Treats every round as a perfect
   circle of evenly-spaced stitches.
2. **Row height**: constant `1 / rounds_per_cm` per round, applied
   uniformly across crown, body, and brim.
3. **Crown dome**: modelled as a hemispherical cap,
   `z = dome_height * sqrt(max(0, 1 - (r/r_max)^2))`, where
   `dome_height = r_max * 0.6`. Chosen for visual continuity with the body
   (meets it at `z = 0` with matching radius) — not derived from the
   increase schedule's actual curvature.
4. **Angular placement**: `angle = 2π * position_in_round / round_count`.
   Because the graph builder emits increase children and decrease parents
   in matching left-to-right order, this alone keeps them close in angle —
   no separate proximity solve is needed for the first slice.
5. **Yarn diameter**: `0.5 / stitches_per_cm` (half a stitch width) unless
   explicitly overridden — a visual default, not a measured yarn property.

None of this feeds back into `engine`/`validation` — this package is a
one-way, read-only consumer of the compiled `Pattern` and its `StitchGraph`.

## Coordinate frames (`frames.py`)

Pure Python, no numpy dependency. `radial_frame(angle)` returns an
orthonormal (tangent, normal, binormal) basis:

- **tangent**: direction of increasing angle (around the fabric).
- **normal**: radially outward — a simplification that ignores local crown
  slope.
- **binormal**: vertical, through stitch height — always `tangent × normal`,
  so the frame is orthonormal by construction, never independently guessed.

`frame_to_quaternion` converts this basis to a unit quaternion via
Shepperd's method (numerically stable across all rotation angles), tested
for unit length and orthonormality preservation.

## GeometryDocument schema (JSON, schema_version `0.1.0`)

Top-level fields: `pattern_fingerprint`, `graph_fingerprint`,
`geometry_fingerprint` (all three carried through so the viewer can display
full provenance), `units` (`"cm"`), `gauge` (stitches/rounds per cm + yarn
diameter), `stitches[]`, `yarn_segments[]`, `edges[]` (graph edges carried
through for graph-mode rendering), `bounds`, `measurements`, `warnings[]`.

Each `StitchGeometry` record mirrors `StitchNode` one-to-one by
`stitch_id`, adding `position` (cm, `[x,y,z]`), `orientation` (unit
quaternion `[x,y,z,w]`), `tangent`/`normal`/`binormal`, and `scale`. **The
viewer must never infer stitch identity from position** — every rendered
object carries its `stitch_id` through instancing metadata (see
`scientific-viewer-spec.md`).

`GeometryMeasurements` (`overall_height_cm`, `max_radius_cm`,
`max_circumference_cm`) are **estimates from analytical placement, not
measurements of a physical object** — the viewer labels them "(estimated)"
wherever displayed.

## Fixture generation

```bash
python -m crochet_reconstruction.cli generate-geometry \
  --input examples/adult_beanie_hdc.json \
  --output build/geometry_fixtures/adult_beanie_hdc/
```

Exit codes mirror `generate`: 0 success, 1 fatal pattern validation (no
graph/geometry is built — a validation failure must prevent rendering), 2
malformed input, 3 pattern cannot be compiled, 4 a compiled/validated
pattern still fails stitch-graph invariants (defensive, should-never-happen
path).
