# Diagram topology inference

Circular/radial topology inference: centre detection, round clustering,
stitch ordering, parent attachment, and increase/decrease grouping. See
`src/crochet_reconstruction/diagram/topology.py` for the authoritative
implementation — this document explains the algorithm and the reasoning
behind it, checked against `tests/diagram/test_topology.py` and
`tests/diagram/test_fixtures.py`'s worked examples.

```text
Diagram symbols
→ round clustering
→ sequence ordering
→ parent inference
→ existing StitchGraph
```

## Scope: circular/radial only, this slice

`DiagramConstruction.mode` supports only `"circular"`. `"row"` is reserved
in the schema (the same forward-compatible-without-a-breaking-change
pattern `domain.enums.Construction.JOINED` already uses) but selecting or
detecting it produces an explicit `UNSUPPORTED_CHART_CONSTRUCTION`
diagnostic — never a silent best-effort circular interpretation of a chart
that isn't actually circular.

## Centre detection

Priority order (`_detect_centre`):

1. **Explicit correction** (`ConstructionOverrides.centre`) — always wins
   if a user has set one.
2. **Explicit foundation-ring symbol** — exactly one `magic_ring`/`chain`
   symbol found → its position is the centre, `centre_method: explicit_symbol`.
3. Multiple foundation-ring symbols found → the first (by document order)
   is used, with an `AMBIGUOUS_CENTRE` warning — a chart with two
   apparent foundation rings likely has two unrelated motifs (see
   `docs/known-limitations.md`'s "single connected component" scope
   boundary) rather than being genuinely ambiguous about which is "the"
   centre.
4. **Geometric estimate** — the centroid of all classified worked-stitch
   symbol positions, `centre_method: geometric_estimate`, when no
   foundation-ring symbol exists at all.
5. **Fail**: zero worked stitches and no foundation ring → `MISSING_CENTRE`
   (error, blocking), with an actionable suggestion (mark the centre
   explicitly).

## Round clustering (`_cluster_rounds`)

Only worked-stitch symbols are clustered into numbered rounds — the
foundation ring is conceptually round 0 (referenced directly by symbol id
via a `centre_attachment` relationship) and must never consume a round
number, or every real round would be off by one.

1. Symbols with explicit `data-round` metadata (or a correction setting
   `round_index`) are placed directly — **explicit metadata always
   overrides geometric clustering**, per the brief.
2. Remaining symbols are sorted by radial distance from the centre and
   split into clusters wherever the gap to the next symbol exceeds a
   tolerance.
3. **Tolerance**: `max(gap_based_estimate, noise_floor, 1e-6)`, where
   `gap_based_estimate` is 1.5x the mean gap between consecutive sorted
   radii, and `noise_floor` is 1% of the largest radius in the chart.
   - The gap-based estimate alone is fragile when most symbols in a round
     are placed at *exactly* the same radius (real gap = 0) and only one
     round-transition gap carries any signal — the mean-gap estimate can
     end up tighter than ordinary floating-point or hand-authored-
     coordinate noise, splitting a single intended round into two. The 1%
     noise floor exists specifically to absorb that — see
     `tests/diagram/test_topology.py::test_round_clustering_tolerance_absorbs_minor_coordinate_noise`,
     a regression test for exactly this failure mode.
   - `DiagramConstruction.round_tolerance` (settable via correction)
     overrides both estimates entirely when set.
4. A cluster of size 1 (among otherwise larger clusters) still becomes its
   own round — never silently merged into a neighbour — but produces a
   `ROUND_CLUSTERING_AMBIGUITY` warning asking the user to confirm it's
   intentional. This is the brief's "do not allow one outlier to create a
   false round without warning," applied as "warn, don't guess either
   direction."

## Stitch ordering within a round (`_order_round`)

- Polar angle around the centre (`atan2`), ascending for `clockwise`,
  descending for `counterclockwise`. Direction defaults to `clockwise`
  when nothing else specifies it — an arbitrary-but-deterministic default,
  reversible via the "reverse round direction" correction.
