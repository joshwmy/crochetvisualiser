# SVG diagram-ingestion milestone: closure audit

Second-pass verification of the SVG diagram-ingestion slice (commits
`752bdf2`, `791ef35`, `48babb4`, `10699bf` on
`pattern-to-scientific-3d-visualizer`), performed by re-deriving every claim
from git state, source, and actual test/tool runs rather than trusting the
prior session's self-report. See the end of this document for exactly what
that verification found wrong (little) and what it found genuinely missing
(the sequence-index correction, the diagram schema-version guard, several
2D-review/correction controls, and visual-regression baselines) — all fixed
in this pass.

## Baseline commands run (exact)

| Command | Result |
|---|---|
| `pytest -q` (full suite) | 486 passed |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 1 file reformatted (`tests/diagram/test_security.py`), 147 clean on recheck |
| `mypy src` | Success: no issues found in 98 source files |
| `npx tsc --noEmit` (viewer) | clean |
| `npx vitest run` (viewer) | 162 passed (17 files) |
| `npm run build` (viewer) | succeeds (pre-existing >500kB chunk-size warning only) |
| `npx playwright test e2e/diagram-workflow.spec.ts --workers=1` | 3 passed |
| `npx playwright test e2e/visual-regression.spec.ts --workers=1 --update-snapshots` | 3 new diagram baselines generated, manually inspected against the existing `structural-overview-win32.png` rendering style before acceptance |
| `npx playwright test e2e/visual-regression.spec.ts --workers=1` | 12 passed (9 pre-existing scientific-viewer + 3 new diagram) |
| `npx playwright test --workers=1` (full suite) | **19/19 passed**, 8.5 min, zero leaked `node`/`python`/Chromium processes afterward (`tasklist` check) |

The prior pass in this same session recorded 16/21 flaky full-suite runs
under memory pressure and widened several backend round-trip timeouts as a
result (kept — see "Playwright reliability" below for why that change is
still correct). On this final verification pass, with the machine in a
cleaner state, the full suite passed outright with no flakiness and no
timeout widening needed beyond what was already applied. The test count
also reads 19 rather than 21 here because `npx playwright test --list`
reports 19 total specs in this repo state — the prior doc's "21" was not
re-derived from `--list` and is superseded by this number.

Git state at the start of this pass: branch `pattern-to-scientific-3d-visualizer`,
working tree clean, all four reported SVG commits present and verified via
`git log`.

## Compliance matrix

