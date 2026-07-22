"""Phase 1.5: physical validation and expert-evaluation tooling.

This package sits *around* the Phase 1 deterministic engine
(`crochet_reconstruction.domain`, `.engine`, `.validation`, `.rendering`)
without modifying it. Its job is to generate controlled physical trials,
package them for crochet experts, ingest their real-world measurements and
ratings, and report — honestly, without fabrication — whether the
engine's mathematical assumptions survive contact with an actual beanie.

Nothing in this package may alter a crown formula, increase schedule,
supported range, circumference tolerance, or brim/body calculation. Those
live in `crochet_reconstruction.engine` and `crochet_reconstruction.templates`
and change only after physical evidence and expert review — see
docs/decision-gates.md.
"""
