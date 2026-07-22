# Physical validation protocol (Phase 1.5)

## Purpose

Phase 1 proved the deterministic engine is *internally* consistent: its own
tests pass, its arithmetic is self-checked, its fingerprints are
reproducible. None of that proves a generated pattern produces a physically
usable, correctly sized beanie when an actual person crochets it. Phase 1.5
exists to test that, honestly — including the possibility that it fails.

**No software test in this repository, however thorough, is evidence of
crochet validity.** Only a real person crocheting a real generated pattern
and reporting what actually happened is evidence of crochet validity.

## What must not happen

- No physical result may be fabricated, estimated, or "reasonably assumed."
  If a measurement is missing, it is reported as missing
  (`failed-trials.md`), not filled in.
- No engine formula, supported range, tolerance, or crown/body/brim
  calculation changes as a side effect of this phase. See
  `docs/decision-gates.md` for how evidence eventually leads to a change —
  always via explicit human decision, never automatically.
- No single "accuracy" number is reported in place of the four separate
  acceptance categories (`docs/expert-evaluation-rubric.md`).

## The trial matrix

Ten trials (`BV-001`-`BV-010`), defined in
`src/crochet_reconstruction/physical_validation/trial_matrix.py`, are
deliberately weighted toward the **boundaries** of the currently-declared
supported ranges (head circumference 42-64cm, stitch gauge 10-24 st/10cm,
round gauge 7-20 rounds/10cm, negative ease 0-12%) rather than comfortable
mid-range values. Mid-range behaviour is already covered by Phase 1's
property-based tests over the whole valid range; what those tests *cannot*
tell us is whether a range boundary that is mathematically valid is also
*physically* wearable. That is the specific question this matrix is
designed to answer.

This is a hand-constructed, pairwise-*inspired* selection — every level of
every variable (both stitches, both brim types, both range extremes on
every numeric variable) appears at least twice — not a certified orthogonal
covering array. With only 10 trials against 4+ multi-level variables, full
formal pairwise coverage was not attempted; the selection prioritises
covering real boundary interactions (e.g. "hdc at the gauge ceiling," "sc
at the smallest supported head with maximum ease") over combinatorial
completeness.

### Minimum trial set

If only 4 physical beanies can be made: `BV-001, BV-002, BV-004, BV-006`.
This subset alone covers both stitches, both brim states, and both ease
extremes at least once each.

If 6 can be made, add `BV-003, BV-005`.

## Workflow

```
1. Generate the expert-review pack (this repo, deterministic)
       ↓
2. Distribute to physical testers (outside this repo)
       ↓
3. Testers crochet, measure, and fill in review-form.md (outside this repo)
       ↓
4. Convert completed review forms into PhysicalTrialResult JSON files
   (currently a manual step — see result_schema.py for the exact shape)
       ↓
5. Ingest + evaluate (this repo, deterministic given the submitted files)
       ↓
6. A human reviews build/physical_evaluation/ against docs/decision-gates.md
       ↓
7. Human decision: continue / narrow / redesign — recorded outside this repo
```

Steps 1 and 5 are the only steps this codebase automates. Steps 2-4 and 6-7
are inherently human and are not, and should not be, automated.

### Step 1: generate the pack

```bash
python -m crochet_reconstruction.cli expert-review-pack --output build/expert_review/
```

Produces `index.md`, `trial-matrix.csv`/`.json`, and a `patterns/<TRIAL-ID>/`
directory per trial containing `input.json`, `pattern.json`,
`validation.json`, `pattern.txt`, and a blank `review-form.md`. See
`docs/pattern-format.md` for what `pattern.json` contains.

Give testers `crocheter-instructions.md`, `measurement-guide.md`, and
`evaluation-rubric.md` from inside the generated pack (copied automatically
from the canonical `docs/` versions at generation time).

### Step 4 (manual): completed review form -> result JSON

There is currently no form-scanning or transcription tool — a coordinator
manually transcribes each completed `review-form.md` (plus its answers)
into a `PhysicalTrialResult` JSON file
(`src/crochet_reconstruction/physical_validation/result_schema.py`) and
places it in a results directory. This is intentionally manual for Phase
1.5: building an automated transcription pipeline before knowing whether
the underlying patterns are even physically valid would be solving the
wrong problem first.

### Step 5: ingest and evaluate

```bash
python -m crochet_reconstruction.cli evaluate \
  --trials build/expert_review/ \
  --results physical-results/ \
  --output build/physical_evaluation/
```

Every result is checked against the trial matrix: an unknown `trial_id` or
a `pattern_fingerprint` that doesn't match what the engine currently
produces for that trial is rejected and listed in `failed-trials.md`, not
silently accepted. Produces `summary.md` (observations only),
`metrics.json`, `trial-results.csv`, `failed-trials.md`,
`assumption-review.md`, and `recommended-decisions.md` (recommendations for
human review, never automated action).

## How evidence changes the engine

It doesn't, automatically. `recommended-decisions.md` and
`assumption-review.md` are inputs to a human decision, made against
`docs/decision-gates.md`. If a decision is made to narrow scope (e.g. drop
`hdc`, drop the BLO brim, tighten the supported gauge range), that is a
deliberate, reviewed code change to `templates/top_down_beanie.py` and
associated tests — the same review discipline Phase 1 itself was built
under, not a script reacting to a report.
