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

This document was extended for the crochet-specific stitch-geometry slice
(`viewer/src/geometry/stitch_paths/`, `parallel_transport_tube.ts`,
`materials/yarn_material.ts`, `measurement/`, `selection/graph_overlay.ts`):
new entries and re-evaluations for that slice are marked **(re-evaluated
this slice)** below rather than filed as separate sections, so each
resource keeps one history instead of being split across documents.

## Crochet-specific prior art

### CrochetPARADE
- **Purpose**: DSL parser + validator + 3D/SVG-chart renderer for crochet patterns — the closest existing end-to-end system to this project's own pipeline.
- **Status**: **Design reference only.** No source code was read or copied.
- **License**: Reported GPLv3 (core), showcase patterns public-domain/author-released.
- **Compatibility**: GPLv3 is not compatible with keeping this repository's core under a permissive license without extending GPL obligations to the whole runtime — per the brief's explicit instruction, no GPLv3 source was copied.
- **What this repo actually reused**: the *concept* that a formal grammar can capture rounds/rows, stitch tokens, counts, and repeats, and that a canonical IR should sit between parsing and rendering — which this repository already had (the pre-existing `domain.Pattern`/`Round`/`Operation` model, built independently in Phase 1 before this pivot). The new `parsing/written/` grammar (`docs/written-pattern-grammar.md`) is a clean-room Lark grammar written against the abbreviation list in this task's own brief, not against CrochetPARADE's grammar file.
- **Files influenced**: none directly; informed the decision to keep `parsing/written/` as a distinct stage feeding the existing domain model rather than inventing a second IR (see `docs/crochet-ir-spec.md`).
- **(Re-evaluated this slice)**: checked whether CrochetPARADE's published material describes per-stitch parametric loop/post geometry (leg length, top-of-stitch loop diameter, wrap angle for hdc/dc) that could seed `viewer/src/geometry/stitch_paths/strategies/`. It does not — the reported system renders symbol charts and a simplified 3D preview from the same IR, not a documented parametric stitch-shape model, and its GPLv3 source was not read. **Verdict unchanged: design reference only.** The strategy constants in `strategies/*.ts` (loop radii, post curve control points, wrap counts for hdc/dc) were authored from this project's own crochet-construction reasoning (documented inline per strategy) and validated against the existing golden/property test suite, not derived from CrochetPARADE.
- **(Re-evaluated this slice, SVG diagram ingestion)**: CrochetPARADE is the closest published prior art to this slice's own SVG-diagram-to-3D pipeline specifically (it also parses chart-like input into a canonical representation feeding a renderer). Studied as a **semantic/design reference only** — no GPLv3 source or grammar file was read. Concepts studied: that a chart symbol needs a canonical (terminology-independent) identity separate from its visual glyph, and that "increase/decrease" is more naturally a topological fact (parent/child fan-out) than a distinct symbol category. Both concepts are already reflected in `diagram/ontology.py`'s design, arrived at independently from this project's own written-pattern parser's existing canonical/display-terminology split (`docs/terminology.md`) and the brief's own explicit "acceptable... through topology" instruction — not derived from reading CrochetPARADE's implementation. Clean-room precaution: this slice's `topology.py` (centre detection, round clustering, proportional-distribution parent attachment) and `classification.py` (primitive-geometry heuristic) were designed and implemented from first principles against this project's own synthetic fixtures, with no CrochetPARADE source consulted at any point. **Verdict: still design reference only**, consistent with the written-pattern slice's earlier evaluation.

### CrochetBench
- **Purpose**: benchmark dataset (reported ~6,085 patterns / 55 categories) pairing raw pattern text with CrochetPARADE-executable representations.
- **Status**: **Deferred.** Not downloaded, not incorporated.
- **License**: Report states patterns are sourced from Yarnspirations; a permissive redistribution license was not confirmed. Per the brief's explicit instruction not to place unlicensed patterns in the repository, none were added.
- **Reason**: Cannot verify redistribution rights this session. This repository's own test fixtures (`viewer/tests/fixtures.ts`, `tests/parsing/`) are hand-authored small synthetic patterns instead — see "Example fixtures" in the parser docs.
- **Future path**: if a license check later confirms reuse is permitted, `tests/parsing/fixtures/` is the natural adapter point — one JSON/text file per benchmark pattern, run through the parser, diffed against expected diagnostics/counts.
- **(Re-evaluated this slice)**: the new per-stitch geometry strategies (`viewer/src/geometry/stitch_paths/`) raised the same question from a different angle — would CrochetBench's paired text/executable-representation corpus be useful as *geometry* regression fixtures (does a real sc/hdc/dc/inc/dec sequence at scale produce a self-intersection-free tube mesh)? Same licensing blocker applies (Yarnspirations-sourced patterns, redistribution rights unconfirmed), so still **deferred, not incorporated**. This project's own `AMIGURUMI_EXAMPLE` fixture (used in `viewer/e2e/compile-workflow.spec.ts` and the Vitest geometry-document tests) continues to serve as the hand-authored substitute.

