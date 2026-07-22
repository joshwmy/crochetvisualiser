# Experiment: crochet vs. knitting classification

**Status: scaffolding only. No dataset has been downloaded, no model has
been trained, and no production vision service exists.** This directory
defines the experiment design so that data collection, annotation, and
baseline evaluation can proceed in a controlled way once someone is ready
to run it — it does not run anything itself.

This is Experiment 7 in the source decision package's experiment
programme, listed as useful-but-not-core: a manual "what craft is this"
first question is a perfectly adequate fallback, so this classifier is an
optional automation of routing, not a dependency of anything in Phase 1 or
Phase 1.5.

## Why this experiment, and why now (as scaffolding)

The decision package's central architecture rule is that probabilistic
image interpretation, user-confirmed design state, and deterministic
compilation must stay in three separate layers, and only deterministic
compilation may produce the source-of-truth pattern (see
`docs/product-boundary.md` and `docs/pattern-format.md` in the repository
root). Before any image-analysis code is written, the *evaluation
methodology* for that code needs to exist — otherwise there is no way to
know whether a future classifier is trustworthy enough to sit even in the
"untrusted candidate suggestion" role the architecture allows.

## What this classifier would do (once built)

Given a photograph, assign one of:

1. **Crochet**
2. **Knitting**
3. **Woven fabric**
4. **Machine-made crochet-like textile**
5. **Unsupported or uncertain craft**

Class 5 exists so the classifier can honestly decline to guess rather than
force a confident-looking wrong answer on ambiguous images (dark, fuzzy,
distant, or genuinely ambiguous handmade-vs-machine-made cases).

## Files in this directory

- [`dataset-schema.json`](dataset-schema.json) — JSON Schema for one
  labelled image record, including the required capture metadata.
- [`annotation-guide.md`](annotation-guide.md) — how a human annotator
  assigns one of the five classes, including edge cases and how to use the
  uncertain class honestly.
- [`split-policy.md`](split-policy.md) — how train/validation/test splits
  are constructed at the *project* (physical object) level, and why
  image-level splitting would leak information.
- [`results-template.md`](results-template.md) — the metrics a baseline run
  must report (never a single accuracy number), including confusion
  matrices, calibration, and the human-review workflow for low-confidence
  predictions.

## Explicit non-goals for this experiment

- No PyTorch, no model training, no dataset download in this repository
  until this scaffolding has been reviewed and a decision made to proceed.
- No claim that this classifier, once built, may author stitch counts,
  operations, or any part of a structured pattern — see the AI-boundary
  table in the source decision package (§11) and `docs/product-boundary.md`.
- No commercial dataset assumption — see the source decision package's
  licensing audit (§2-3) regarding CrochetBench (CC BY-NC 4.0, research/
  personal use only) and the Roboflow crochet-stitch dataset (small, likely
  leaky). Any real data collection for this experiment needs its own
  consent and licensing review before it starts, independent of this
  scaffolding.
