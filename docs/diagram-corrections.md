# Diagram corrections

The versioned override model that lets a user fix an uncertain automatic
interpretation before compiling — and the deterministic order it's applied
in. See `src/crochet_reconstruction/diagram/corrections.py` for the
authoritative implementation, `schemas/diagram_correction_set.schema.json`
for the committed JSON Schema, and `viewer/src/app/diagram_controller.ts` /
`viewer/src/types/diagram.ts` for the frontend counterpart.

```text
Automatic interpretation
→ confidence and diagnostics
→ user corrections
→ deterministic corrected Diagram IR
→ 3D compilation
```

`CORRECTIONS_SCHEMA_VERSION = "1.0.0"`. No server-side persistence: a
`DiagramCorrectionSet` only ever exists within one compile request/response
round-trip — the brief's explicit "no server-side persistence required."
The frontend keeps it in-memory (`DiagramState.corrections`,
`diagram_store.ts`) for the duration of a review session.

## Shape

```json
{
  "schema_version": "1.0.0",
  "symbol_overrides": {
    "svg-symbol-12": { "stitch_type": "single_crochet", "round_index": 2 }
  },
  "relationship_overrides": [],
  "construction_overrides": { "centre": [400, 400], "direction": "counterclockwise", "start_symbol_id": "svg-symbol-1" }
}
```

## `SymbolOverride`

All fields optional; only the ones set are applied (`corrections.py`'s
`apply_symbol_overrides` builds an update dict from only the non-`None`
fields). Setting `stitch_type` also resets the symbol's
`classification_method` to `manual_override`, `confidence` to `1.0`,
`confidence_band` to `"manual"`, and clears `ambiguous`/`unsupported` —
a correction is never re-scored against the automatic confidence scale.

| Field | Effect |
|---|---|
| `stitch_type` | Reclassifies the symbol. |
| `round_index` | Explicit round assignment (also feeds round clustering on the next inference pass — see below). |
| `sequence_index` | Desired 0-based working-order position **within the symbol's own round** (after any `round_index` override) — applied as a bounded reinsertion into that round's already-inferred angular order (`topology._apply_sequence_pins`). Out-of-range values clamp to the round's valid index range rather than erroring. Does not move a symbol across rounds — that's `round_index`'s job. |
| `ignored` | Excludes the symbol entirely from the compiled graph (it is dropped from the corrected symbol list, not just marked). |
| `round_start` | Marks/unmarks this symbol as the round's starting stitch — rotates that round's angular order. |
| `round_closure` | Marks/unmarks this symbol as an explicit round-closure marker. |

## `RelationshipOverride`