### AmiGo (Computational Design of Amigurumi Crochet Patterns)
- **Purpose**: "Crochet Graph" connecting geometry, connectivity, and manufacturable instructions; component segmentation; join-as-you-go assembly — the inverse problem (shape → pattern) from this project's (pattern → shape) direction.
- **Status**: **Design reference only** for graph edge-type completeness.
- **Comparison to this repo's existing `StitchGraph`** (`src/crochet_reconstruction/graph/models.py`):
  - **Similarities**: both distinguish yarn-sequence adjacency from structural attachment (this repo: `yarn_sequence` vs `insertion` edges); both group multiple stitches under one semantic unit (this repo: `increase_group_id`/`decrease_group_id`; AmiGo: increase/decrease grouping within its Crochet Graph).
  - **Differences**: AmiGo models multi-component assembly and seams (`join`/`seam`/`assembly` edge types) because amigurumi is built from separate worked-then-joined pieces. This repo's graph schema already reserves those edge type names (see `docs/stitch-graph-spec.md`, "Not yet implemented") but no current pattern (beanie, or the new written-pattern examples) has more than one joined component, so no builder code emits them yet.
  - **Missing relationships**: none required for this slice's rotational, single-component patterns. Multi-component amigurumi (a body attached to a head) would need the `assembly`/`seam` edges activated — explicitly future work, not built here.
  - **Does the existing rotational layout generalise beyond hats/rotational amigurumi?** No, by design — `docs/geometry-transfer-spec.md` already documents this as a `rotational_rounds.py`-specific strategy, with generic graph/geometry schemas kept separate from category-specific layout precisely so a future non-rotational strategy (flat panels, joined components) can be added without touching this one. This matches AmiGo's own architectural instinct (component segmentation as a distinct concern from stitch-level geometry) — no code change was made this slice, since no non-rotational category exists yet to justify one.
- **Files influenced**: none this slice (no demonstrated semantic limitation to fix); documented here as the basis for *not* changing the graph schema prematurely, per the brief's explicit instruction.
- **(Re-evaluated this slice)**: the new `StitchPathResult` model (`viewer/src/geometry/stitch_paths/types.ts`) adds per-stitch path-role metadata (loop-in, post, loop-out, wrap segments) — checked whether AmiGo's Crochet Graph has an equivalent finer-than-stitch decomposition worth mirroring. AmiGo's public description stays at stitch-level graph granularity (nodes are whole stitches; edges are yarn-sequence/insertion/assembly relationships) and does not publish a sub-stitch yarn-path decomposition, so there is nothing at that resolution to compare against. **Verdict unchanged: design reference only**, and `StitchPathResult` remains this project's own addition, layered strictly above the existing `StitchGraph`/`StitchNode` schema (one `StitchPathResult` per `StitchNode`) rather than a replacement for it.

### Crochet Charts / Crochet CAD / crochet-simulator
- **Purpose**: symbol-chart authoring tools and pattern-to-shape prediction.
- **Status**: **Rejected** for the written-pattern slice; **re-evaluated, still rejected** for this slice.
- **License**: reported GPLv3 (Crochet Charts core; CC BY-SA 4.0 artwork), unspecified for the others.
- **Reason (written-pattern slice)**: out of scope — that slice was written-text-to-3D only.
- **(Re-evaluated this slice, SVG diagram ingestion)**: this slice does now do diagram/chart work, so the question is live again — does Crochet Charts' authoring format or symbol artwork have anything reusable? No source was read (GPLv3) and no CC BY-SA 4.0 artwork was copied into this repository — `docs/diagram-symbol-ontology.md`'s vocabulary and `tests/diagram/fixtures/svg/`'s synthetic shapes were both authored independently against the Craft Yarn Council's public terminology standard (see below), not against Crochet Charts' own symbol set. **Verdict unchanged: rejected**, now for licensing reasons specific to this slice rather than "out of scope."

