# Yarn material, lighting, and quality presets

## Yarn material (`viewer/src/materials/yarn_material.ts`)

Starts from `THREE.MeshPhysicalMaterial`, per the brief's "start from
`MeshPhysicalMaterial` unless measurement shows it's inadequate" guidance —
no such measurement exists (see `docs/open-source-resource-adoption.md`'s
Three.js `MeshPhysicalMaterial` entry).

**Deliberately avoided**: high clearcoat, transmission, and normal-map
"glitter" — all of which read as plastic/wet rather than soft fibre.
**What actually gives yarn its look**: sheen (a thin-fibre-like grazing
highlight, `sheen`/`sheenRoughness`/`sheenColor`) combined with high
`roughness` (0.92 default) so specular highlights stay soft and wide rather
than sharp and mirror-like.

```
color:          0xcbb89a (default warm neutral yarn tone)
roughness:      0.92
metalness:      0
sheen:          0.65
sheenRoughness: 0.55
sheenColor:     0xffffff
envMapIntensity: 0.6
clearcoat:      0
transmission:   0
```

### Semantic yarn colors

`SEMANTIC_YARN_COLORS`: `main` (0xcbb89a), `increase` (0xe8a33d, warm
orange), `decrease` (0xe85d5d, red), `selected` (0xf5e642, yellow) — applied
per-vertex via `vertexColors` on the merged component mesh
(`build_yarn_paths.ts`), so a single draw call can still distinguish
increase/decrease stitches from plain ones without a per-stitch material.

### X-ray / opacity state

`applyYarnMaterialState(material, { opacity, xray })` caps effective
opacity at 0.22 when X-ray mode is active (regardless of the user's opacity
slider position), and only enables `depthWrite` once opacity is at or above
0.98 — avoiding the classic transparent-object depth-sorting artifact where
a fully-opaque object behind a translucent one is drawn in the wrong order.

## Lighting presets (`viewer/src/scene/scene.ts`)

Three presets, all built from the same key/fill/rim/hemisphere recipe —
only intensities and colors differ. Switching presets rebuilds the four
named lights in place (`applyLightingPreset`) rather than requiring a scene
rebuild.

| Preset | Purpose | Key intensity | Fill intensity | Rim intensity |
|---|---|---|---|---|
| `neutral_laboratory` (default) | Even, shadow-light illumination so stitch structure reads clearly regardless of yarn color, view mode, or clipping state — per the brief's "avoid highly dramatic cinematic lighting that obscures stitch structure" | 1.5 | 0.4 (cool blue fill) | 0.5 |
| `soft_studio` | Warmer, slightly softer contrast — a more presentation-friendly look without sacrificing readability | 1.1 | 0.6 (warm fill) | 0.3 |
| `high_contrast_inspection` | Strong key light, minimal fill, strong rim — maximises visible surface detail (post wraps, loop edges) for close inspection at the cost of a harsher overall look | 2.2 | 0.15 | 0.9 |

`neutral_laboratory` is the default specifically because it's the least
likely of the three to visually obscure a real geometry problem behind a
dramatic lighting choice — the other two are legitimate alternatives, not
"better" defaults.

## Quality presets (`viewer/src/geometry/build_yarn_paths.ts`)

Quality controls only how finely a strategy's semantic control points get
swept into tube geometry — never the control points themselves (see
`docs/stitch-geometry-strategies.md`). Two numbers per preset:

| Preset | `radialSegments` (tube cross-section) | `samplesPerCm` (curve sampling density) |
|---|---|---|
| `low` | 4 | 1.5 |
| `medium` | 6 | 3 |
| `high` | 10 | 6 |

`defaultQualityFor(stitchCount)` picks a deterministic default —
`low` above 4000 stitches, `medium` above 500, `high` otherwise — **never**
a random or camera-distance-based heuristic, per the brief's explicit "do
not automatically select high quality for very large models" requirement
(a large model silently defaulting to a slow preset would be a worse
surprise than a visibly-labelled low-quality default the user can raise).

## Measured performance (`viewer/tests/benchmark.test.ts`, `adult_beanie_hdc`, 1640 stitches)

Two consecutive local runs, reported as a range rather than a single number
— per this project's "measure, don't claim precision CI hardware can't
back up" convention (see `docs/scientific-viewer-spec.md`'s own
performance section for the pre-existing structural/validation numbers).

| Measurement | Range |
|---|---|
| Structural instanced-scene build | 20–34 ms, 3 draw calls, ~88,560 triangles |
| Yarn-path build, `low` quality | 684–854 ms, 3 draw calls, 8,336 segments, ~342,208 triangles |
| Yarn-path build, `medium` quality | 737–1,226 ms, 3 draw calls, 8,336 segments, ~513,312 triangles |
| Yarn-path build, `high` quality | 1,317–1,572 ms, 3 draw calls, 8,336 segments, ~986,720 triangles |
| Geometry-document validation | 3–4 ms |
| Fixture JSON size | 3,279 KB |

**Segment count (8,336) is quality-independent** — it comes from the
strategies' semantic decomposition (how many `StitchPathSegment`s a
1640-stitch pattern produces), not from tessellation. Only triangle count
and build time scale with quality, since quality only affects how densely
each segment is swept.

**This is a real, measured cost increase over the previous "basic yarn"
milestone** (straight tubes merged per component, ≈155–200 ms) — the new
per-stitch parallel-transport tube geometry with semantic segment
decomposition is substantially more expensive to build, by design, in
exchange for crochet-specific shape fidelity. The quality presets exist
specifically to make this cost adjustable rather than fixed; see
`docs/open-source-resource-adoption.md`'s re-evaluation of
`three-mesh-bvh`/`postprocessing`/N8AO for why quality presets, not a
rendering-library addition, were judged the right lever for this slice.

Draw-call count stays flat (3, matching structural mode) at every quality
level and does not depend on stitch count directly — it depends on
component count, since all of one component's stitches merge into one
mesh. A future fixture with many more components (e.g. a multi-piece
amigurumi) would be the case to re-measure draw-call scaling for, not this
one.
