# Open-source resource adoption

Source: `deep-research-report.md` (supplied 2026-07-22), a third-party
research survey of crochet-specific prior art plus general-purpose parsing,
CV, graph, geometry, and web-visualization tooling. This document records,
for every resource the report or the task brief named, what this repository
actually did with it. License strings and version numbers below are as
stated in the source report or my own general knowledge of the named
project; none were re-verified against a live source in this session (no
network access was used to confirm them) — **treat any license/version
claim here as "reported," not "audited," until someone checks the primary
source before a legal decision depends on it.**

Status legend: **Adopted** (a dependency was added and code uses it) ·
**Design reference** (no dependency added; concepts/behaviour studied and
reimplemented independently) · **Rejected** (evaluated, explicitly not
used, with reason) · **Deferred** (relevant to a later phase, not this
slice).

## Crochet-specific prior art

### CrochetPARADE
- **Purpose**: DSL parser + validator + 3D/SVG-chart renderer for crochet patterns — the closest existing end-to-end system to this project's own pipeline.
- **Status**: **Design reference only.** No source code was read or copied.
- **License**: Reported GPLv3 (core), showcase patterns public-domain/author-released.
- **Compatibility**: GPLv3 is not compatible with keeping this repository's core under a permissive license without extending GPL obligations to the whole runtime — per the brief's explicit instruction, no GPLv3 source was copied.
- **What this repo actually reused**: the *concept* that a formal grammar can capture rounds/rows, stitch tokens, counts, and repeats, and that a canonical IR should sit between parsing and rendering — which this repository already had (the pre-existing `domain.Pattern`/`Round`/`Operation` model, built independently in Phase 1 before this pivot). The new `parsing/written/` grammar (`docs/written-pattern-grammar.md`) is a clean-room Lark grammar written against the abbreviation list in this task's own brief, not against CrochetPARADE's grammar file.
- **Files influenced**: none directly; informed the decision to keep `parsing/written/` as a distinct stage feeding the existing domain model rather than inventing a second IR (see `docs/crochet-ir-spec.md`).

### CrochetBench
- **Purpose**: benchmark dataset (reported ~6,085 patterns / 55 categories) pairing raw pattern text with CrochetPARADE-executable representations.
- **Status**: **Deferred.** Not downloaded, not incorporated.
- **License**: Report states patterns are sourced from Yarnspirations; a permissive redistribution license was not confirmed. Per the brief's explicit instruction not to place unlicensed patterns in the repository, none were added.
- **Reason**: Cannot verify redistribution rights this session. This repository's own test fixtures (`viewer/tests/fixtures.ts`, `tests/parsing/`) are hand-authored small synthetic patterns instead — see "Example fixtures" in the parser docs.
- **Future path**: if a license check later confirms reuse is permitted, `tests/parsing/fixtures/` is the natural adapter point — one JSON/text file per benchmark pattern, run through the parser, diffed against expected diagnostics/counts.

### AmiGo (Computational Design of Amigurumi Crochet Patterns)
- **Purpose**: "Crochet Graph" connecting geometry, connectivity, and manufacturable instructions; component segmentation; join-as-you-go assembly — the inverse problem (shape → pattern) from this project's (pattern → shape) direction.
- **Status**: **Design reference only** for graph edge-type completeness.
- **Comparison to this repo's existing `StitchGraph`** (`src/crochet_reconstruction/graph/models.py`):
  - **Similarities**: both distinguish yarn-sequence adjacency from structural attachment (this repo: `yarn_sequence` vs `insertion` edges); both group multiple stitches under one semantic unit (this repo: `increase_group_id`/`decrease_group_id`; AmiGo: increase/decrease grouping within its Crochet Graph).
  - **Differences**: AmiGo models multi-component assembly and seams (`join`/`seam`/`assembly` edge types) because amigurumi is built from separate worked-then-joined pieces. This repo's graph schema already reserves those edge type names (see `docs/stitch-graph-spec.md`, "Not yet implemented") but no current pattern (beanie, or the new written-pattern examples) has more than one joined component, so no builder code emits them yet.
  - **Missing relationships**: none required for this slice's rotational, single-component patterns. Multi-component amigurumi (a body attached to a head) would need the `assembly`/`seam` edges activated — explicitly future work, not built here.
  - **Does the existing rotational layout generalise beyond hats/rotational amigurumi?** No, by design — `docs/geometry-transfer-spec.md` already documents this as a `rotational_rounds.py`-specific strategy, with generic graph/geometry schemas kept separate from category-specific layout precisely so a future non-rotational strategy (flat panels, joined components) can be added without touching this one. This matches AmiGo's own architectural instinct (component segmentation as a distinct concern from stitch-level geometry) — no code change was made this slice, since no non-rotational category exists yet to justify one.
