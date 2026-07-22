# Split policy

## The grouping key is `object_id`, never `record_id`

Every train/validation/test split must be constructed by first grouping
all image records by `object_id` (the physical object photographed), then
assigning **entire groups** to a single split. Never assign individual
`record_id`s to splits independently.

### Why this matters

If two photographs of the same physical beanie end up in different splits
(one in train, one in test), a model can learn to recognise *that specific
object's* yarn colour, lighting quirks, or background — and appear to
generalise well on the test image simply because it has effectively seen
the same object during training. This is the exact leakage risk the source
decision package flags explicitly (§2, "How will train/test leakage be
prevented when multiple images show the same object?") and it is
well-documented in adjacent computer-vision literature (e.g. per-subject
leakage in medical imaging). A classifier evaluated this way will report
inflated accuracy that will not hold up on genuinely new objects.

## Split ratios (proposed default)

70% train / 15% validation / 15% test, by **object count**, not image
count (an object with 6 photos and an object with 2 photos each count as
one unit for the purpose of the ratio, even though they contribute
different numbers of images).

This ratio is a reasonable starting default for a small experimental
dataset, not a validated optimum — revisit once the actual collected
dataset size is known.

## Stratification

Within the object-level grouping constraint, splits should be stratified
by:

1. **`class_label`** (so no split is missing or nearly-missing a class,
   especially `uncertain` and `machine_made_crochet_like`, which are likely
   to be rarer than `crochet`/`knitting`).
2. **Capture-condition coverage** (`lighting_condition`, `focus_quality`,
   `yarn_colour_category`) — the test set must include its fair share of
   dark/fuzzy/low-resolution examples, not just the easy, clean images. A
   test set skewed toward easy examples will systematically overstate
   real-world performance.

If perfect stratification and the object-level grouping constraint
conflict (small dataset, few objects in a rare class), **the object-level
grouping constraint always wins** — accept imperfect stratification rather
than leak objects across splits.

## Process

1. Enumerate all distinct `object_id` values.
2. For each, compute the set of `class_label`s and capture conditions
   present among its images (most objects will have only one class_label,
   but capture conditions can vary across an object's photos).
3. Assign whole objects to train/val/test using a stratified allocation
   that respects the ratios above, prioritising class balance first, then
   capture-condition balance.
4. Verify after assignment: no `object_id` appears in more than one split
   (this should be enforced by construction, but verify it explicitly as a
   final check before any training run).
5. Record the split assignment back into each record's `split` field.

## What this policy does not cover yet

Exact stratified-sampling implementation (e.g. a script) is not part of
this scaffolding — this document defines the *policy* a future
implementation must satisfy. Building that script is reasonable follow-up
work once real data collection begins, not before.