### Craft Yarn Council crochet chart-symbol standard
- **Purpose**: the industry-standard reference for crochet chart symbol meanings and stitch terminology (US/UK).
- **Status**: **Adopted as an ontology/terminology reference only** — no artwork redistributed.
- **What this repo actually did**: `diagram/ontology.py`'s canonical stitch names (`magic_ring`, `chain`, `slip_stitch`, `single_crochet`, `half_double_crochet`, `double_crochet`, `increase`, `decrease`, `join`) and the reserved-future vocabulary (`treble_crochet`, `picot`, `puff_stitch`, `bobble`, `cluster`, `front_post`, `back_post`) were named against this standard's terminology, matching the existing written-pattern parser's own US/UK terminology-vs-identity split (`docs/terminology.md`). **No Craft Yarn Council symbol artwork (the actual chart glyphs) is anywhere in this repository** — every synthetic fixture symbol shape in `tests/diagram/fixtures/svg/` (the cross/T/loop/dot primitives `classification.py` recognises) was designed from scratch for this project's own bounded geometry heuristic, calibrated to this project's own authoring convention, not traced from or matching the Council's published artwork.
- **License note**: a terminology/naming standard and a specific piece of artwork are different things under copyright — using "single crochet" as a canonical identifier is using a fact/term, not reproducing a creative work; the Council's actual chart symbol *drawings* would be a creative work requiring a licence check before any reproduction, which this project never attempted.
- **Files influenced**: `diagram/ontology.py`, `docs/diagram-symbol-ontology.md`.

