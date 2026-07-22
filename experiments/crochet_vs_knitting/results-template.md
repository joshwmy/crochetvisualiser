# Results template

Copy this structure when reporting any baseline run of the crochet-vs-
knitting classifier. **A single accuracy number is never an acceptable
report** — the source decision package's own audit of this exact task
(§7, Experiment 7) requires per-class precision/recall, a reject/uncertain
option, and calibration, precisely because a high overall accuracy can
hide a classifier that is dangerously confident on machine-made lookalikes.

## 1. Run metadata

- Model/method name and version:
- Dataset version (commit hash or dataset release ID):
- Split policy version (link to split-policy.md revision used):
- Number of objects / images per split:
- Date run:

## 2. Baseline comparisons

Report the candidate method alongside, at minimum:

- **Random baseline** (predicts uniformly at random among the 5 classes).
- **Majority-class baseline** (always predicts the most common class in
  training data).

A candidate that doesn't clearly beat majority-class on the rarer classes
(`machine_made_crochet_like`, `uncertain`) is not yet useful, even if its
overall number looks fine.

## 3. Per-class metrics (required)

| Class | Precision | Recall | F1 | Support (n images) |
|---|---:|---:|---:|---:|
| crochet | | | | |
| knitting | | | | |
| woven | | | | |
| machine_made_crochet_like | | | | |
| uncertain | | | | |
| **Macro average** | | | | |

Report separately for `view_type: macro` and `view_type: full_object` —
do not pool.

## 4. Confusion matrix (required)

A full 5x5 confusion matrix (predicted vs. actual), not just a summary.
Pay particular attention to:

- **Crochet predicted as `machine_made_crochet_like` or vice versa** — the
  specific failure mode this class exists to catch.
- **Anything predicted as `uncertain` that a human found easy** — suggests
  the model is under-confident, wasting the reject option's value.
- **Anything confidently predicted as a definite class that was actually
  `uncertain` per human annotators** — suggests the model is
  over-confident on genuinely ambiguous cases, the more dangerous
  direction of error.

## 5. Calibration

Report:

- **Expected Calibration Error (ECE)** or an equivalent reliability-diagram
  summary — does the model's stated confidence match its actual accuracy
  at that confidence level?
- **Coverage-at-precision curve**: for a range of confidence thresholds,
  what fraction of images can the model confidently classify (coverage)
  while maintaining at least, e.g., 90%/95%/99% precision on the classified
  subset? This is the practical number for deciding a confidence threshold
  below which the pipeline should route to `uncertain` / manual review
  instead of trusting the model.

## 6. Performance by capture condition

Break down the primary metrics (at minimum, macro-F1 and the confusion
matrix's off-diagonal mass) by:

- `lighting_condition`
- `focus_quality`
- `yarn_colour_category`
- `distance_category` (if populated)

A model that performs well only on `daylight` + `sharp` + `light_solid`
images is not evidence the model works in general intake conditions.

## 7. Human-review workflow for low-confidence or disputed predictions

Describe (even before any model exists, as a design placeholder):

1. **Threshold**: which confidence-at-precision operating point (from
   §5) routes an image to human review instead of an automatic label.
2. **Reviewer**: who reviews (a designated annotator, not the original
   photographer/user).
3. **Outcome recording**: how the human's final label is fed back —
   labelled explicitly as human-adjudicated, not silently merged with
   model predictions, so future retraining can distinguish "the model got
   this right" from "a human had to fix this."
4. **Escalation**: what happens when even a human reviewer would label the
   image `uncertain` — per the source decision package's AI-boundary
   table, this should route to the same manual craft-selection fallback
   the deterministic pattern engine already assumes exists (see
   `docs/product-boundary.md` in the repository root), not to a forced
   guess.

## What this template does not include

Latency/cost benchmarking and deployment-readiness criteria are out of
scope for a baseline experiment report — add them only once a candidate
method has cleared the accuracy/calibration bar above and a decision is
being made about production integration (which is explicitly out of scope
for the current phase of this project).
