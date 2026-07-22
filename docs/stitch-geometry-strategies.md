# Stitch geometry strategies and the semantic yarn-path schema

Location: `viewer/src/geometry/stitch_paths/`. This layer turns each
backend-computed `StitchGeometry` (position/orientation/type/parents — see
`viewer/src/types/geometry.ts`, mirroring `geometry/models.py`) into a
semantic description of the yarn path that visually forms that one stitch:
which loops it passes through, how many times it wraps the hook, where it
attaches to its parent(s), and where its own top loop sits for the next
stitch to attach to. `viewer/src/geometry/build_yarn_paths.ts` is the only
file that turns this description into actual `THREE.BufferGeometry` tubes —
everything in `stitch_paths/` is framework-neutral (no `THREE.*` imports)
by design, so the geometric *reasoning* can be tested (`tests/stitch_paths/`,
`tests/build_yarn_paths.test.ts`) without a WebGL context.

## Why no backend schema change

Every input a strategy needs — `stitch_type`, `loop_placement`,
`parent_stitch_ids`, `is_increase`/`is_decrease`, and the stitch's own
tangent/normal/binormal orientation frame — already exists on the shipped
`GeometryDocument`. This whole layer is a pure frontend *interpretation* of
existing data: it never round-trips back through the compile API, never
changes `geometry_fingerprint`, and never requires the Python `geometry/`
package to know stitch-family-specific shapes exist. If a future stitch
family needs a genuinely new backend field (not just a new frontend
strategy), that would be a deliberate, separate decision — nothing here
assumes it won't happen, but nothing here needed it either.

## The schema (`stitch_paths/types.ts`)

```
StitchPathContext          — read-only lookups a strategy needs across
                              stitch boundaries: getStitch(id), yarnRadiusCm,
                              rowHeightCm (visual reference only, never
                              changes a backend-computed position)

StitchPathStrategy         — { stitchType, generatePaths(stitch, context) }
                              one implementation per recognised stitch_type,
                              looked up via a registry (strategies/index.ts)

StitchPathResult           — { stitchId, stitchType, strategyName,
                                segments: StitchPathSegment[],
                                entryPoint, exitPoint,
                                loopAttachment: LoopAttachment,
                                warnings: string[] }

StitchPathSegment          — { role: SegmentRole, controlPoints: Vec3[],
                                radius, curveType: "catmull_rom" | "line",
                                closed }

SegmentRole                — foundation_loop | top_loop | front_loop |
                              back_loop | post | yarn_over | pull_through |
                              connector | increase_branch | decrease_bridge

LoopAttachment              — { requested: string, resolved: string,
                                 exact: boolean } — see "Loop attachment"
                                 below (completion-audit addition)
```

`entryPoint`/`exitPoint` let the yarn-sequence continuity between
consecutive stitches stay implicit rather than requiring every strategy to
know about its neighbours directly — `build_yarn_paths.ts` only ever calls
`generateStitchPaths` once per stitch, in isolation.

