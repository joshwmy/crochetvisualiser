# Performance benchmarks

Consolidates every timing measurement in this repository: backend pipeline
(`tests/test_benchmark.py`), frontend scene construction and raycasting
(`viewer/tests/benchmark.test.ts`), and lifecycle/resource-leak checks
(`viewer/e2e/lifecycle-stress.spec.ts`). Numbers below are from local runs
on this development environment — see "Environment" for exact hardware —
and are reported as **observed values, not guaranteed production
performance**. Every benchmark test asserts only a generous ceiling
(10-100x the observed value), never a tight millisecond bound, per this
project's own "don't write brittle timing assertions on shared CI"
convention (already established for the pre-existing frontend
build-time benchmarks this file extends).

## Environment

- OS: Windows 11 Home, build 26200
- Reported CPU: 1 logical processor visible to this environment (likely a
  constrained/virtualised environment, not representative of a typical
  developer or end-user machine — reported honestly rather than omitted)
- RAM: ~7.8 GB
- Python: repo venv (`.venv`), pytest
- Node/Vitest: repo `viewer/` devDependencies, jsdom test environment
- Browser (Playwright): Chromium, via `@playwright/test`

**This environment is CPU-constrained relative to a typical desktop.**
Absolute numbers here should not be treated as representative of end-user
experience — the *relative* comparisons (structural vs. yarn raycast cost,
quality-preset scaling) are the more portable takeaway.

## Methodology

- Backend timings: `WARMUP_ITERATIONS = 2` (discarded), then 5 measured
  iterations (3 for the full HTTP round trip, since `TestClient` overhead
  per call is higher) — median and p95 reported per stage per fixture size.
- Frontend timings: single-shot for build times (matching the pre-existing
  convention in this file), 20-200 iterations for cheap per-call operations
  (raycasting, highlight, clipping, measurement creation) with the total
  divided by iteration count.
- "Small"/"medium"/"large" fixtures are separate for backend vs. frontend
  benchmarks (see each section) — the backend benchmarks use synthetic
  written patterns sized to hit specific stitch counts; the frontend
  benchmarks reuse the pre-existing 1640-stitch `adult_beanie_hdc` fixture
  (`viewer/public/geometry.json`) since regenerating that fixture at other
  sizes was judged unnecessary scope for this audit.

## Backend pipeline (`tests/test_benchmark.py`)

