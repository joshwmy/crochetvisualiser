# Product boundary

This document states what this software does and does not do, and is
authoritative if any other documentation or code comment implies otherwise.

## This is not a pattern-recovery tool

This application **does not recover an original designer's exact pattern**
from a photograph, a description, or any other input. Given measurements,
gauge, and a small set of construction choices, it deterministically
**generates an original pattern** within a supported construction family
that is intended to produce a similar-shaped result. It makes no claim to
reproduce anyone's specific stitch-by-stitch construction, design choices,
or intellectual property.

## Phase 1 contains no image-to-pattern AI

The current phase of this project (the deterministic pattern foundation)
contains:

- **No image upload or image analysis.**
- **No computer vision, no stitch recognition, no crochet-vs-knitting
  classification.**
- **No large language model or other AI component anywhere in the
  measurement-to-instructions pipeline.** Every number in a generated
  pattern is produced by explicit, reviewable arithmetic in
  `engine/` and checked by explicit rules in `validation/` — never by a
  model.
- **No automatic gauge or hook-size inference.** Gauge must be measured by
  the user from a physical swatch; hook size, if provided, is user-entered
  metadata only, never a system recommendation.

The source decision package this project is based on describes a much
larger, later product that *would* incorporate guided photo capture and
AI-assisted candidate ranking — always behind a strict boundary where AI
may only suggest untrusted candidates, never author stitch totals,
operations, or validated output. **None of that later phase exists yet.**
This document exists precisely so that boundary is not blurred by omission
as more phases are added.

## What Phase 1 supports

- One project category: **adult top-down beanies, worked in continuous
  (spiral) rounds.**
- Two body stitches: single crochet (`sc`) and half-double crochet (`hdc`).
- One optional brim treatment: a simple, unshaped, back-loop-only in-round
  brim.
- Solid-colour yarn only (no colour-stripe planning).
- US crochet terminology only.

## What Phase 1 explicitly does not support

- Double crochet or any other stitch family.
- Joined (non-spiral) rounds.
- Folded brims, vertical ribbed brims, or any other brim shaping.
- Garments, bags, blankets, amigurumi, bucket hats, or scarves.
- Colour-stripe sequences.
- Yarn yardage/weight estimation.
- A frontend, mobile app, user accounts, payments, or any social/marketplace
  feature.
- A database or cloud storage of any kind — the engine is a pure Python
  library plus a CLI.

## Disclaimer shown with every generated pattern

Every rendered pattern (`rendering/text_renderer.render_text`) begins with:

> This is an original, deterministically generated reconstruction. It is
> not a recovered designer pattern. Make and measure a gauge swatch before
> beginning.

## Review status

Every formula in this engine is documented in
[`mathematical-assumptions.md`](mathematical-assumptions.md) with its
source, assumptions, and limitations. Several load-bearing numeric choices
(supported ranges, dimensional tolerance thresholds, the allowed crown
increase schedule set `{6, 8}`) are **engineering starting points pending
physical crochet trials and expert review** — they are not yet validated
against real, hand-made objects. This is called out explicitly rather than
presented as settled.