| Action | Effect |
|---|---|
| `set_parent` | Replaces the symbol's parent list entirely. |
| `add_parent` | Adds parent id(s) not already present. |
| `remove_parent` | Removes parent id(s) from the current list. |
| `set_children` | The reverse operation: adds this symbol as a parent of each listed child (used to set up an increase from the parent's side). |
| `confirm` | No-op on the parent map — records user intent that an automatic result was reviewed and accepted, without changing it. |
| `restore_automatic` | No-op on the parent map, by design — see "Application order" below for why this doesn't need special-case bookkeeping. |

Referencing an unknown `symbol_id`/parent/child id produces a
`MANUAL_CORRECTION_CONFLICT` diagnostic (error, blocking) rather than being
silently ignored.

The frontend exposes these through the relationship-selection panel:
clicking a relationship line/list entry selects it; `set_parent`/
`add_parent` use whichever symbol is currently *also* selected (symbol and
relationship selection are independent, not mutually exclusive, precisely
so both can be picked at once); `remove_parent` removes exactly the
relationship's currently-shown parent set; `confirm`/`restore_automatic`
need no second selection. Only `parent_attachment`/`centre_attachment`
relationships are correctable this way — `horizontal_neighbor`/
`round_closure`/`yarn_sequence` are structural bookkeeping, not
parent edges, so the panel disables the correction buttons for them.

## `ConstructionOverrides`

`centre`, `direction`, `start_symbol_id`, `round_tolerance` — any set field
feeds back into a full re-run of `topology.infer_topology` (see below),
since changing the centre or direction can invalidate round clustering and
ordering entirely; there is no cheaper partial-update path for these.

The frontend's "Reverse round direction" and "Apply chart settings"
controls both **merge** into the existing `construction_overrides` object
(read-modify-write against `state.corrections.construction_overrides`)
rather than replacing it outright — an earlier version of the reverse-
direction handler replaced the whole object with `{ direction: ... }`,
which silently discarded any previously-set centre/start/tolerance
override the moment direction was toggled. Fixed alongside adding the
chart-construction panel.

## Deterministic application order

This is the part the brief specifically asks to be documented, since
correction application must be idempotent (re-applying the same set twice
is a no-op) and order-independent in the sense that the *result* doesn't
depend on incidental dict/list ordering within the correction set itself.

1. **`construction_overrides`** first — centre/direction/start feed
   straight into a fresh `infer_topology` call, since they can invalidate
   round clustering and parent attachment entirely; a full re-run is the
   only correct way to apply them.
2. **`symbol_overrides`** next, applied to the symbol list *before* that
   same topology re-run — so a corrected stitch type or round participates
   correctly in parent-attachment and round-clustering for every other
   symbol too (a symbol that was ambiguous can be fixed and then correctly
   act as a neighbour's parent in the same pass).
3. **`relationship_overrides`** last, applied *after* the topology re-run
   — final, explicit edits layered on top of the (re-)inferred
   relationships. They never feed back into inference itself, which is
   exactly what keeps this step idempotent: re-applying the same
   `set_parent` override to an already-corrected parent map is a no-op.

`pipeline.compile_svg_diagram` implements this order directly; see its
docstring and `corrections.py`'s module docstring for the same reasoning
recorded at the code level.

### Why `restore_automatic`/`confirm` need no special bookkeeping

By the time `relationship_overrides` are applied (step 3), the parent map
already **is** the freshly re-inferred automatic result — corrections
don't mutate a "live" state that needs restoring, they're recomputed from
scratch against the corrected symbols every time. So "restore automatic"
simply means "don't include an override for this relationship" (or set one
with action `restore_automatic`, which is a documented no-op) — there is
no separate "was this automatic or corrected" flag to reset.

## Compile-time re-derivation of blocking diagnostics (a real bug this caught)

The original implementation carried `document.diagnostics` (produced once,
at analyse time) forward unchanged into the compile response. This meant
correcting a symbol's stitch type would leave its now-stale
`UNCLASSIFIED_SYMBOL` diagnostic in the response — cosmetically wrong —
and, more seriously, an *uncorrected* unclassified symbol would silently
stop blocking compile after any unrelated correction was applied, because
`is_worked_stitch(None)` simply excludes an unresolved symbol from
topology/compilation without itself raising a fresh diagnostic (extraction
only runs once, at analyse time — topology re-inference doesn't re-check
classification). Fixed: `pipeline.compile_svg_diagram` now re-derives
blocking diagnostics directly from the *corrected* symbol list after every
compile request — any symbol still `stitch_type is None` after corrections
are applied gets a fresh `UNCLASSIFIED_SYMBOL`/`AMBIGUOUS_SYMBOL`
diagnostic, and a symbol that *was* corrected simply doesn't reappear,
since it now has a resolved type. See
`tests/diagram/test_corrections.py::test_compile_blocked_by_unresolved_symbol`
and `test_symbol_type_correction_unblocks_compile` for the regression
coverage, and `pipeline.py`'s inline comment for the full explanation.

## Frontend correction UI

`viewer/src/diagram/svg_overlay.ts` renders the safe 2D preview (see
`docs/svg-security.md` for why it's safe); `viewer/src/app/diagram_controller.ts`
owns the correction-mutation methods
(`setSymbolOverride`/`addRelationshipOverride`/`setConstructionOverride`/
`resetCorrections`) and the analyse/compile network round-trip;
`viewer/src/main.ts`'s `wireDiagramWorkflow` wires the DOM (symbol list,
relationship selection/correction panel, correction form, confidence
legend, pan/zoom/fit-to-view preview, round-visibility filter, chart-level
construction controls, compile/return-to-review buttons) to that
controller. A failed compile never touches the
existing 3D viewer (`App.loadGeometryDocument` is only called after a
successful compile response) — the previous valid model, if any, stays
exactly as it was; see `viewer/tests/diagram_controller.test.ts`'s
"a failed compile never touches the viewer" test.
