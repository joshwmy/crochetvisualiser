# Expert evaluation rubric

Anchored 1-5 scales for every rating in `PhysicalTrialResult.ratings`
(`src/crochet_reconstruction/physical_validation/result_schema.py`). Pick
the anchor description closest to your experience; these are guides for
consistency across testers, not a rigid legal definition.

## Mathematical correctness

Did the stated stitch totals match what following the instructions
literally produced?

| Score | Anchor |
|---:|---|
| 5 | Every round's stated total matched exactly, no corrections needed anywhere. |
| 4 | One minor total was off by 1-2 stitches in a single round; trivially fixed. |
| 3 | A few rounds needed correction, but the overall shape/count was recoverable. |
| 2 | Multiple rounds needed correction; totals drifted noticeably by the end. |
| 1 | Totals were unrecoverable without redesigning the round; gave up following as written. |

## Instruction clarity

Independent of whether the math was correct: was the wording easy to
follow?

| Score | Anchor |
|---:|---|
| 5 | Clear on first read, no re-reading needed. |
| 4 | Clear after one re-read of a round or two. |
| 3 | Understandable but required careful attention throughout. |
| 2 | Repeatedly confusing; had to guess intent more than once. |
| 1 | Could not determine what was being asked without outside help. |

## Construction plausibility

Does the construction sequence (crown -> body -> brim, magic ring, spiral
rounds) make sense as a real, buildable crochet object?

| Score | Anchor |
|---:|---|
| 5 | Textbook-normal construction; nothing felt unusual. |
| 4 | Minor oddity (e.g. an unusual increase placement) but clearly workable. |
| 3 | Workable but noticeably different from how you'd normally build this. |
| 2 | Awkward construction that fought against normal technique. |
| 1 | Construction sequence didn't make physical sense; had to invent your own approach. |

## Fit

Compared to the stated target circumference and the wearer it was sized
for (or your own head, if testing generically):

| Score | Anchor |
|---:|---|
| 5 | Fits as intended; comfortable, appropriate ease. |
| 4 | Fits acceptably; slightly loose or snug but wearable. |
| 3 | Noticeably off (loose or tight) but still wearable. |
| 2 | Uncomfortably loose or tight. |
| 1 | Unwearable — too large or too small to serve as a beanie. |

## Shape

Independent of size: is the silhouette a normal beanie shape (smooth
rounded crown, straight or gently tapered body)?

| Score | Anchor |
|---:|---|
| 5 | Smooth, symmetric, no visible ripples or cupping. |
| 4 | Very minor asymmetry or texture, not noticeable at a glance. |
| 3 | Visible but minor rippling/cupping/polygon-cornering. |
| 2 | Noticeable shape distortion that affects how it sits on a head. |
| 1 | Severely distorted; does not read as a beanie shape. |

## Visual quality

Overall finished-object impression, independent of fit/shape/math:

| Score | Anchor |
|---:|---|
| 5 | Looks like a deliberately designed, finished object. |
| 4 | Minor cosmetic issues (visible jog at colour/round start, slightly uneven tension). |
| 3 | Noticeable cosmetic issues but still presentable. |
| 2 | Rough/unfinished appearance. |
| 1 | Would not show this to anyone. |

## Beginner suitability

Would a beginner (per `ExperienceLevel.BEGINNER`) likely succeed with this
pattern as written, with no outside help?

| Score | Anchor |
|---:|---|
| 5 | Yes, with standard beginner crochet knowledge only. |
| 4 | Yes, but might need to look up one technique (e.g. magic ring). |
| 3 | Possible but would likely need outside help at least once. |
| 2 | Would likely fail or need significant help throughout. |
| 1 | Not attemptable by a beginner. |

## Overall usability

Your holistic judgement, considering everything above together — not a
recomputed average.

| Score | Anchor |
|---:|---|
| 5 | Would hand this to someone else to make, as-is. |
| 4 | Would use it myself; minor caveats I'd mention. |
| 3 | Usable with the corrections I made; wouldn't recommend as-is. |
| 2 | Only usable with significant rework. |
| 1 | Not usable. |

## Acceptance status (choose exactly one)

- **Acceptable without correction** — followed exactly as written, produced
  a usable, correctly-sized beanie.
- **Acceptable with minor correction** — needed one or a few small fixes
  (see `docs/measurement-guide.md`, "Reporting a corrected instruction"),
  but the result was usable.
- **Requires major correction** — needed substantial rework to produce a
  usable result.
- **Unusable** — could not produce a usable beanie from this pattern.

These four categories are reported as **separate proportions**, never
averaged into one score (`metrics.acceptance_proportions`). A pattern that
is "acceptable with minor correction" 100% of the time is a materially
different finding from one that is "acceptable without correction" 50% of
the time and "unusable" 50% of the time, even though a naive average might
treat them similarly.