- **Files influenced**: none this slice (no demonstrated semantic limitation to fix); documented here as the basis for *not* changing the graph schema prematurely, per the brief's explicit instruction.

### Crochet Charts / Crochet CAD / crochet-simulator
- **Purpose**: symbol-chart authoring tools and pattern-to-shape prediction.
- **Status**: **Rejected** for this slice (no diagram/chart work happens in this slice at all).
- **License**: reported GPLv3 (Crochet Charts core; CC BY-SA 4.0 artwork), unspecified for the others.
- **Reason**: out of scope — this slice is written-text-to-3D only, per the brief's explicit exclusion of diagram recognition.

## Parsing

### Lark
- **Purpose**: grammar-backed written-pattern parser.
- **Status**: **Adopted.**
- **License**: MIT.
- **Version pinned**: `lark>=1.2,<2` (see `pyproject.toml`).
- **Files**: `src/crochet_reconstruction/parsing/written/grammar.lark`, `src/crochet_reconstruction/parsing/written/parser.py`.
- **Reason**: matches the brief's explicit preference; Python-native; LALR mode is fast enough and expressive enough for the bounded grammar in `docs/written-pattern-grammar.md`; avoids hand-rolled regex-chain parsing the brief explicitly warns against.

### ANTLR, Parsimonious, spaCy
- **Status**: **Rejected** (ANTLR, Parsimonious) / **Deferred** (spaCy).
- **Reason**: ANTLR's cross-language generation isn't needed (no second-language parser exists); Parsimonious offers no advantage over Lark for this grammar's size. spaCy-style free-text normalization (handling "work even," "repeat from *," prose ambiguity) is explicitly out of scope for this slice's *deterministic* parser — the brief requires such phrases to trigger a diagnostic, not a guess, so no NLP library is in the deterministic path. Could become relevant for the future "candidate interpretation" assist layer described in `docs/product-boundary.md`, never as a replacement for deterministic validation.

## Graph

### NetworkX
- **Status**: **Rejected.**
- **Reason**: this repository's `StitchGraph` (`graph/models.py`) is a flat Pydantic list-of-nodes/edges, not an in-memory traversal structure — its only consumers are the geometry layer (direct field access) and the invariant checker (`graph/validation.py`, plain Python loops over lists/dicts). Adding NetworkX would mean maintaining two graph representations (Pydantic-for-serialization, NetworkX-for-algorithms) for no current algorithmic need — nothing in this codebase does graph traversal complex enough to need it (no shortest-path, no connected-components query). Revisit if a future relaxation/constraint-solving pass needs real graph algorithms.

## Geometry

### Trimesh, PyVista, libigl, Eigen, pybind11
- **Status**: **Rejected** for this slice.
- **Reason**: the existing `geometry/` package (`frames.py`, `rotational_rounds.py`) is closed-form trigonometry over Python floats/tuples — there is no mesh to process, no sparse linear system to solve, and no C++ kernel need. These remain the correct next step *only* if a future constraint-relaxation slice (position-based dynamics, Laplacian smoothing) is built, exactly as the report's own "adopt only after analytical layouts work" guidance says. Not evaluated further because that slice hasn't started.