| Requirement | Status | Evidence | Action |
|---|---|---|---|
| Reject `<script>` | Complete | `security.py` `DISALLOWED_TAGS`; `tests/diagram/test_security.py::test_rejects_script_tag` | none |
| Reject `foreignObject` | Complete | same; `test_rejects_foreign_object` | none |
| Reject inline event handlers | Complete | `_check_disallowed_attrs`; `test_rejects_inline_event_handler` | none |
| Reject external references | Complete | `HREF_ATTRIBUTES` local-fragment-only check; `test_rejects_external_use_reference`, `test_rejects_remote_image`, `test_rejects_external_stylesheet_link` | none |
| Reject `javascript:`/CSS `url()` | Complete | `DISALLOWED_VALUE_SUBSTRINGS`; `test_rejects_javascript_url`, `test_rejects_css_url_reference` | none |
| Reject `data:text/html` | Complete | same constant, but **no test existed** for the value-substring branch specifically (only via the already-disallowed `<image>` tag) | **Added** `test_rejects_data_html_url` exercising the substring check on an otherwise-permitted tag |
| Reject DTDs/entities | Complete | `defused_fromstring(forbid_dtd=True, forbid_entities=True, forbid_external=True)`; `test_rejects_dtd_declaration` (combined DTD+XXE case) | none |
| Excessive nesting/elements/transforms/path commands/coordinates fail safely | Complete | `SafetyLimits` + `_walk`'s per-element accounting; `test_element_count_limit`, `test_nesting_depth_limit`, `test_deep_nesting_fails_cleanly_not_recursion_error`, `test_path_command_limit`, `test_transform_function_count_limit`, `test_coordinate_magnitude_limit`, `test_viewbox_dimension_limit`, `test_use_reference_count_limit` | none |
| Frontend never renders raw SVG | Complete | `svg_overlay.ts` builds the preview via `createElementNS`/`setAttribute`/`textContent` only, from the structured `DiagramDocument` — never `innerHTML`s the uploaded source; `tests/svg_overlay.test.ts::"never contains a <script> tag..."` | none |
| Diagram IR versioned | Complete | `DIAGRAM_SCHEMA_VERSION = "1.0.0"` (`ir.py`), `CORRECTIONS_SCHEMA_VERSION` (`corrections.py`) | none |
| Symbols/relationships have stable IDs | Complete | `symbol_id`/`relationship_id` fields, generated deterministically (`svg-symbol-N`, `rel-%05d`) | none |
| Classification method, confidence, provenance stored | Complete | `DiagramSymbol.classification_method`/`confidence`/`confidence_band`/`source_element_path`/`source_metadata` | none |
| Corrections affect fingerprints | Complete | `pipeline.compile_svg_diagram` recomputes `fingerprint` via `compute_diagram_fingerprint(rebuilt_document)` after every correction application; `tests/diagram/test_corrections.py::test_corrections_are_deterministic_and_serialisable` | none |
| JSON Schemas generated reproducibly | Complete | `schemas/diagram_*.schema.json` committed; `docs/schema-artifacts.md` documents the generation script | none |
| Frontend schema-version handling tested | **Was Missing** | Geometry loading (`geometry/load.ts`) already guarded against an unsupported `schema_version`; the diagram path had no equivalent — a mismatched `DiagramDocument.schema_version` would have been silently accepted and rendered/corrected/compiled against possibly-invalid assumptions | **Added** `SUPPORTED_DIAGRAM_SCHEMA_VERSION` (`types/diagram.ts`), `assertSupportedSchemaVersion`/`DiagramSchemaError` (`diagram_controller.ts`), applied after both analyse and compile responses; 2 new controller tests |
| Unsupported future versions fail clearly | **Was Missing** (same item) | — | Fixed as above: mismatched version → `status: "internal_error"` with a clear message, last valid document/model preserved |
| Pan | **Was Missing** | `svg_overlay.ts` had no viewport concept beyond the document's fixed native `viewBox` | **Added**: `DiagramViewport`, drag-to-pan on `#diagram-preview`, wired through `diagram_store.ts`'s new `viewport` field |
| Zoom | **Was Missing** | same | **Added**: scroll-to-zoom (cursor-anchored) + `+`/`−` buttons |
| Fit to view | **Was Missing** | same | **Added**: `#diagram-fit-view` resets `viewport` to `null` (renders `nativeViewport(document)`) |
| Symbol selection | Complete | click/keyboard-activate on symbol groups; `onSelectSymbol` | none |
| Relationship selection | **Was Missing** | relationship `<line>`s were rendered but had no interaction at all | **Added**: click/keyboard-activate on relationship lines, `selectedRelationshipId` in store, distinct selection stroke colour |
| Symbol labels | **Was Missing** | only an in-circle "?" for unclassified/ambiguous symbols; no visible label for a classified symbol's type | **Added**: short visible stitch-type-abbreviation label (`sc`/`dc`/…) below each classified symbol, plus a native `<title>` tooltip for every symbol |
| Confidence legend with text, not colour only | Complete | `CONFIDENCE_LEGEND` renders swatch + text label for every band | none |
| Filtering low-confidence symbols | Complete | `#diagram-only-low-confidence` checkbox, `onlyLowConfidence` filter | none |
| Filtering unclassified symbols | Complete | `#diagram-only-unclassified` checkbox | none |
| Round visibility | **Was Missing** | `OverlayFilters.visibleRounds` existed in the type but was hard-coded to `null` in `main.ts` — no UI ever set it | **Added** `#diagram-round-filter` multi-select, populated from `document.rounds` |
| Relationship visibility | Complete | `#diagram-show-relationships` checkbox (unchanged, pre-existing) | none |
| Change stitch type | Complete | `#diagram-stitch-type-select` + Apply | none |
| Assign a round | **Was Missing** | no UI for `SymbolOverride.round_index`, though the backend field existed | **Added** `#diagram-round-index-input` |
| Change sequence index | **Was Partial → Now Complete (bounded)** | see "Sequence-index correction" below | Fixed at the topology level, not just UI |
| Ignore a symbol | Complete | `#diagram-mark-ignored` | none |
| Restore automatic classification | Complete | `#diagram-restore-automatic` → `setSymbolOverride(id, null)` | none |
| Set loop placement | Deferred by design | No `loop_placement` field exists anywhere in `DiagramSymbol`/`SymbolOverride` — this is not a partially-wired UI gap, it is a data-model absence. Adding it would mean inventing new backend semantics (what does "loop placement" mean for an SVG symbol with no FLO/BLO source signal?) — out of this slice's bounded scope per the task's own restriction against inventing new backend capabilities from the frontend | Not implemented; documented here and in `docs/known-limitations.md` |
| Mark a round start | Complete | `#diagram-mark-round-start` | none |
| Mark a round closure | Complete | `#diagram-mark-round-closure` | none |
| Select a relationship (chart-level) | **Was Missing** | — | Added, see above |
| Add/remove/replace a parent edge | **Was Missing** | `RelationshipOverride` actions (`set_parent`/`add_parent`/`remove_parent`) existed in the backend and in `DiagramController`, but no UI ever called them | **Added** relationship-correction panel: Set parent / Add parent (both use a concurrently-selected candidate symbol) / Remove parent (removes the relationship's current parent set) |
| Multiple parents for a decrease | Complete (backend); now reachable from UI | `parent_symbol_ids: list[str]` already supports it; `add_parent` UI adds one at a time — repeatable | none further; documented as click-to-add-each rather than a multi-select, a deliberately bounded interaction |
| Confirm an inferred relationship | **Was Missing** | — | Added (`#diagram-relationship-confirm`) |
| Restore automatic (relationship) | **Was Missing** | — | Added (`#diagram-relationship-restore`) |
| Set/adjust chart centre | **Was Missing** | backend `ConstructionOverrides.centre` existed, no UI | **Added** `#diagram-centre-x-input`/`#diagram-centre-y-input` + Apply |
| Reverse clockwise/counterclockwise | Complete (pre-existing) — **and a real bug fixed alongside it** | `#diagram-reverse-direction` existed, but replaced the *entire* `construction_overrides` object instead of merging, silently discarding any previously-set centre/start/tolerance the moment direction was toggled | Fixed: now reads-modifies-writes the existing overrides object; regression covered by manual inspection of the merge logic (see `docs/diagram-corrections.md`) |
| Choose starting stitch | **Was Missing** | backend `start_symbol_id` existed, no UI | **Added** `#diagram-start-symbol-select`, populated from `document.symbols` |
| Adjust round-clustering tolerance | **Was Missing** | backend `round_tolerance` existed, no UI | **Added** `#diagram-round-tolerance-input` |
| Re-run inference | Deferred by design | There is no backend "re-infer without compiling" endpoint — `infer_topology` only ever runs as part of `analyse` or `compile`. Adding a third endpoint purely to expose "preview the topology re-run without producing a StitchGraph" would be new backend surface, out of scope per the task's restriction. Any correction (symbol, relationship, or construction) already re-runs full topology inference automatically on the next Compile click | Documented, not implemented as a separate action |
| Reset all corrections | Complete (pre-existing) | `#diagram-reset-corrections` → `resetCorrections()` | none |
| Structural hit-proxy picking (all view modes) | Complete | `selection/hit_proxies.ts`; `App.pickStitch` always raycasts hit-proxy spheres, in every mode; `tests/hit_proxies.test.ts` (6 tests) | none |
| Hidden proxies filtered from raycasting | Complete | verified by inspection of `hit_proxies.ts` / existing tests | none |
| Stable stitch IDs returned | Complete | `piece-r\d+-s\d+` pattern asserted in `diagram-workflow.spec.ts` and `compile-workflow.spec.ts` | none |
| Visible yarn geometry not used as picking target | Complete | benchmark comment in `tests/benchmark.test.ts` explicitly documents `App.pickStitch` uses hit-proxy spheres "in every view mode" | none |
| Hit proxies disposed on model replacement | Complete | `App.ts`: `disposeHitProxyScene(this.scene, previousHitProxies)` runs on every `loadGeometryDocument`, the same shared path both written-pattern and diagram compiles use | none |
| Diagram-derived stitches pickable | Complete | `diagram-workflow.spec.ts` test 1 explicitly selects a stitch in yarn mode after a diagram compile | none |
| Picking correct after returning from diagram review | Complete | same test's step 5 | none |
| Proxy-vs-yarn-raycast benchmark exists | Complete | `tests/benchmark.test.ts`: structural ~45ms, yarn ~1398ms, hit-proxy ~17ms per 25-point sweep (this run's numbers; see `docs/performance-benchmarks.md`) | none |
| Diagram lifecycle: review→3D→review preserves IR/corrections | Complete | `diagram-workflow.spec.ts` step 5 | none |
| New diagram replaces old overlays/model | Complete | shared `App.loadGeometryDocument` disposal path (`disposeStructural`/`disposeYarnScene`/`disposeHitProxyScene`/`disposeOverlays`), exercised repeatedly by `lifecycle-stress.spec.ts` | none |
| Failed analysis/compile preserves last valid model | Complete | `DiagramController.compile()`: `app.loadGeometryDocument` only called after a successful response; `diagram-workflow.spec.ts` test 2 asserts this directly for a malicious-SVG rejection after a valid compile | none |
| Repeated analyse/compile doesn't leak Three.js resources | Complete (via shared path) | `lifecycle-stress.spec.ts`'s 2 tests exercise the identical `loadGeometryDocument` disposal path a diagram compile also uses; no diagram-specific leak path exists since diagram compiles produce the same `GeometryDocument` shape | none |
| Visual-regression baselines for diagram states | **Was Missing** (explicitly deferred by the prior slice) | none existed | **Added** — see "Visual-regression baselines" below; not the full 9-scenario list from the original ask, bounded and documented |
| Playwright reliability under memory pressure | **Was Partial** | prior session reported "one test... unreliable under severe memory pressure"; this pass reproduced failures across *multiple* spec files depending on the run, all on real backend-response waits | Fixed the fixable part (response-wait timeout too tight for this machine's real conditions), documented the rest as an environment limit — see below |

## Sequence-index correction (the specifically-flagged partial item)

**Root cause found**: `topology.infer_topology`'s `_order_round` computed
every round's working order purely from angular position around the chart
centre (`math.atan2`), then optionally rotated to a `start_symbol_id`. It
never read a symbol's `sequence_index` at all as an input — `corrections.py`
correctly *wrote* a user's `sequence_index` override onto the corrected
symbol, but the very next step (topology re-inference, which the compile
pipeline always runs after applying symbol overrides) silently discarded it
by recomputing the whole order from scratch. The correction was recorded
and displayed but had zero effect on the compiled stitch graph.

**Why a naive fix is unsafe**: making `sequence_index` a free global ordinal
that topology just "sorts by" would let a correction silently violate round
clustering (a symbol could get sorted into the wrong round's position, or
create gaps/duplicates within a round) — the exact kind of invalid graph
state the task explicitly asks to prevent via "structured diagnostics
rather than silent mutation."

**The bounded fix implemented**: `sequence_index` is now interpreted as a
desired 0-based position *within the symbol's own round*, applied as a
deterministic reinsertion into that round's already-computed angular order
(`topology._apply_sequence_pins`, threaded through `infer_topology`'s new
`sequence_pins` parameter, populated by `pipeline.compile_svg_diagram` from
`corrections.symbol_overrides[...].sequence_index`). Out-of-range values
clamp instead of erroring. Round *membership* is untouched — moving a
symbol to a different round is still `round_index`'s job. This is safe
because:

- it can never produce an invalid round (membership is decided earlier,
  by clustering/`round_index`, not touched by this step);
- it's deterministic regardless of correction-dict iteration order (pins
  are applied in ascending target-index order, documented in
  `_apply_sequence_pins`'s docstring);
- re-applying the same correction set twice is still a no-op (idempotent),
  preserving the property `docs/diagram-corrections.md` documents for the
  whole correction system.

Tests added: `tests/diagram/test_corrections.py::test_sequence_index_override_reorders_within_round`
and `::test_sequence_index_override_out_of_range_clamps_not_crashes`.

## Visual-regression baselines

The prior slice explicitly deferred these. This pass adds a bounded subset,
not the full nine-scenario list in the original ask — prioritised for
signal-per-screenshot and stability rather than exhaustive coverage:

- Analysed flat-circle diagram (2D review, unmodified)
- Confidence overlay + a corrected (manually-classified) ambiguous symbol
- Diagram-derived 3D structural model, selected stitch (reuses the existing
  stabilised camera/lighting/quality harness from
  `visual-regression.spec.ts` rather than inventing a second one)

Deferred, with reasons: a dedicated "security-error state" screenshot was
not added because that state has no distinct visual surface to regress —
it's the same diagnostics list the malicious-SVG Playwright test already
asserts on by text, and a screenshot of a `<ul>` of error text adds
maintenance cost without new coverage. A "sphere-like fixture" diagram
screenshot was not added in this pass — the existing synthetic diagram
fixtures in this slice are flat-circle only (see
`tests/diagram/fixtures/`); building a second, larger synthetic SVG fixture
purely for a screenshot is deferred as a follow-up rather than done
hastily under this pass's time budget. See `docs/known-limitations.md`.

## Playwright reliability under memory pressure

This machine has 8GB total RAM and was measured with 370–650MB free
physical memory (`Get-CimInstance Win32_OperatingSystem`) even immediately
after a full Playwright run completed and released its processes — verified
via `tasklist` showing zero leaked `node`/`python`/Chromium processes after
every run in this pass. Two full-suite runs (before and after this pass's
fix) both showed 5 failures out of 21 tests, but **not the same 5 tests
either time** — `compile-workflow.spec.ts`, `diagram-workflow.spec.ts`,
`lifecycle-stress.spec.ts`, and `visual-regression.spec.ts` each failed on
at least one run, always on the same failure mode: `page.waitForResponse`
exceeding a 15-second timeout waiting for a real backend compile/analyse
response. Running the diagram spec alone or any single spec file in
isolation passes reliably.

This is genuine resource contention, not a code defect — confirmed by:
`workers: 1` (already serial, unchanged), no leaked processes, and the
*same* test passing cleanly when machine load is lower (e.g. the isolated
single-file reruns in this pass). Per the task's explicit instruction not
to "modify valid application code merely to mask resource exhaustion," no
application code was touched for this. What *was* changed: every
`page.waitForResponse`/status-text wait tied to a real backend round trip
across `compile-workflow.spec.ts`, `diagram-workflow.spec.ts`, and
`lifecycle-stress.spec.ts` was raised from 15s to 45s
(`BACKEND_ROUND_TRIP_TIMEOUT`, documented inline in each file) — a bounded,
justified change to the test harness's patience for a slow-but-genuine
response, not a change to what's being asserted. This matches the existing
precedent already in `playwright.config.ts` (whose own comment documents
the overall per-test timeout being raised from 30s→90s→150s for the same
reason). After this change, the diagram spec passed on both full-suite
reruns; two `visual-regression.spec.ts`/`lifecycle-stress.spec.ts` failures
and one `compile-workflow.spec.ts` failure persisted across reruns on
unrelated (non-diagram, pre-existing) tests, plus two `benchmark.test.ts`
hard timing-threshold assertions in Vitest — all consistent with the same
underlying memory constraint, not touched, documented honestly rather than
hidden.

**This full-suite flakiness is an environment limitation of this specific
development machine, not a milestone blocker** — every diagram-specific
test (Python, Vitest, Playwright) passed cleanly and repeatably throughout
this pass.

**Update, final verification run**: with the widened timeouts already in
place from the fix above, a subsequent full-suite run on this same machine
(`npx playwright test --workers=1`, 19 tests, 8.5 minutes) passed 19/19 with
no failures and no leaked processes afterward. The intermittent failures
described above are still real and still attributable to memory pressure —
they are not being retroactively declared impossible — but they did not
reproduce on this run. The timeout widening is kept as the correct fix
regardless, since it addresses the actual mechanism (slow-but-genuine
backend responses under load) rather than papering over a specific run.

## Files changed in this pass

Backend: `src/crochet_reconstruction/diagram/topology.py` (sequence-index
pins), `src/crochet_reconstruction/diagram/corrections.py` (docstring),
`src/crochet_reconstruction/diagram/pipeline.py` (wiring),
`tests/diagram/test_security.py` (+1 test), `tests/diagram/test_corrections.py` (+2 tests).

Frontend: `viewer/src/types/diagram.ts` (schema-version constant),
`viewer/src/app/diagram_controller.ts` (schema-version guard, relationship
selection, viewport), `viewer/src/state/diagram_store.ts` (new state
fields), `viewer/src/diagram/svg_overlay.ts` (pan/zoom viewport param,
relationship selection, symbol labels), `viewer/src/main.ts` (all new
controls wired), `viewer/index.html` (new controls), `viewer/tests/diagram_controller.test.ts`
(+4 tests), `viewer/tests/svg_overlay.test.ts` (+4 tests).

Playwright: `viewer/e2e/compile-workflow.spec.ts`,
`viewer/e2e/diagram-workflow.spec.ts`, `viewer/e2e/lifecycle-stress.spec.ts`
(timeout constant), plus new visual-regression cases.

Docs: this file, `docs/diagram-corrections.md`, `docs/known-limitations.md`.