- **Deterministic tie-breaking**: symbols at the exact same angle (a real
  possibility with machine-generated coordinates) sort by `symbol_id` as
  the tiebreaker, so re-analysing identical input always produces an
  identical order.
- An explicit start marker (`round_start` on a symbol, or
  `ConstructionOverrides.start_symbol_id` for round 1 specifically)
  rotates the already-angle-sorted list so that symbol is first — it does
  not change the angular order itself, only where the sequence begins.

## Parent attachment (`_distribute`, `_resolve_connectors`)

Priority order:

1. **Explicit connector edges** — a `<line>`/`<path>` tagged as a
   connector, resolved to its nearest symbol endpoints within
   `CONNECTOR_MATCH_TOLERANCE` (6 normalised units). The endpoint in the
   earlier round is the parent. Confidence `1.0`. An endpoint that lands
   on no known symbol within tolerance produces `INVALID_CONNECTOR`
   (warning) and the connector is ignored for that edge.
2. **Explicit `data-parent` style metadata** — round 1's foundation
   attachment is `explicit_metadata` when the foundation symbol was itself
   explicit; see the confidence table below.
3. **Manual correction** — applied after this base inference (see
   `docs/diagram-corrections.md`); a `SET_PARENT`/`ADD_PARENT`/
   `REMOVE_PARENT` override always wins over whatever this section
   computed.
4. **Radial/proportional projection** (the default, `radial_projection`,
   confidence `0.5`) — when round *r* has `child_count` symbols and round
   *r-1* has `parent_count`, every child index is mapped to a parent index
   (or contiguous block of parent indices) by simple proportional
   distribution:
   - `child_count == parent_count`: 1:1 mapping, no increase/decrease.
   - `child_count > parent_count` (growing): each parent index is
     responsible for a contiguous block of child indices — a parent
     responsible for >1 child is an **increase**, with a shared
     `increase_group_id`.
   - `child_count < parent_count` (shrinking): each child index is
     responsible for a contiguous block of parent indices — a child
     consuming >1 parent is a **decrease**. The block is **contiguous by
     construction** (angularly adjacent in the previous round), so
     `NON_ADJACENT_DECREASE_PARENTS` can only fire when an explicit
     connector or manual correction overrides this default with
     non-adjacent parents — checked defensively in `compiler.py`
     (`_is_circularly_contiguous`).

   This is the same "evenly distribute N over M" idea
   `graph/builder.py`'s left-to-right written-pattern consumption uses,
   driven by this round's actual angular order instead of a written
   pattern's aggregate operation counts.
5. **Fail**: no resolvable parent at all (e.g. an empty previous round) →
   `MISSING_PARENT` (error, blocking).

## Increase/decrease: never invented from round-count alone

The brief: "Do not invent decreases merely because round counts contract."
This is honoured structurally — decreases are only ever produced when the
proportional-distribution mapping (or an explicit connector/correction)
actually assigns multiple parents to one child; a round that happens to
have fewer stitches than the previous one for some *other* reason (e.g. a
correction reassigning parents oddly) does not retroactively become a
"decrease round" by inspection of the totals — the per-stitch parent
count is always the source of truth.

## Round closure

A round gets a `round_closure` relationship (translated to the existing
`round_closure` edge type + `ClosureKind.SLIP_STITCH_JOIN`) only when an
explicit `slip_stitch`/`join` symbol marked `round_closure=True` is
present in it. No implicit default closure is applied — matching the
existing engine's own default of continuous/spiral rounds with no
per-round closure unless explicitly modelled.

## Safety limits during inference

`SafetyLimits.max_inferred_stitches` and `.max_inferred_edges` are checked
after round assignment and after relationship construction respectively —
bounding the *interpretation* cost of a chart independently from the raw
SVG element-count limit (a single small SVG could in principle describe an
enormous number of implied stitches via `<use>` repetition; this is the
second layer of defence against that).
