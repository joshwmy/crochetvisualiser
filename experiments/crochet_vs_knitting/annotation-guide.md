# Annotation guide

How a human annotator assigns one of the five `class_label` values in
[`dataset-schema.json`](dataset-schema.json) to an image.

## Decision tree

1. **Is the fabric structure visible enough to judge at all?**
   - No (too dark, too distant, too fuzzy a yarn, too blurry) -> `uncertain`.
     Do not guess from context (e.g. "it's on a crochet blog so it's
     probably crochet") — label only from what the image itself shows.
2. **Does it show interlocking knots/loops pulled through other loops
   (crochet's structure), or interlocking columns of knit/purl stitches
   (knitting's structure)?**
   - Crochet structure clearly visible -> `crochet`.
   - Knit/purl column structure clearly visible -> `knitting`.
3. **Is it a woven fabric (perpendicular thread grid, no loop structure at
   all)?** -> `woven`.
4. **Does it look crochet-like but suspiciously uniform (perfectly even
   tension, no visible hand-tension variation, possible manufacturing
   selvage or tag)?** -> `machine_made_crochet_like`. This class exists
   because a naive crochet/knit classifier trained without it will
   misclassify machine-made lookalikes as handmade crochet with high
   confidence — see the source decision package's audit of this exact
   failure mode (§2, "Crochet-versus-knitting classification").
5. **Still not confident after 1-4?** -> `uncertain`. This is not a failure
   state for the annotator — it is the correct label for a genuinely
   ambiguous image, and the whole point of including this class is that
   "confidently wrong" is worse than "honestly unsure."

## Do not guess from surrounding context

Label the image as if it were the only evidence you have — not based on a
caption, file name, source website, or what other images of the same
object show. If two images of the same object are ambiguous individually
but the object_id groups them, that grouping is for split integrity (see
split-policy.md), not a labelling shortcut. Each image gets its own honest
label.

## Handling deliberately hard examples

The dataset must include, not exclude, examples that are hard to label:

- **Dark or low-light images.**
- **Fuzzy/eyelash yarn** where stitch structure is inherently obscured.
- **Variegated/highly patterned yarn** where colour changes can be mistaken
  for structural detail.
- **Low-resolution or heavily compressed images.**
- **Distant, full-scene photos** with the object as a small part of frame.

These are not noise to be filtered out before annotation — they are exactly
the conditions a real intake pipeline will see, and a classifier evaluated
only on clean macro shots would report misleadingly good numbers.

## Macro vs. full-object views

Both `view_type: macro` and `view_type: full_object` should be collected
for the same objects where possible (same `object_id`, different
`record_id`). Macro views test structural discrimination; full-object views
test whether silhouette/context alone gives useful signal when structure
isn't resolvable. Report metrics separately per `view_type`
(see results-template.md) — do not pool them into one number, since a
classifier can perform very differently on each.

## Inter-annotator agreement

A fixed random sample (recommended: at least 10% of the dataset, stratified
by class) should be labelled independently by two annotators before being
adjudicated by a third. Record both annotators' labels and confidences in
`annotation.second_annotator_id` / `annotation.second_annotator_label`; if
they disagree, record who adjudicated in `disagreement_resolved_by`. Report
inter-annotator agreement (e.g. Cohen's kappa) per class in the experiment
write-up — low agreement on a class is itself a finding (it likely means
the class boundary needs a clearer definition, not that annotators need
retraining).

## What annotators must never do

- Never infer craft type from anything other than the image itself.
- Never leave a genuinely ambiguous image unlabelled — use `uncertain`
  explicitly.
- Never assign a `split` value — that is set later, at the dataset level,
  not per-image (see split-policy.md).
