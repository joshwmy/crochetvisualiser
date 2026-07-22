# Mathematical assumptions

This document is the single source of truth for every formula, rounding
policy, and numeric constant the Phase 1 engine uses. Every formula here is
implemented in exactly one place in the codebase (no duplicated arithmetic
between `engine/`, `validation/`, and `rendering/`) — see the file reference
under each section.

All formulas operate on `decimal.Decimal`. Gauge is always converted from
"per 10 cm" (the user-facing unit) to "per cm" internally by dividing by 10.

## Rounding policy

**Every** rounding-to-integer operation in the engine uses round-half-up
(ties away from zero), implemented once in
`engine/sizing.round_half_up`. This is a deliberate, explicit choice — the
decision package does not mandate a specific tie-breaking rule, and
round-half-up is the convention most crocheters would expect when told "a
round adds 20.5 stitches, round to 21." Python's `Decimal` module default
(`ROUND_HALF_EVEN`, banker's rounding) is intentionally not used, because it
would silently round 20.5 down to 20 in half of all cases, which is
surprising for this domain and not something a rendered pattern could
explain to a reader.

## 1. Target circumference and negative ease

```
C_t = H * (1 - e)
```

- `H` — head circumference (cm), required user input.
- `e` — negative ease as a fraction (user enters a percentage; the engine
  divides by 100).
- `C_t` — target finished body circumference (cm).

**Source:** decision package §14, "Target circumference." A crochet/garment
convention treated as an explicit design assumption, not a physical law.

**Assumption locked for Phase 1:** negative ease is **always required and
user-supplied**, never defaulted. The decision package mentions a possible
"template default ease" (§14, edge cases); Phase 1 does not implement one,
because defaulting a value that materially changes finished dimensions
conflicts with the "do not silently repair obviously invalid values"
requirement, and because there is no physically validated per-template
default yet.

**Supported range:** 0–12% (rule `V-RANGE-001`, fatal outside this range).
This is the exact range given in the decision package's Experiment 1
dataset specification — the only concrete ease range the source document
commits to. It is a starting point for the POC, **not a physically proven
safe range**, and is flagged for crochet-expert review.

**File:** `engine/sizing.target_circumference_cm`.

## 2. Gauge conversion

```
g_s = stitches_per_10cm / 10   (stitches / cm)
g_r = rounds_per_10cm / 10     (rounds / cm)
```

Gauge is user-measured from a physical swatch. Phase 1 has no automatic
gauge inference of any kind. **File:** `domain/gauge.Gauge` properties.

**Supported range:** stitch gauge 10–24 st/10cm, round gauge 7–20
rounds/10cm (rule `V-RANGE-001`). Source: decision package Experiment 1
dataset specification, same caveat as above.

## 3. Body stitch count and repeat-compatible rounding

```
N_raw = C_t * g_s
```

`N_raw` is rounded to the nearest multiple of the crown's
increases-per-round `m` (see §5) by comparing the two neighbouring
candidates' resulting circumference against `C_t` and choosing whichever is
closer:

```
N_down = floor(N_raw / m) * m
N_up   = N_down + m
choose whichever of {N_down, N_up} minimizes |n/g_s - C_t|
```

**Tie-break rule (locked assumption):** when both candidates are equally
close, the engine prefers the **larger** candidate. Rationale: a larger
stitch count at fixed gauge produces a larger finished circumference, i.e.
effectively *less* negative ease — the decision package's own tie-break
guidance (§14) favours "the less restrictive ease." This is an arbitrary
but necessary, explicitly documented choice; the source document does not
mandate a direction.

**Zero-candidate guard:** `N_down` is never allowed to be 0 or negative — a
crown needs at least one repeat's worth of stitches. If the floor candidate
would be ≤ 0, both candidates are shifted up by one multiple.

**Mathematical guarantee (verified by property test):**
```
deviation_cm <= (m / 2) / g_s
```
i.e. the resulting circumference is never farther than half a repeat unit's
worth of centimetres from the target. The raw value, chosen value, and
resulting deviation are all recorded on `CalculatedParameters` for
auditability, per the decision package's explicit requirement.

**Dimensional tolerance (locked assumption, no source in decision
package):** the deviation above is compared against the target
circumference as a percentage:
- **> 3%** → warning (`V-ROUNDING-001`)
- **> 8%** → fatal (`V-DIM-001`)

These two numbers are not derived from any source in the decision package
(which gives physical-testing *success thresholds*, e.g. "median error
≤5%," but no engine-level validation tolerance). They are a conservative
starting point chosen so that Phase 1's supported gauge/circumference
combinations normally stay well under the warning threshold, and are
explicitly flagged for revision once Experiment 1 (physical crochet trials)
produces real data.

**File:** `engine/sizing.repeat_compatible_count`,
`validation/dimensions.check_circumference_deviation`.

## 4. Hat height and round allocation

```
R_h = round(h_t * g_r)               (total rounds for target height)
R_body = R_h - R_crown - R_brim      (straight body rounds)
```

If `R_body < template.min_body_rounds` (1 for `top_down_basic@1.0.0`), the
engine raises `UnsupportedDimensionsError` rather than silently clamping to
zero or a negative count — the requested height is incompatible with the
crown/brim it implies.

**File:** `engine/sizing.rounds_from_height`, `engine/body.body_round_count`.

## 5. Crown diameter and increase rate (diagnostic only)

```
D_c ≈ C_t / π
k   ≈ 2π * g_s / g_r
```

- `D_c` is an approximate flat-disk crown diameter, used only as a
  diagnostic sanity check — **never** as the crown's stopping condition
  (the actual stopping condition is "reached the repeat-compatible stitch
  count `N` exactly," §3/§6). A real fitted crown curves into the head
  before reaching a flat disk's full diameter, so `D_c` systematically
  understates how "open" the crown should feel; this is a documented
  limitation, not a bug.
- `k` estimates how many stitches a flat circle's circumference grows by
  per round, given the measured gauge. It is **snapped to the nearest
  member of the template's expert-approved schedule set**, never used
  directly.

**Locked assumption — allowed increase schedules:** `top_down_basic@1.0.0`
permits only `m ∈ {6, 8}` increases per round. This is a deliberately
narrow starting set (real crochet crowns sometimes use 10 or 12 for taller
stitches or looser gauges) chosen to keep the first vertical slice small;
widening it requires crochet-expert review of the resulting crown
silhouettes, not just a config change.

**Tie-break rule:** ties in "nearest allowed `m`" are broken toward the
*smaller* value, for determinism.

`PI` is a fixed 20-digit Decimal literal (not derived from `math.pi` at
runtime) so the constant is explicit, reviewable, and independent of any
floating-point conversion step.

**File:** `engine/crown.crown_diameter_cm`, `engine/crown.estimate_increases_per_round`.

## 6. Crown increase schedule

**Locked assumption unifying §3 and §5** (the decision package specifies
these as two separate formulas without stating how they interact): the
crown's starting stitch count `s0` equals the increases-per-round `m`
exactly (one stitch produced per magic-ring "increase group"), and the
repeat multiple used for rounding `N` in §3 is always this same `m`. This
guarantees the crown's constant-increase schedule can always reach `N`
exactly:

```
Round 1 total       = s0 = m           (magic ring)
Round r (r >= 2)     total = r * m
```

Each of the `m` repeat groups in round `r >= 2` consumes `r - 1` stitches
from the previous round (`r - 2` plain stitches plus one increase) and
produces `r` stitches. This is the decision package's "simple
constant-increase family" (§14) — a flat, untapered schedule.

**Documented limitation:** real crochet crown patterns often taper the
final increase round(s) to avoid a visibly "waved" edge. Phase 1's schedule
is constant all the way to the target count. This is a known simplification
flagged for crochet-expert review during Experiment 3/4 of the six-week
programme, not a claim that it is the physically optimal schedule.

Position rotation between rounds (a real-world technique to avoid a visible
seam of increase points stacking vertically) is a construction nicety that
does not affect stitch counts and is **not modelled** in the Phase 1 IR —
noted here so it is not mistaken for an oversight.

**File:** `engine/crown.build_crown_rounds`.

## 7. Brim

```
R_brim = round(b_t * g_r)     (in-round, unshaped brim)
```

Only an unshaped, back-loop-only in-round brim is supported (`BrimType.BLO_IN_ROUND`).
Its stitch count always equals the body stitch count `N` — Phase 1 does not
model brim shaping. Folded brims and separately-worked vertical ribbing are
out of scope (decision package §16 lists them as later MVP templates).

**File:** `engine/brim.brim_round_count`, `engine/brim.build_brim_rounds`.

## 8. What is deliberately NOT modelled in Phase 1

- Yarn/yardage estimation (decision package §14 "Yarn estimate" — explicitly
  optional even for the source document's own POC).
- Automatic hook-size recommendation (the decision package's DSL example
  shows a `hook_mm recommendation ... confidence ...` mechanism; Phase 1's
  hook field is purely optional user-entered metadata with no inference).
- Colour-stripe planning.
- Joined-round chain/closure conventions.
- Tapered (non-constant) crown increase schedules.

## 9. Supported range summary (rule `V-RANGE-001`)

| Input | Minimum | Maximum |
|---|---:|---:|
| Head circumference | 42 cm | 64 cm |
| Stitch gauge | 10 st/10cm | 24 st/10cm |
| Round gauge | 7 rounds/10cm | 20 rounds/10cm |
| Negative ease | 0% | 12% |

Source: decision package §7, Experiment 1 dataset specification. **Not yet
physically validated** — see `README.md` "Known limitations."