### Digital Crochet / crochet visual-language and graph-layout research
- **Purpose**: academic/hobbyist research on crochet chart visual conventions and graph-based layout of crochet structures.
- **Status**: **Design reference only**, at the same "concept, not implementation" level as AmiGo above.
- **What this repo actually did**: the general idea that a crochet chart's visual layout (radial symbol placement around a centre, angular ordering within a round) corresponds directly to the underlying stitch graph's topology (which this project's `topology.py` already treats as the source of truth) is a well-established observation in this research area, not a novel insight original to any one source — this project's own radial/proportional-distribution algorithm (`docs/diagram-topology-inference.md`) was designed directly from crochet-construction reasoning (how rounds, increases, and decreases physically work) rather than transcribed from any specific paper's published algorithm. No code or pseudocode from any specific publication was read or adapted.
- **Files influenced**: none directly; recorded here per the brief's explicit instruction to revisit this resource category for this slice.

## Parsing

### defusedxml (new this slice)
- **Status**: **Adopted.**
- **License**: PSF-2.0 (Python Software Foundation License).
- **Version pinned**: `defusedxml>=0.7,<0.8` (see `pyproject.toml`).
- **Files**: `src/crochet_reconstruction/diagram/svg_parser.py`.
- **Reason**: the standard, widely-recommended Python answer to XXE/entity-expansion/DTD-based XML attacks (matches the brief's explicit "evaluate a library such as `defusedxml` or an equivalent secure approach" instruction) — see `docs/svg-security.md` for the full threat model. Rejected alternative: hand-rolling XXE/entity-expansion defences over the standard-library `xml.etree.ElementTree` directly, which would mean re-deriving a well-known, already-solved security control instead of using the community-vetted one.

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
- **Status**: **Adopted**, via Pydantic's built-in schema generation (`model_json_schema()`).
- **Reason**: brief explicitly permits "Pydantic-generated JSON Schema... if generated deterministically, versioned, and reproducible." `api/schemas.py` request/response models (plus `graph.models.StitchGraph`, `geometry.models.GeometryDocument`) are the single source of truth.
- **(Re-evaluated this slice)**: the written-pattern slice originally chose *not* to commit a static schema file, judging reproducible on-demand generation sufficient. This completion audit raised that bar: `schemas/*.schema.json` are now committed, versioned (`$id`, `$schema`, `version` fields), and match-tested (`src/crochet_reconstruction/api/schema_export.py`, `tests/test_schema_export.py` — five tests asserting the committed files are byte-identical to what the current models would generate, checking reproducibility, and checking version fields track each model's own version constant). See `docs/schema-artifacts.md` for the generation command and version-compatibility policy. This is still the same Pydantic-generated-schema approach, not a second competing schema system — the audit's own instruction was explicit about that.
- The frontend-only types `StitchPathResult` (`viewer/src/geometry/stitch_paths/types.ts`) and `Measurement` (`viewer/src/measurement/types.ts`) were checked against this same policy and remain **not schema'd**. Neither crosses a process/serialization boundary — `StitchPathResult` is computed in-browser from an already-validated `GeometryDocument` and consumed only by the yarn tube builder in the same process; `Measurement` is computed from already-loaded stitch positions/bounds and stored only in the in-memory viewer store (never sent to the backend, never persisted). Revisit if either type is later persisted (e.g. saved measurement sessions) or sent to the backend.

### RFC 8785 (JSON Canonicalization Scheme)
- **Status**: **Audited, not adopted** — see `docs/canonical-json-audit.md` for the full comparison and test vectors.
- **Finding**: the existing `canonical_json()` implementations (`engine/compiler.py`, `graph/fingerprint.py`, `geometry/layout.py`) use `json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)` — key-sorted, whitespace-minimal, but **not** RFC 8785-compliant: RFC 8785 additionally mandates a specific Unicode normalization and a strict ECMAScript-compatible number serialization (no `default=str` escape hatch, no trailing-zero ambiguity), neither of which this codebase's `json.dumps` recipe guarantees byte-for-byte. Documented precisely why the existing scheme remains deterministic anyway for this codebase's actual value domain (only ASCII enum strings, Decimals pre-converted to fixed-precision floats/strings, and integers — no case where two distinct in-domain values could canonicalize identically under Python's `json.dumps` but differently under RFC 8785). Not changed this slice: switching would invalidate every existing fingerprint test vector for no behavioural benefit within this codebase's actual data.
- **(Re-evaluated this slice)**: the audit's test-vector table was extended with nested-object, array, integer, decimal-like, negative-zero, Unicode-string, and raw-float vectors (`docs/canonical-json-audit.md` § Test vectors, `tests/test_canonical_json.py`) to make the existing deviations (ASCII-escaping, `repr`-based float formatting, `Decimal`'s signed-zero string form) concrete and executable rather than asserted in prose alone. No behavioural change to `canonical_json()` itself — this slice's stitch-geometry additions (`StitchPathResult`, quality presets, materials) are frontend-only and never pass through the Python fingerprint functions, so there was no new call site to audit, only the existing one to document more thoroughly.

### PROV-JSON (new this slice)
- **Status**: **Evaluated, rejected** for this slice's provenance needs.
- **What it is**: a JSON serialization of the W3C PROV Data Model — a graph of Entities, Activities, and Agents connected by typed relations (`wasDerivedFrom`, `wasGeneratedBy`, `used`, `wasAttributedTo`) for representing *how* a piece of data came to exist across tool/process boundaries.
- **Where it would apply here**: this codebase already has a real derivation chain — written pattern text → `Pattern` → `StitchGraph` → `GeometryDocument` → (this slice) per-stitch `StitchPathResult` → rendered tube mesh — each stage fingerprinted (`fingerprint.py`, `geometry_fingerprint`). PROV-JSON's Entity/Activity/`wasDerivedFrom` model maps onto that chain in principle.
- **Reason for rejection**: this project's actual requirement is narrower than what PROV-JSON is built for — *"did this output come from this exact input, byte for byte"* (answered today by the existing SHA-256 canonical-JSON fingerprints at each stage, audited above), not *"which external tools, agents, or third-party datasets contributed to this artifact over time,"* which is the cross-tool/cross-organization interchange problem PROV-JSON actually solves. Adopting it would mean maintaining a second provenance representation (PROV entities/activities) alongside the fingerprints that already give this codebase what it needs, for a cross-system interchange use case (e.g. exporting lineage to an external provenance-tracking service) that doesn't exist yet. **License**: PROV-JSON is a W3C specification (W3C Document License), not a library — there is no dependency to add, only a data-model convention to optionally adopt.
- **Revisit if**: a future requirement needs this project's provenance to interoperate with an external PROV-consuming system, or needs to represent contributions from multiple distinct tools/agents (e.g. a human-edited pattern merged with a machine-vision-extracted one) rather than this codebase's current single-pipeline, single-agent derivation chain.

## Frontend / viewer

### Three.js (existing), gl-matrix
- **Status**: Three.js **already adopted** (previous milestone). gl-matrix **rejected** — Three.js's own `Vector3`/`Quaternion`/`Matrix4` already cover every math need in `viewer/src/`; adding a second math library would duplicate responsibility for no gain.

### Three.js `TubeGeometry` (re-evaluated this slice)
- **Status**: **Rejected**, in favor of a hand-written parallel-transport tube builder (`viewer/src/geometry/parallel_transport_tube.ts`).
- **Reason**: `THREE.TubeGeometry`/`THREE.Curve.computeFrenetFrames` derives its per-frame normal from curvature, which is undefined on a perfectly straight segment and numerically unstable near zero curvature — exactly the shape of this project's connector/increase-branch/decrease-bridge segments and the low-curvature stretches of a post curve. `computeFrenetFrames`'s fallback (an arbitrary consistent normal per curve instance) is stable for one static straight segment in isolation but produces a visible seam/twist discontinuity where a single mixed curve transitions between high- and near-zero-curvature stretches, which every semantic yarn path in this codebase does (loop-in → post → loop-out). `computeParallelTransportFrames` avoids this by rotating each frame from its predecessor via the angle between consecutive tangents (never from curvature), degrading gracefully to "no rotation" on straight stretches instead of re-picking an arbitrary normal. Full reasoning in the file's own header comment.
- **Files**: `viewer/src/geometry/parallel_transport_tube.ts` (frame computation + `buildTubeGeometry`), consumed by `viewer/src/geometry/build_yarn_paths.ts`.

### Three.js `MeshPhysicalMaterial` (re-evaluated this slice)
- **Status**: **Adopted**, per the brief's "start from `MeshPhysicalMaterial` unless measurement shows it's inadequate" guidance — no such measurement exists.
- **Reason**: sheen (a thin-fibre grazing highlight) plus high roughness gives a soft-fibre look without clearcoat/transmission, which read as plastic/wet rather than yarn. `viewer/src/materials/yarn_material.ts` documents the deliberate exclusions (no clearcoat, no transmission, no normal-map glitter) and exposes semantic color presets for main/increase/decrease/selected yarn segments.
- **Files**: `viewer/src/materials/yarn_material.ts`.

### Three.js raycasting (re-evaluated this slice, diagram-ingestion slice)
- **Status**: **Adopted, mechanism changed** — `App.pickStitch` now raycasts against `selection/hit_proxies.ts`'s invisible per-stitch `InstancedMesh` set in *every* view mode (structural, yarn, x-ray, graph-overlay, path), instead of branching between the fast structural `Picker` path and a per-triangle raycast against the visible yarn tube meshes (the old `App.pickYarn`, now deleted — its logic is preserved for comparison purposes only in `viewer/tests/benchmark.test.ts`'s "yarn mode" benchmark).
- **Why not `three-mesh-bvh`**: the brief's guidance was to try simplified structural hit proxies first and adopt a BVH acceleration structure only if proxies failed to deliver acceptable performance. They didn't fail — see the measured numbers below — so `three-mesh-bvh` remains unjustified.
- **Measured before/after** (`viewer/tests/benchmark.test.ts`, 1640-stitch reference fixture, 25-point NDC grid sweep, mean of 20 sweeps, this machine/run — see the file for the exact numbers on any given run):
  - Before (yarn mode raycasting the merged, high-triangle-count tube meshes directly): **~700–970 ms** per sweep.
  - After (hit-proxy raycast, low-poly invisible spheres, used in every mode): **~9–11 ms** per sweep — roughly a **70–100x** reduction, and slightly faster than the structural capsule raycast itself (~15–24 ms), since the proxy sphere geometry is cheaper.
  - Structural-mode raycast (unchanged mechanism, now against proxies instead of the visible capsules) stays in the same ~15–25 ms range as before.
- **Correctness, not just speed**: proxies are deliberately sized slightly larger than the visible geometry (a comfortable click target — `hit_proxies.ts`'s `proxyRadius`), so in densely packed regions the nearest-hit proxy can occasionally resolve to an angularly adjacent stitch rather than bit-for-bit the stitch a tighter raycast would report; `viewer/tests/benchmark.test.ts`'s correctness test checks "resolves to a real, nearby stitch" (within 3 stitch-widths) rather than exact-ID equality, which is the property that actually matters for click-to-select UX.
- **A real bug this surfaced**: `THREE.Raycaster.intersectObjects` does **not** skip `object.visible = false` objects on its own — `.visible` only gates the *renderer*. `selection/picking.ts`'s `Picker` previously relied on the caller only ever passing already-visible meshes (true before this slice, since it was only invoked while structural mode's meshes were genuinely visible); the hit-proxy scene's "always `visible = true`, hidden via zero opacity" design broke that assumption for the new `hiddenComponentIds` case, so `Picker.pick` now explicitly filters `scene.groups` by `.mesh.visible` before raycasting. See `viewer/tests/hit_proxies.test.ts`'s regression test.
- **Files**: `viewer/src/selection/hit_proxies.ts` (new), `viewer/src/selection/picking.ts` (visibility filter), `viewer/src/app/App.ts` (`pickStitch`, `applyPerStitchVisibility`), `viewer/tests/hit_proxies.test.ts`, `viewer/tests/benchmark.test.ts`.

### Three.js clipping planes (re-evaluated this slice)
- **Status**: **Adopted, unchanged mechanism** — `viewer/src/clipping/clipping.ts` builds a `THREE.Plane` from the UI's axis/offset/invert state and assigns it to `material.clippingPlanes` (Three.js's native per-material local-clipping feature), applied uniformly to both structural and yarn materials via `applyClippingToMaterials`. No new dependency; extended this slice only in that yarn materials are now included in the same clipping-plane assignment as structural materials.

### pmndrs/postprocessing, N8AO, three-mesh-bvh, three-gpu-pathtracer
- **Status**: **Deferred**, per the brief's explicit "evaluate only against measured needs."
- **Measured reasons recorded**: `viewer/tests/benchmark.test.ts` shows CPU raycasting and the existing `MeshStandardMaterial`/`ACESFilmicToneMapping` setup already comfortably handle the 1640-stitch reference fixture (structural build 16–60 ms, no picking-latency complaints). No measurement in this repository yet shows shading as a bottleneck, so `postprocessing`/N8AO (SSAO) and `three-gpu-pathtracer` remain unjustified additions. Revisit if a future fixture (tens of thousands of stitches) shows measured frame-time regressions.
- **(Re-evaluated this slice, diagram-ingestion slice)**: `three-mesh-bvh` was the previously identified "natural next step" if yarn-mode picking cost was ever measured as a real problem — this slice measured it (it was: ~700–970 ms per pick-sweep against the merged tube meshes) and addressed it via the brief's preferred *first* approach (simplified invisible structural hit proxies — see the "Three.js raycasting" entry above) rather than jumping straight to a BVH acceleration structure over the *visible* high-triangle-count geometry. The proxy approach measured ~9–11 ms per sweep, an ~70–100x improvement that already beats even the structural-mode raycast — no BVH pass was needed to reach that result. **Verdict: `three-mesh-bvh` stays deferred**, now with a concrete reason beyond "not measured as a problem yet" — a much simpler fix already solved the measured problem. Revisit only if a future fixture's *hit-proxy* raycast cost (not the now-irrelevant yarn-tube one) is itself measured as a bottleneck, e.g. tens of thousands of stitches where even the low-poly proxy count becomes the limiting factor.

### VTK.js, Mol*, ParaView, MeshLab, NGL Viewer
- **Status**: **Design reference only** (interaction patterns, not code or dependencies).
- **Patterns studied and adopted into the existing/extended Three.js viewer**:
  - Selection hierarchy (whole object → component → round → stitch) — already implemented pre-slice (`viewer/src/state/store.ts`, isolate-round dropdown); this slice's `loadGeometryDocument` preserves that hierarchy across recompiles rather than rebuilding it as a NGL/VTK-style scene-graph object, since the flat instanced-mesh approach already satisfies it.
  - Colour-independent selection marker (Mol*/VTK.js both avoid colour-only selection indicators) — already implemented pre-slice (`selection/highlight.ts`'s wireframe torus).
  - Clipping-plane-relative-to-bounds UX (VTK.js's widget convention of expressing clip position as a fraction of the data's bounding box, not an absolute world coordinate) — already implemented pre-slice (`clipping/clipping.ts`); this slice's loader resets that fraction-relative-to-bounds state whenever bounds change (new pattern), matching the VTK.js convention that a clip widget re-derives its handle position from new data bounds rather than keeping a stale absolute position.
- **Not adopted**: neither framework was embedded; both remain reference material only, per the brief's explicit instruction not to copy their interfaces wholesale.
- **(Re-evaluated this slice)**: the new graph-overlay mode (`viewer/src/selection/graph_overlay.ts`, a bounded-neighbourhood highlight of a selected stitch's parents/children) is the same "focus + context" interaction VTK.js/Mol* use for selection halos and residue-neighbourhood highlighting — show the selected element clearly, dim or line-render the immediate structural neighbourhood, and leave the rest of the scene at normal rendering rather than isolating to an empty view. `graph_overlay.ts` follows that shape: it draws thin connector lines to bounded-depth parents/children of the selection rather than either (a) highlighting only the single selected stitch with no relational context, or (b) rebuilding the whole scene into a graph-only view. **Not adopted as code** — no graph-visualization library was added; the overlay is built directly from `StitchGraph` edges already present in `GeometryDocument`, reusing the existing `THREE.Line`-based approach `measurement/measurement.ts`'s measurement lines also use, rather than introducing a second line-rendering convention.

## Testing

### Playwright
- **Status**: **Adopted.**
- **License**: Apache-2.0.
- **Version pinned**: see `viewer/package.json` devDependencies.
- **Files**: `viewer/e2e/compile-workflow.spec.ts`.
- **Reason**: brief explicitly requires real-browser proof of the editor → API → live-geometry-replacement → selection workflow, which Vitest's jsdom environment cannot exercise (no real WebGL canvas, no real network round-trip through a running backend).
- **(Re-evaluated this slice)**: extended the existing spec with a second scenario covering the full crochet-specific inspection workflow — yarn mode, stitch selection with parent inspection, X-ray mode, a clipping plane, a stitch-to-stitch measurement, a quality change, then a recompile that must dispose the old geometry/measurement state and leave the new model interactive. Two implementation details worth recording for future test authors: (1) Playwright's `.fill()` does not support `<input type="range">`, so clipping-offset and similar range inputs are driven by a small helper that sets `.value` directly and dispatches synthetic `input`/`change` events; (2) a canvas-click probe helper must click **one offset at a time** and re-check application state after each click when driving a stateful two-click flow (like measurement mode) — probing all offsets in a batch before checking state let several pending/complete measurement cycles fire silently before the assertion ever looked, which the first version of this test hit as 4 recorded measurements instead of the expected 1.

## Deferred to the future diagram pipeline (not this slice)

### OpenCV, Tesseract, Detectron2, MMDetection
- **Status**: **Deferred**, exactly per the brief.
- **Recorded future pipeline**: `SVG diagram parsing → raster preprocessing with OpenCV → optional learned symbol detection (Detectron2/MMDetection, only once a licensed annotated dataset exists) → canonical Pattern/StitchGraph → existing geometry pipeline`. No code added this slice.
- **(Re-evaluated this slice)**: unrelated to this slice's stitch-geometry/viewer work (diagram recognition is a distinct, still-unstarted pipeline stage upstream of parsing). Re-checked only to confirm neither library became relevant as a side effect of the new frontend geometry code — it did not. **Verdict unchanged.**
- **(Re-evaluated again, SVG diagram ingestion slice)**: this slice implements the **vector-SVG half** of the pipeline sketched above (`SVG diagram parsing → ... → canonical Diagram IR → existing StitchGraph pipeline`), explicitly *without* raster preprocessing, OCR, or machine learning — the brief for this slice was explicit that raster/photograph/PDF/OCR input remains out of scope. OpenCV/Tesseract/Detectron2/MMDetection therefore remain exactly as deferred as before; nothing in this slice's own scope needed them, and nothing in this slice changes when they'd become relevant (only a future raster-ingestion slice would revisit this). **Verdict unchanged: still deferred.**

### glTF / glTF-Validator
- **Status**: **Deferred.**
- **Design constraint honoured now**: `GeometryDocument` (`geometry/models.py`) stores plain position/orientation/radius/material-reference data with no Three.js-specific or parser-specific types leaking into it, so a future glTF exporter could be written as a pure consumer of `GeometryDocument` without touching `parsing/`, `graph/`, or `geometry/layout.py`. No exporter was written this slice.
- **(Re-evaluated this slice)**: `GeometryDocument` itself (the backend-defined type, `viewer/src/types/geometry.ts`) was **not** widened this slice — it still carries only plain position/orientation/radius/material-reference data. The new geometry-strategy/path-role metadata (surfaced in the inspector's "Geometry strategy"/"Path roles" rows) lives entirely in `StitchPathResult` (`viewer/src/geometry/stitch_paths/types.ts`), computed client-side from `GeometryDocument` plus each stitch's `StitchFamily`, and never sent to or stored by the backend. This actually *strengthens* the design constraint rather than complicating it: a future glTF exporter consuming `GeometryDocument` would need no changes at all to accommodate this slice, since none of its new data lives on that type. **Verdict unchanged: still deferred**, no exporter written.

## Summary table

| Resource | Status | License (reported) | Files influenced |
|---|---|---|---|
| CrochetPARADE | Design reference (re-evaluated) | GPLv3 | none (concept only) |
| CrochetBench | Deferred (re-evaluated) | Unconfirmed | none |
| AmiGo | Design reference (re-evaluated) | N/A (paper) | `docs/stitch-graph-spec.md` (no code change) |
| Crochet Charts/CAD/simulator | Rejected (re-evaluated: licensing, not scope, now) | GPLv3 / CC BY-SA 4.0 | none |
| Craft Yarn Council symbol standard | **Adopted, terminology only** (new this slice) | Proprietary artwork, not redistributed | `diagram/ontology.py` |
| Digital Crochet / graph-layout research | Design reference (new this slice) | N/A (research) | none (concept only) |
| Lark | **Adopted** | MIT | `parsing/written/grammar.lark`, `parsing/written/parser.py` |
| defusedxml | **Adopted** (new this slice) | PSF-2.0 | `diagram/svg_parser.py` |
| ANTLR / Parsimonious | Rejected | BSD-3 / MIT | none |
| spaCy | Deferred | MIT | none |
| NetworkX | Rejected | BSD-3 | none |
| Trimesh/PyVista/libigl/Eigen/pybind11 | Rejected (no current need) | MIT/MIT/MPL2/MPL2/BSD | none |
| PBD/XPBD/rods/Laplacian | Deferred | MIT (PBD ref impl) | none |
| JSON Schema (via Pydantic) | **Adopted**; now committed + match-tested artefacts (re-evaluated this audit) | N/A (spec) | `api/schema_export.py`, `schemas/*.schema.json` |
| RFC 8785 | Audited, not adopted; test vectors extended | IETF standard | `docs/canonical-json-audit.md`, `tests/test_canonical_json.py` |
| Three.js | Already adopted (prior milestone) | MIT | `viewer/src/**` |
| Three.js `TubeGeometry`/Frenet frames | **Rejected** (re-evaluated) | MIT | `viewer/src/geometry/parallel_transport_tube.ts` (custom replacement) |
| Three.js `MeshPhysicalMaterial` | **Adopted** (re-evaluated) | MIT | `viewer/src/materials/yarn_material.ts` |
| Three.js raycasting / clipping planes | **Adopted, mechanism changed for picking** (re-evaluated) | MIT | `selection/hit_proxies.ts`, `selection/picking.ts`, `app/App.ts` (`pickStitch`), `clipping/clipping.ts` |
| gl-matrix | Rejected | MIT | none |
| postprocessing/N8AO/three-mesh-bvh/pathtracer | Deferred (three-mesh-bvh re-evaluated again: measured problem solved without it) | MIT/MIT/MIT/MIT | none |
| VTK.js/Mol*/ParaView/MeshLab/NGL | Design reference (re-evaluated) | BSD-3/MIT/BSD/GPL-3/MIT | `selection/highlight.ts`, `clipping/clipping.ts`, `selection/graph_overlay.ts` |
| Playwright | **Adopted**, extended this slice | Apache-2.0 | `viewer/e2e/compile-workflow.spec.ts` |
| OpenCV/Tesseract/Detectron2/MMDetection | Deferred (re-checked, unaffected) | Apache-2.0 (all) | none |
| glTF/glTF-Validator | Deferred (re-checked, constraint strengthened) | Khronos/Apache-2.0 | none (`GeometryDocument` unwidened; new metadata kept frontend-only) |
| PROV-JSON | **Rejected** (new this slice) | W3C Document License | none |
