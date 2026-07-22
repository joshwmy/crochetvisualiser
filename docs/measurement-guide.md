# Measurement guide

This defines exactly how to measure everything a Phase 1.5 physical trial
needs. Crochet practice allows more than one valid method for several of
these measurements — where that's true, this guide picks **one convention**
and states it explicitly, so results from different testers are actually
comparable to each other and to the engine's calculated values.

## Gauge: before or after blocking?

**Convention: measure gauge unblocked (as worked off the hook, relaxed but
not stretched), unless the trial explicitly asks for a blocked swatch.**

Rationale: the engine's gauge input (`stitches_per_10cm`, `rounds_per_10cm`)
is a single number with no "blocked" vs. "unblocked" distinction in Phase 1
— see `docs/mathematical-assumptions.md`. Comparing like with like requires
picking one state. Unblocked was chosen because it requires no extra step
before a tester can start crocheting, and because Phase 1's supported yarn
is unspecified/solid-colour with no blocking-sensitive stitch pattern
(cables, lace) that would make blocking materially change gauge.

**If you do block your swatch or finished item, record that explicitly** in
the review form's notes — do not silently report post-blocking numbers as
if they were unblocked.

### How to measure gauge

1. Crochet a swatch of at least 15 cm x 15 cm in the trial's stitch and
   (if given) hook.
2. Lay it flat on a hard surface, unstretched, unblocked. Do not pin it.
3. Using a rigid ruler (not a soft tape, which can distort), measure a
   10 cm span in the middle of the swatch (avoid the first/last 2-3 rows and
   edge stitches, which are less consistent).
4. Count stitches across that 10 cm span, including partial stitches as a
   fraction (e.g. 15.5).
5. Repeat for rounds/rows across a vertical 10 cm span.
6. Record both numbers exactly as measured — do not round to match the
   pattern's requested gauge.

## Relaxed circumference

**Convention: lay the finished piece flat, unstretched, and measure the
opening's circumference by measuring its flat width and doubling it** (a
tape measure wrapped around a slightly stretchy fabric introduces its own
tension, which is why a doubled flat-width measurement is more repeatable).

1. Lay the finished beanie flat on a table, right side up, opening facing
   you, with no stretching or smoothing beyond removing obvious wrinkles.
2. Measure the flat width edge-to-edge across the opening with a rigid
   ruler.
3. Circumference = flat width x 2.

## Stretched circumference

**Convention: stretch the opening around a rigid cylindrical object of
known circumference close to the wearer's head size (e.g. a large bowl, a
head form, or a gallon paint can) and measure how far it stretches before
tension becomes uncomfortable to maintain by hand** — not "as far as it can
possibly stretch," which varies too much by tester grip strength to be
comparable.

1. Find or improvise a rigid cylinder close to the target head
   circumference.
2. Stretch the opening around it.
3. Measure the cylinder's circumference at that point with a soft tape.
4. Note what you used as the cylinder in the review form.

## Crown diameter

**Convention: measure the crown flat, before it curves into the body**,
i.e. measure across the increase section only, laid flat, corner to corner
through the centre (magic ring point).

Recall the engine's crown diameter is a diagnostic approximation
(`C_t / pi`) assuming a flat disk — your measured value is expected to
differ somewhat from the calculated one; that difference is exactly what
this experiment is measuring (see `docs/mathematical-assumptions.md` §5).

## Total height

Lay the finished piece flat, opening down, crown up. Measure vertically
from the table to the highest point of the crown with a rigid ruler. Do not
stretch vertically.

## Brim height

Same flat, unstretched convention: measure the brim section's height alone
(from the very edge of the opening to where the brim section's stitches end
and the body begins), with a rigid ruler.

## Documenting yarn and hook substitutions

If you used different yarn or a different hook size than the trial's
metadata suggests (or if none was specified and you chose your own), record
in the review form:

- Yarn brand/line, weight category, and fibre content.
- Hook size in mm (not just a letter/number label, which varies by
  manufacturer).
- Whether this was a deliberate substitution to hit gauge, or your default
  choice.

## Photographing the finished result

Take four photos, in consistent lighting (daylight or a single bright
indoor light, not flash):

1. **Front**: laid flat, opening toward camera.
2. **Side**: standing or on a head form if available, profile view.
3. **Top-down**: directly above the crown, showing the increase spiral.
4. **Brim close-up** (if the trial has one): close enough to see individual
   back-loop stitches.

Save as `<trial-id>-<view>.jpg` (e.g. `BV-001-front.jpg`) alongside your
completed review form.

## Reporting a corrected instruction

If you had to deviate from the written instructions to keep the piece
correct (e.g. the stated round total didn't match what was actually on your
hook), record it as a **correction**, not a silent fix:

1. Note the exact round number.
2. Note what the instruction said.
3. Note what you actually did instead, and why.
4. Note the resulting stitch count after your correction.

This is the single most valuable piece of data this experiment collects —
an undocumented silent fix looks identical to a pattern that worked
perfectly, which is exactly the failure mode this protocol exists to avoid.

## How this evidence will be used

See `docs/decision-gates.md` for exactly how measurements and ratings map
to continue/narrow/redesign recommendations, and
`docs/physical-validation-protocol.md` for the overall experimental design.
