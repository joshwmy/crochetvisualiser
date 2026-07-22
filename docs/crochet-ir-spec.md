# Crochet IR specification

## What "IR" means here

The canonical crochet representation is the compiled `Pattern` object
(`src/crochet_reconstruction/domain/pattern.py`), produced today only by
`engine.compiler.compile_pattern` from a structured `ProjectInput`. This
document describes what it currently contains, what it deliberately does
not yet contain, and how the new `graph`/`geometry` packages extend it
without modifying it.

**This IR was audited, not replaced.** The pivot's first requirement was to
determine whether the existing Phase 1 domain model was reusable for
stitch-level rendering. It is — with one addition (`graph.models.StitchGraph`,
described in `stitch-graph-spec.md`) layered on top, never inside it.

## Structure (unchanged from Phase 1)

```
Pattern
├── schema_version            "0.1.0"
├── input: ProjectInput       measurements, gauge, template, terminology, yarn/hook metadata
├── calculated: CalculatedParameters   every derived sizing value
├── assumptions: list[Assumption]
├── components: list[Component]
│   ├── kind: ComponentKind   crown | body | brim
│   ├── construction: Construction   continuous_rounds | joined_rounds
│   └── rounds: list[Round]
│       ├── number
│       ├── operations: list[Operation]   MagicRingOp | StitchOp | IncreaseOp | DecreaseOp | RepeatOp
│       ├── stated_total
│       └── closure: ClosureKind   none | slip_stitch_join
├── validation: ValidationReport | None
└── fingerprint: str | None   SHA-256 over canonical JSON
```

## What the IR does NOT record (and why the graph package exists)

Every `Operation` is an **aggregate** — `StitchOp(count=8)` means "8 plain
stitches," not eight individually identified stitches. `IncreaseOp(input=1,
output=2)` means "work 2 stitches into 1 previous-round stitch," but never
says *which* previous-round stitch by ID. This was a deliberate Phase 1
design (the validator only ever needed aggregate counts), confirmed by
direct code audit before this pivot began — not an oversight discovered
during the pivot.

Because stitch-level 3D rendering needs per-stitch identity, insertion
targets, and sequence order, `crochet_reconstruction.graph.builder` expands
this aggregate IR into an explicit `StitchGraph` (see
`stitch-graph-spec.md`) — a **derived**, reproducible representation, never
a second source of truth. The `Pattern` object remains authoritative;
rebuilding its graph from the same `Pattern` always produces an identical,
fingerprinted result.

## Future input routes (not built in this milestone)

The longer-term product accepts written patterns and diagrams in addition
to structured JSON (see `docs/product-boundary.md` for the full roadmap).
All three routes are required to compile into this same `Pattern` IR before
anything downstream (graph, geometry, rendering) runs — a written-pattern or
diagram parser is a *producer* of a `ProjectInput`/`Pattern`, never a
separate code path that bypasses deterministic validation. Nothing in this
milestone begins that parsing work.