### PositionBasedDynamics, XPBD, Discrete Elastic Rods, Laplacian Surface Editing
- **Status**: **Deferred**, explicitly, per the brief ("do not implement XPBD relaxation" for this slice).
- **Design-reference value recorded for later**: PBD (MIT-licensed reference implementation reported) is the natural first upgrade past pure analytical placement; rod-based mechanics is reserved for a much later "realistic yarn" slice, matching this repo's own `docs/geometry-transfer-spec.md` layering (deterministic topology → analytical shape → constraint relaxation → visual rendering → future physical simulation).

## Backend / API

### JSON Schema
- **Status**: **Adopted**, via Pydantic's built-in schema generation (`model_json_schema()`), not a hand-authored schema file.
- **Reason**: brief explicitly permits "Pydantic-generated JSON Schema... if generated deterministically, versioned, and reproducible." `api/schemas.py` request/response models are the single source of truth; `docs/compile-api.md` documents how to regenerate the schema JSON on demand (`python -c "from crochet_reconstruction.api.schemas import CompileResponse; import json; print(json.dumps(CompileResponse.model_json_schema()))"`). Not committed as a static file this slice — reproducible generation was judged sufficient over a checked-in artifact that could silently drift from the models it describes.

### RFC 8785 (JSON Canonicalization Scheme)
- **Status**: **Audited, not adopted** — see `docs/canonical-json-audit.md` for the full comparison and test vectors.
- **Finding**: the existing `canonical_json()` implementations (`engine/compiler.py`, `graph/fingerprint.py`, `geometry/layout.py`) use `json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)` — key-sorted, whitespace-minimal, but **not** RFC 8785-compliant: RFC 8785 additionally mandates a specific Unicode normalization and a strict ECMAScript-compatible number serialization (no `default=str` escape hatch, no trailing-zero ambiguity), neither of which this codebase's `json.dumps` recipe guarantees byte-for-byte. Documented precisely why the existing scheme remains deterministic anyway for this codebase's actual value domain (only ASCII enum strings, Decimals pre-converted to fixed-precision floats/strings, and integers — no case where two distinct in-domain values could canonicalize identically under Python's `json.dumps` but differently under RFC 8785). Not changed this slice: switching would invalidate every existing fingerprint test vector for no behavioural benefit within this codebase's actual data.

## Frontend / viewer

### Three.js (existing), gl-matrix
- **Status**: Three.js **already adopted** (previous milestone). gl-matrix **rejected** — Three.js's own `Vector3`/`Quaternion`/`Matrix4` already cover every math need in `viewer/src/`; adding a second math library would duplicate responsibility for no gain.

### pmndrs/postprocessing, N8AO, three-mesh-bvh, three-gpu-pathtracer
- **Status**: **Deferred**, per the brief's explicit "evaluate only against measured needs."
- **Measured reasons recorded**: `viewer/tests/benchmark.test.ts` shows CPU raycasting and the existing `MeshStandardMaterial`/`ACESFilmicToneMapping` setup already comfortably handle the 1640-stitch reference fixture (structural build 16–60 ms, no picking-latency complaints). No measurement in this repository yet shows raycasting or shading as a bottleneck, so `three-mesh-bvh` (picking acceleration), `postprocessing`/N8AO (SSAO), and `three-gpu-pathtracer` remain unjustified additions. Revisit if a future fixture (tens of thousands of stitches) shows measured picking or frame-time regressions.

### VTK.js, Mol*, ParaView, MeshLab, NGL Viewer
- **Status**: **Design reference only** (interaction patterns, not code or dependencies).
- **Patterns studied and adopted into the existing/extended Three.js viewer**:
  - Selection hierarchy (whole object → component → round → stitch) — already implemented pre-slice (`viewer/src/state/store.ts`, isolate-round dropdown); this slice's `loadGeometryDocument` preserves that hierarchy across recompiles rather than rebuilding it as a NGL/VTK-style scene-graph object, since the flat instanced-mesh approach already satisfies it.
  - Colour-independent selection marker (Mol*/VTK.js both avoid colour-only selection indicators) — already implemented pre-slice (`selection/highlight.ts`'s wireframe torus).
  - Clipping-plane-relative-to-bounds UX (VTK.js's widget convention of expressing clip position as a fraction of the data's bounding box, not an absolute world coordinate) — already implemented pre-slice (`clipping/clipping.ts`); this slice's loader resets that fraction-relative-to-bounds state whenever bounds change (new pattern), matching the VTK.js convention that a clip widget re-derives its handle position from new data bounds rather than keeping a stale absolute position.
- **Not adopted**: neither framework was embedded; both remain reference material only, per the brief's explicit instruction not to copy their interfaces wholesale.

## Testing

### Playwright
- **Status**: **Adopted.**
- **License**: Apache-2.0.
- **Version pinned**: see `viewer/package.json` devDependencies.
- **Files**: `viewer/e2e/compile-workflow.spec.ts`.
- **Reason**: brief explicitly requires real-browser proof of the editor → API → live-geometry-replacement → selection workflow, which Vitest's jsdom environment cannot exercise (no real WebGL canvas, no real network round-trip through a running backend).

## Deferred to the future diagram pipeline (not this slice)

### OpenCV, Tesseract, Detectron2, MMDetection
- **Status**: **Deferred**, exactly per the brief.
- **Recorded future pipeline**: `SVG diagram parsing → raster preprocessing with OpenCV → optional learned symbol detection (Detectron2/MMDetection, only once a licensed annotated dataset exists) → canonical Pattern/StitchGraph → existing geometry pipeline`. No code added this slice.

### glTF / glTF-Validator
- **Status**: **Deferred.**
- **Design constraint honoured now**: `GeometryDocument` (`geometry/models.py`) stores plain position/orientation/radius/material-reference data with no Three.js-specific or parser-specific types leaking into it, so a future glTF exporter could be written as a pure consumer of `GeometryDocument` without touching `parsing/`, `graph/`, or `geometry/layout.py`. No exporter was written this slice.

## Summary table

| Resource | Status | License (reported) | Files influenced |
|---|---|---|---|
| CrochetPARADE | Design reference | GPLv3 | none (concept only) |
| CrochetBench | Deferred | Unconfirmed | none |
| AmiGo | Design reference | N/A (paper) | `docs/stitch-graph-spec.md` (no code change) |
| Crochet Charts/CAD/simulator | Rejected (out of scope) | GPLv3 / CC BY-SA 4.0 | none |
| Lark | **Adopted** | MIT | `parsing/written/grammar.lark`, `parsing/written/parser.py` |
| ANTLR / Parsimonious | Rejected | BSD-3 / MIT | none |
| spaCy | Deferred | MIT | none |
| NetworkX | Rejected | BSD-3 | none |
| Trimesh/PyVista/libigl/Eigen/pybind11 | Rejected (no current need) | MIT/MIT/MPL2/MPL2/BSD | none |
| PBD/XPBD/rods/Laplacian | Deferred | MIT (PBD ref impl) | none |
| JSON Schema (via Pydantic) | **Adopted** | N/A (spec) | `api/schemas.py` |
| RFC 8785 | Audited, not adopted | IETF standard | `docs/canonical-json-audit.md` |
| Three.js | Already adopted (prior milestone) | MIT | `viewer/src/**` |
| gl-matrix | Rejected | MIT | none |
| postprocessing/N8AO/three-mesh-bvh/pathtracer | Deferred | MIT/MIT/MIT/MIT | none |
| VTK.js/Mol*/ParaView/MeshLab/NGL | Design reference | BSD-3/MIT/BSD/GPL-3/MIT | `selection/highlight.ts`, `clipping/clipping.ts` (pre-existing, patterns confirmed not changed) |
| Playwright | **Adopted** | Apache-2.0 | `viewer/e2e/compile-workflow.spec.ts` |
| OpenCV/Tesseract/Detectron2/MMDetection | Deferred | Apache-2.0 (all) | none |
| glTF/glTF-Validator | Deferred | Khronos/Apache-2.0 | none (design constraint honoured in `geometry/models.py`) |
