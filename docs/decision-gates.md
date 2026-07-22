# Decision gates

**These are proposed experimental thresholds awaiting crochet-expert
approval — not proven crochet laws, and not automated triggers.** Nothing
in this codebase reads this file and changes engine behaviour. A human
reviews physical evidence (`build/physical_evaluation/`) against these
gates and decides.

Where a gate requires a specific numeric tolerance (e.g. "within X cm"),
this document deliberately leaves it as **TBD — requires expert approval**
rather than inventing a number. Inventing a plausible-looking centimetre
tolerance without a crochet expert's sign-off would be worse than leaving
it blank: it would look authoritative while being unfounded.

## Continue

The engine may proceed toward MVP integration when **all** of the
following hold:

- No fatal arithmetic or repeat errors occur in physical trials (i.e.
  `overall_arithmetic_failure_rate == 0` in `metrics.json`).
- At least 80% of the minimum trial set
  (`physical_validation.trial_matrix.MINIMUM_TRIAL_SET`) are rated
  "acceptable without correction" or "acceptable with minor correction" —
  i.e. `acceptable_no_correction + acceptable_minor_correction >= 0.80`.
- Median absolute circumference error is within an **expert-approved
  tolerance — TBD.** (`metrics.json`'s
  `overall_median_absolute_circumference_error_cm` reports the observed
  value; there is no engine-level pass/fail line drawn on it yet.)
- Median absolute height error is within an **expert-approved tolerance —
  TBD.** (Same caveat as above, via
  `overall_median_absolute_height_error_cm`.)
- No supported stitch family (`sc` or `hdc`) consistently produces severe
  rippling or cupping — i.e. `failure_mode_counts["crown_rippled"]` and
  `failure_mode_counts["crown_cupped_early"]` are not concentrated in one
  stitch family's trials (compare `by_stitch_family` group summaries).
- Expert reviewers consider the instructions understandable and
  reproducible (`instructions_understandable` / `abbreviations_clear`
  mostly `true` across submitted results).

## Narrow

Narrow the engine's supported scope when evidence points at **one specific
feature**, not the whole approach:

- One stitch family performs consistently worse than the other (compare
  `by_stitch_family` group recommendations in `recommended-decisions.md`).
- BLO brim behaviour is unreliable (`blo_brim_behaved_as_expected` mostly
  `false`, or the `by_brim_type` group for `blo_in_round` recommends
  `narrow`).
- One end of the supported measurement or gauge range fails (check
  `by_gauge_range` / `by_size_range` groups — recall the trial matrix was
  deliberately weighted toward range boundaries, see
  `docs/physical-validation-protocol.md`).
- The constant crown-increase schedule (`m in {6, 8}`,
  `docs/mathematical-assumptions.md` §5-6) works only within a narrower
  sub-range than currently declared.
- A formula works only after systematic correction in a specific group
  (i.e. that group's `arithmetic_failure_rate` is elevated relative to
  others).

**Examples of narrowing**, to be decided by a crochet expert reviewing the
evidence, not automatically: supporting `hdc` only; removing the BLO brim;
reducing the supported gauge range; reducing the supported size range;
supporting only one crown increase schedule (`m=6` or `m=8`, not both).

## Stop or redesign

Stop progression toward image-integration phases when:

- Patterns regularly require mathematical correction across most/all
  groups (`overall_arithmetic_failure_rate` is high and not concentrated in
  one narrow-able feature).
- Identical input and gauge do not yield reasonably reproducible
  dimensions across testers (compare multiple testers' results for the same
  `trial_id` — large, unexplained spread suggests the model itself, not
  tester error, is the problem).
- Crown geometry cannot be stabilised within the current small template
  family (rippling/cupping present across most stitch families and gauge
  ranges, not isolated to one).
- Expert reviewers consider the instructions unsafe or unusable at scale
  (`unusable` proportion is high and not concentrated in one narrow-able
  group).
- Physical performance depends mainly on undocumented crocheter intuition
  rather than what the written instructions actually say (testers report
  needing to "just know" conventions the pattern didn't state).

## Reporting buckets used by `evaluation_report.py`

`gauge_bucket()` and `size_bucket()` split results into low/medium/high and
small/medium/large groups purely **for readable reporting** — these
boundaries are not template-supported-range boundaries (those are in
`docs/mathematical-assumptions.md` §9) and are not gates themselves:

| Gauge bucket | Range |
|---|---|
| low | <= 13 st/10cm |
| medium | 14-19 st/10cm |
| high | >= 20 st/10cm |

| Size bucket | Range |
|---|---|
| small | <= 46 cm |
| medium | 47-58 cm |
| large | >= 59 cm |

## Who approves what

A crochet technical editor or equivalent domain expert must sign off before
any of the following become real (non-TBD) numbers used to interpret
results: circumference error tolerance, height error tolerance, and the
minimum acceptable proportion in each acceptance category beyond the 80%
figure given directly in the Phase 1.5 brief above.