Three synthetic written patterns: small (108 stitches, the existing
amigurumi example), medium (800 stitches), large (1700 stitches, close to
the frontend's 1640-stitch reference fixture for rough comparability).

| Stage | Small (108 st.) | Medium (800 st.) | Large (1700 st.) |
|---|---|---|---|
| Parser | 15.7 / 17.6 ms | 77.6 / 93.1 ms | 170.6 / 244.2 ms |
| Graph build + validate | 11.3 / 14.1 ms | 72.7 / 94.2 ms | 121.7 / 162.1 ms |
| Geometry generation | 8.8 / 9.4 ms | 88.6 / 90.6 ms | 240.5 / 327.7 ms |
| Full compile API round trip | 59.4 / 69.6 ms | 337.2 / 398.7 ms | 512.0 / 621.1 ms |

(all cells: median / p95)

| Payload size | Small | Medium | Large |
|---|---|---|---|
| Response size | 263.0 KB | 1,924.5 KB | 4,107.1 KB |
| Bytes per stitch | ~2,494 | ~2,463 | ~2,474 |

Bytes-per-stitch stays essentially flat (~2,460-2,494) across a 15x
stitch-count range — the payload scales linearly with stitch count, not
super-linearly, which is the main thing this measurement was checking for
(an accidental O(n²) serialization cost would show up here as a rising
bytes/stitch trend).

## Frontend scene construction (`viewer/tests/benchmark.test.ts`)

On the 1640-stitch `adult_beanie_hdc` fixture, one representative run:

| Measurement | Value |
|---|---|
| Geometry-document validation | 1.9 ms |
| Structural instanced-scene build | 3.0 ms (3 draw calls, ~88,560 triangles) |
| Yarn-path build, `low` quality | 515.6 ms (3 draw calls, 8,336 segments, ~342,208 triangles) |
| Yarn-path build, `medium` quality | 680.4 ms (~513,312 triangles) |
| Yarn-path build, `high` quality | 1,142.8 ms (~986,720 triangles) |
| Fixture JSON size | 3,279 KB |

**Run-to-run variance was substantial** across the many runs performed
during this audit — structural build ranged 3-62 ms and yarn builds ranged
roughly 515-3,880 ms across repeated runs on this shared, CPU-constrained
environment (concurrent backend/test processes measurably affected these
numbers). The relative shape (yarn mode costs an order of magnitude more
than structural; `high` costs roughly 2x `low`) was consistent across every
run; the absolute milliseconds were not, which is exactly why the
benchmark tests assert only generous ceilings.

## Raycasting (`viewer/tests/benchmark.test.ts`, new this audit)

Self-flagged as missing in the prior milestone's own final report. Casts a
5×5 grid of NDC rays (25 points, sweeping most of the frame) against the
same fixture, structural vs. yarn mode:

| Mode | Time per 25-point sweep |
|---|---|
| Structural (`InstancedMesh`, 3 groups) | 11.3 ms |
| Yarn (merged component `Mesh`, 3 meshes) | 631.1 ms |

**Yarn raycasting is ~56x more expensive than structural** on this fixture
— confirming the hypothesis recorded in
`docs/open-source-resource-adoption.md`'s `three-mesh-bvh` re-evaluation:
both modes use exactly 3 raycast-target meshes (same draw-call count), so
the cost difference is entirely the linear-scan-over-triangles cost of a
non-BVH-indexed mesh with ~343K-987K triangles vs. structural's ~88.6K.
This is the concrete number that re-evaluation was missing; the
recommendation there (add `three-mesh-bvh` if raycast cost is ever
measured as a problem) is now backed by an actual measurement rather than
a prediction.

## Other interaction operations (`viewer/tests/benchmark.test.ts`, new this audit)

| Operation | Time per call |
|---|---|
| Selection-highlight update | 0.009 ms |
| Graph-overlay rebuild | 0.386 ms |
| Clipping-plane update | 0.003 ms |
| Measurement creation (all 5 types, one call each) | 0.030 ms |

All four are negligible relative to a yarn-mode scene rebuild — none of
them are a plausible bottleneck at this fixture size. Quality-level
switching is not measured separately here: it *is* the yarn-path build
time already measured above (`setQuality` tears down and rebuilds the yarn
scene at the new quality via the same `buildYarnPathScene` call). X-ray
mode switching (`applyOpacityAndXray`) is a handful of material-property
writes, cheaper than any of the four operations above, and was judged not
worth a separate benchmark for the same reason.

## Lifecycle / resource-leak stress (`viewer/e2e/lifecycle-stress.spec.ts`, new this audit)

Two scenarios, both against a real browser and real backend (not
mockable — this is exactly the kind of test that needs the real
`renderer.info` accounting a unit test can't provide):

1. Recompile the same small pattern 5 times in a row (reduced from the
   brief's suggested 10 for total suite runtime — each iteration is a real
   backend round trip, not a mock; 5 is still enough to distinguish "leaks
   a little every time" from "stable after the first couple of
   recompiles"). Assertion: `renderer.info.memory.geometries` after the
   5th compile is no more than 2 above its value after the 1st — not
   exactly equal, since legitimate small fluctuations in how geometries
   happen to merge are possible, but no upward trend.
2. Alternate between two small patterns 5 times. Same geometry-count
   assertion, plus confirms the final model is the actually-last-compiled
   one and remains interactive.

Both scenarios also assert `#measurement-list` returns to zero items after
every single recompile in the loop, not just the first one — this is a
stronger check than the original workflow test's single-recompile
assertion (`compile-workflow.spec.ts`), which only proved disposal works
once.

## What's intentionally not measured

- **Memory (JS heap) usage.** No credible cross-process memory API was
  used — `performance.memory` is Chromium-only, non-standardized, and
  reports isolate-wide heap size, not attributable to this app's Three.js
  resources specifically. `renderer.info.memory.geometries`/`.textures`
  (explicit Three.js resource counters, not browser heap) are used instead
  throughout — this is a deliberate substitution, not an oversight, and is
  the same approach the pre-existing single-recompile leak check already
  used.
- **Draw-call/frame-rate profiling under real user interaction** (orbit
  drag, animation playback) — out of scope for this audit's "backend and
  raycast timing were missing" gap; the existing manual-verification
  process (`docs/scientific-viewer-spec.md`'s "Known environment caveat")
  remains the mechanism for that.
