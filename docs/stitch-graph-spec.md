# Stitch-graph specification

Package: `src/crochet_reconstruction/graph/` (`models.py`, `builder.py`,
`validation.py`, `fingerprint.py`, `errors.py`).

## Purpose

A deterministic, derived, per-stitch expansion of a compiled `Pattern`.
Reproducible: identical `Pattern` input always produces an identical graph
and an identical `graph.fingerprint`. Never stored as a second source of
truth — always regenerated from the `Pattern`.

## The insertion-target assumption (read this before extending the builder)

The IR (see `crochet-ir-spec.md`) never states which specific previous-round
stitch an increase/decrease/plain-stitch targets — only aggregate counts.
`graph.builder` resolves this by consuming the previous round's stitches
**strictly left-to-right**, in worked order. This is safe for every pattern
the current compiler produces (crown/body schedules are worked in one
direction with no back-tracking), and is recorded explicitly on every node
as `target_rule: "deterministic_left_to_right"` rather than presented as
IR-given fact. A future written-pattern or diagram parser producing
out-of-order or ambiguous instructions **must not** reuse this builder
without re-examining that assumption — see the module docstring in
`builder.py`.

## StitchNode fields

| Field | Meaning |
|---|---|
| `stitch_id` | Stable ID, e.g. `body-r04-s018` (component-round-position). |
| `component_kind`, `round_number`, `position_in_round` | Structural location. |
| `sequence_index` | 0-indexed global worked order — the only field the construction-animation timeline uses. |
| `stitch_type`, `stitch_height_category` | From `StitchFamily`; height category is a coarse `short`/`medium` bucket (see caveat below). |
| `loop_placement` | Reused directly from the IR's `LoopPlacement` enum. |
| `parent_stitch_ids`, `into_ring` | Insertion target(s); `into_ring=True` only for round-1 magic-ring stitches, which have no parent. |
| `is_increase`/`increase_group_id`, `is_decrease`/`decrease_group_id` | Group ID ties every child of one increase, or every consumed parent of one decrease, together. |
| `repeat_group_id` | Which `RepeatOp` iteration produced this stitch, if any. |
| `source_reference` | Human-readable provenance, e.g. `"crown round 2 operation 1 (repeat 4/8)"`. |
| `target_rule` | Always `"deterministic_left_to_right"` today — see above. |

**Known simplification**: `stitch_height_category` only distinguishes `sc`
(short) from `hdc` (medium) — a lookup table, not a dimension model. The
geometry layer does not yet use it to vary stitch size (see
`geometry-transfer-spec.md`); this is explicitly deferred to the
"stitch-specific geometry strategies" slice, not silently pretended to be
stitch-accurate today.

## Edges (first slice)

`yarn_sequence` (chains every stitch in worked order), `insertion` (child →
parent), `horizontal_neighbor` (adjacent stitches within a round, including
wraparound — every round is geometrically a closed loop regardless of
continuous-vs-joined construction), `round_closure` (only emitted when
`Round.closure == SLIP_STITCH_JOIN`; the current engine never produces this,
so it exists in the model but is untested against a real fixture — the
schema is ready for joined rounds before the engine is).

Not yet implemented: `join`, `seam`, `assembly`, `colour_transition` — no
current pattern has more than one colour or component that needs joining.

## Yarn segments (first-slice simplification)

One `connector` segment per consecutive pair of stitches in worked order —
a straight line, not the richer entry/lower-loop/post/upper-loop/exit
semantic segmentation described in the product spec. The `YarnSegment`
model is intentionally narrow; extending it to richer segments is a
geometry/rendering-layer change, not a graph-layer one.

## Invariants checked (`validation.py`)

Unique stitch IDs; contiguous 0..N-1 sequence indices; every insertion
target exists and is not in the same round as its child; round totals match
`Round.stated_total`; `position_in_round` values are contiguous per round.
Most of these are also checked *during* construction in `builder.py`
(raising `GraphBuildError` immediately) — `validation.py` re-checks them
independently over a finished graph object (including one loaded from a
serialized fixture, not just a freshly built one), the same "trust but
verify" posture `validation/validator.py` takes toward the compiler.

## Fingerprint

Identical recipe to `Pattern.fingerprint`: canonical (key-sorted,
whitespace-minimal) JSON over the graph (minus the fingerprint field
itself), SHA-256 hex digest. Implemented standalone in
`graph/fingerprint.py` rather than imported from `engine.compiler`, so the
`graph` package has zero dependency on `engine`.