`warnings` carry non-fatal notices (e.g. "loop placement shown as an
approximate lateral offset") through to mesh `userData` for inspection,
rather than being logged and discarded — per the project's general
"semantic path parts must not be silently dropped" convention (see also
`docs/measurement-tools.md`'s "approximate, not measured" framing).

## Loop attachment: exact vs. fallback (completion-audit addition)

`LoopAttachment` records how a stitch's requested loop placement
(`front_loop_only`/`back_loop_only`/`both`) was actually resolved into
geometry — `{ requested, resolved: string (human-readable), exact:
boolean }`. **No strategy in this codebase has ever modelled two
anatomically distinct loops** — `buildPlainStitchPaths` always uses the
same lateral-offset heuristic for a single-loop request — so every
non-`both` placement on a real plain stitch is a fallback by construction:

| Case | `exact` | `resolved` |
|---|---|---|
| `both`, has a parent | `true` | "full stitch top (both loops) — the standard insertion, no loop split needed" |
| `front_loop_only`/`back_loop_only`, has a parent | `false` | "lateral offset approximation of the requested single loop — no strategy models two anatomically distinct loops" |
| any placement, no parent (magic-ring root) | `true` | "no parent stitch to attach a loop to (magic ring root)" |
| any non-`both` placement on `chain`/`slip_stitch` | `false` | "loop placement is not modelled for chain/slip stitches" — these strategies never read `loop_placement` at all, so a non-default request is flagged rather than silently ignored |

Surfaced in the inspector as "Resolved attachment" and "Exact attachment"
rows (`main.ts`), alongside the pre-existing "Loop placement (requested)"
row. This is deliberately conservative: rather than inventing fake "exact"
geometry to make the flag read `true` more often, the flag stays `false`
for every case that's genuinely approximate — see
`docs/known-limitations.md`'s "Loop placement" bullet.

## Strategy registry and fallback (`strategies/index.ts`)

`generateStitchPaths(stitch, context)` looks up a strategy by
`stitch.stitch_type` in a `Map`. An unrecognised `stitch_type` falls back to
the single-crochet strategy **with a warning attached** — never a silent,
unlabelled guess. Increase/decrease are not separate stitch *types* in this
domain model (an `IncreaseOp`'s `stitch` field is still `sc`/`hdc`/`dc`);
they are a property any plain stitch can have, so `augmentForIncrease`/
`augmentForDecrease` (`strategies/increase_decrease.ts`) run as a
post-processing pass over whichever base strategy already ran, appending an
extra branch/bridge segment rather than duplicating each plain strategy for
its increase/decrease variant.

## Implemented strategies

### sc / hdc / dc — `plain_stitch.ts` + one three-line wrapper each

All three share one builder (`buildPlainStitchPaths`): attach → post →
(wraps) → top loop → exit. Only two numbers differ per stitch type:

| Stitch | `heightFactor` | `wrapCount` |
|---|---|---|
| sc (`sc.ts`) | 0.6 | 0 |
| hdc (`hdc.ts`) | 0.85 | 1 |
| dc (`dc.ts`) | 1.2 | 2 |

**Deliberate, documented cosmetic exaggeration**: the underlying stitch
*position* comes unchanged from the backend's uniform-row-height layout
(a separate, already-documented limitation — see "Known limitations"
below); only the locally-drawn curve between a visually-lowered "attach"
point and the stitch's real position varies by type. This is enough to make
sc/hdc/dc visually distinguishable (a dc's yarn path visibly wraps twice and
rises higher than an sc's) without touching the geometry-generation
backend or its fingerprinted output.

Loop placement (`front_loop_only`/`back_loop_only`/`both`) is drawn as an
approximate lateral offset from the parent's normal — a `front_loop`/
`back_loop` segment role is attached with a warning when placement isn't
`both`, rather than modelling the two loops of a real stitch top anatomically.

### chain — `chain.ts`

Not produced by the written-pattern parser yet (`chain`/`slip stitch` are
tokenised but rejected as `UNSUPPORTED_SYNTAX` during semantic conversion —
see `docs/known-limitations.md`), but implemented and tested behind this
strategy interface using synthetic fixtures
(`tests/stitch_paths/chain.test.ts`), per the brief's explicit allowance for
building recognised-but-not-yet-reachable strategies ahead of parser support.

Represented as a single closed loop whose plane alternates between the
stitch's own `(tangent, normal)` and `(tangent, binormal)` planes, keyed off
`sequence_index` parity for determinism — this makes consecutive chain
loops read as visually interlocking rather than a row of disconnected
flat rings.

### slip_stitch — `slip_stitch.ts`

Same "recognised but not yet parser-producible" status as chain. A compact
attachment loop with minimal vertical rise (15% of a normal stitch's row
height) and immediate yarn continuity to the next stitch — no post, no
wraps, matching a slip stitch's near-zero height in real crochet.

### Increase / decrease augmentation — `increase_decrease.ts`

- **Increase**: both increase children share one parent (`graph/builder.py`'s
  `increase_group_id`); each child independently draws an `increase_branch`
  line segment back to that shared parent position. Rendered together, two
  children's branches form a visible fan/V from one point — no extra
  backend data was needed, since both children already carry the same
  `parent_stitch_ids[0]`.
- **Decrease**: draws a `decrease_bridge` from the first parent, through
  the midpoint of the two parents, to the second parent, then a second
  bridge segment from that midpoint into the decrease stitch's own entry
  point — visually showing the two parent loops merging into one stitch.

## Quality presets and performance

Radial-segment count and curve-sampling density (`samplesPerCm`) are
controlled by `QualityPreset` (`build_yarn_paths.ts`), not by anything in
`stitch_paths/` — strategies always produce the same semantic control
points regardless of quality; only how finely those control points get
swept into a tube mesh changes. See `docs/yarn-material-and-lighting.md`
for the quality-preset table and measured build-time/triangle-count numbers.

## Testing

- `tests/stitch_paths/strategies.test.ts` (with `tests/stitch_paths/factory.ts`
  providing a small synthetic-`StitchGeometry` builder) — asserts segment
  roles, control-point counts, and warning behaviour for every strategy in
  isolation (no `GeometryDocument`, no THREE.js).
- `tests/build_yarn_paths.test.ts` — integration: a small synthetic
  `GeometryDocument` through `buildYarnPathScene`, checking merged-mesh
  structure, face-range contiguity (`stitchIdForFace` binary search), and
  quality-preset triangle-count scaling.
- `tests/benchmark.test.ts` — the 1640-stitch `adult_beanie_hdc` reference
  fixture at all three quality presets, logged (not strictly asserted
  beyond a generous ceiling) — see `docs/yarn-material-and-lighting.md`.
