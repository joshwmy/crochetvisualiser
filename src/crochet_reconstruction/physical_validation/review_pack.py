"""Generate the expert-review pack: everything a crochet tester/expert needs.

Pattern data (input JSON, structured pattern, validation report, rendered
instructions, calculated values) is always generated fresh from the current
engine — never hand-duplicated. Only the instructional/form text
(review-form template, index framing) is authored prose, since it is
guidance, not pattern data.
"""

from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path

from crochet_reconstruction.domain.pattern import Pattern
from crochet_reconstruction.physical_validation.trial_matrix import (
    MINIMUM_TRIAL_SET,
    RECOMMENDED_EXTENDED_MINIMUM_SET,
    TrialConfig,
    TrialRow,
    build_project_input,
    build_trial_matrix_rows,
)
from crochet_reconstruction.rendering.text_renderer import (
    PatternNotRenderableError,
    render_text,
)

_CSV_FIELDNAMES = [f.name for f in dataclasses.fields(TrialRow)]


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _write_trial_matrix_files(output_dir: Path, rows: list[TrialRow]) -> None:
    _write_json(output_dir / "trial-matrix.json", [dataclasses.asdict(r) for r in rows])

    with (output_dir / "trial-matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(dataclasses.asdict(row))


def _write_trial_files(trial_dir: Path, trial: TrialConfig, pattern: Pattern) -> None:
    trial_dir.mkdir(parents=True, exist_ok=True)

    project_input = build_project_input(trial)
    _write_json(trial_dir / "input.json", project_input.model_dump(mode="json"))
    _write_json(trial_dir / "pattern.json", pattern.model_dump(mode="json"))
    assert pattern.validation is not None
    _write_json(trial_dir / "validation.json", pattern.validation.model_dump(mode="json"))

    try:
        text = render_text(pattern)
    except PatternNotRenderableError as exc:
        text = (
            f"NOT RENDERABLE.\n\n"
            f"This trial's structured pattern has fatal validation results and "
            f"was not rendered to instructions:\n\n{exc}\n\n"
            f"See validation.json in this directory for the full report. This "
            f"trial should not be given to a physical tester until the "
            f"underlying software issue is investigated — a fatal result here "
            f"is itself a finding worth recording, not something to work around."
        )
    (trial_dir / "pattern.txt").write_text(text, encoding="utf-8")

    (trial_dir / "review-form.md").write_text(_review_form_text(trial, pattern), encoding="utf-8")


def _review_form_text(trial: TrialConfig, pattern: Pattern) -> str:
    calculated = pattern.calculated
    assert pattern.validation is not None
    lines: list[str] = []
    lines.append(f"# Physical trial review form — {trial.trial_id}")
    lines.append("")
    lines.append(
        "Fill in every section below while crocheting this pattern. Record what "
        "actually happened — do not adjust your answers to match the expected "
        "values. A trial that fails is useful data; a trial that is quietly "
        "smoothed over is not."
    )
    lines.append("")
    lines.append("## Expected values (engine-calculated — do not edit)")
    lines.append(f"- Pattern fingerprint: `{pattern.fingerprint}`")
    lines.append(f"- Software validation status: `{pattern.validation.status.value}`")
    lines.append(f"- Stitch: {trial.stitch_family.value}")
    lines.append(f"- Target finished circumference: {calculated.target_circumference_cm} cm")
    lines.append(
        f"- Calculated crown diameter (diagnostic only): {calculated.crown_diameter_cm} cm"
    )
    lines.append(f"- Final body stitch count: {calculated.body_stitch_count}")
    lines.append(f"- Crown rounds: {calculated.crown_round_count}")
    lines.append(f"- Body rounds: {calculated.body_round_count}")
    lines.append(f"- Brim rounds: {calculated.brim_round_count}")
    lines.append(f"- Target height: {trial.target_height_cm} cm")
    lines.append(f"- Brim height (if any): {trial.brim_height_cm} cm")
    lines.append(f"- Assumptions this trial tests: {'; '.join(trial.assumptions_tested)}")
    lines.append(f"- Why this trial exists: {trial.reason}")
    lines.append("")

    lines.append("## 1. Tester information")
    lines.append("- Tester ID (a code, not your name): ")
    lines.append(
        "- Crochet experience level (beginner / intermediate / advanced / professional/designer): "
    )
    lines.append(
        f"- Familiarity with {trial.stitch_family.value} specifically "
        f"(new to it / comfortable / very familiar): "
    )
    lines.append("- Right-handed or left-handed: ")
    lines.append("- Yarn substitution made, if any: ")
    lines.append("- Hook substitution made, if any: ")
    lines.append("")

    lines.append("## 2. Pre-crochet information")
    lines.append("- Yarn brand/identifier: ")
    lines.append("- Yarn fibre: ")
    lines.append("- Yarn weight/category: ")
    lines.append("- Hook size used (mm): ")
    lines.append("- Measured stitch gauge (sts per 10 cm, your swatch): ")
    lines.append("- Measured round gauge (rounds per 10 cm, your swatch): ")
    lines.append(
        f"- Did your swatch match the requested gauge ({trial.stitches_per_10cm} "
        f"st/10cm, {trial.rounds_per_10cm} rounds/10cm)? (yes / no / close): "
    )
    lines.append("- Any modifications made before starting: ")
    lines.append("")

    lines.append("## 3. During-crochet evaluation")
    lines.append("- Were the instructions understandable? (yes / mostly / no): ")
    lines.append("- Were abbreviations clear? (yes / mostly / no): ")
    lines.append("- Did round totals match what you actually had on your hook? (yes / no): ")
    lines.append("- Did the work remain flat during crown construction? (yes / no): ")
    lines.append("- Did the crown cup (dome inward) too early? (yes / no): ")
    lines.append("- Did the crown ripple/wave? (yes / no): ")
    lines.append("- Were increases visually well distributed around the crown? (yes / no): ")
    lines.append("- Did the transition from crown to body make sense? (yes / no): ")
    lines.append(
        "- Did the BLO brim behave as expected (if this trial has one)? (yes / no / n/a): "
    )
    lines.append("- Were any instructions manually corrected? (yes / no): ")
    lines.append("  - If yes, which round(s) caused the problem?: ")
    lines.append("  - If yes, what correction did you make?: ")
    lines.append(
        "  - (Repeat the two lines above for each additional round that needed correction.)"
    )
    lines.append("")

    lines.append("## 4. Final measurements")
    lines.append("- Relaxed circumference (cm): ")
    lines.append("- Stretched circumference (cm, per docs/measurement-guide.md method): ")
    lines.append("- Total height (cm): ")
    lines.append("- Crown diameter, measured flat before curvature sets in (cm): ")
    lines.append("- Brim height, if applicable (cm): ")
    lines.append("- Weight of finished item (g), if available: ")
    lines.append("- Amount of yarn used (g or m), if available: ")
    lines.append("")

    lines.append("## 5. Outcome ratings")
    lines.append("Use the anchored 1-5 scales in docs/expert-evaluation-rubric.md for each.")
    lines.append("- Mathematical correctness (1-5): ")
    lines.append("- Instruction clarity (1-5): ")
    lines.append("- Construction plausibility (1-5): ")
    lines.append("- Fit (1-5): ")
    lines.append("- Shape (1-5): ")
    lines.append("- Visual quality (1-5): ")
    lines.append("- Beginner suitability (1-5): ")
    lines.append("- Overall usability (1-5): ")
    lines.append("- Would you use this pattern again? (yes / no): ")
    lines.append("- Would you recommend it to another crocheter? (yes / no): ")
    lines.append("")
    lines.append("## 6. Acceptance status (choose exactly one)")
    lines.append("- [ ] Acceptable without correction")
    lines.append("- [ ] Acceptable with minor correction")
    lines.append("- [ ] Requires major correction")
    lines.append("- [ ] Unusable")
    lines.append("")
    lines.append("## Notes")
    lines.append("(Anything else worth recording — photos, surprises, ambiguities.)")
    lines.append("")

    return "\n".join(lines)


def _index_text(rows: list[TrialRow]) -> str:
    lines: list[str] = []
    lines.append("# Phase 1.5 expert-review pack")
    lines.append("")
    lines.append(
        "This pack contains a controlled set of generated beanie patterns for "
        "physical crochet testing. **No physical result in this pack is "
        "fabricated** — every value under `patterns/*/pattern.json` and "
        "`patterns/*/validation.json` comes directly from the deterministic "
        "engine; everything under `review-form.md` is blank, waiting for a "
        "real tester to fill in."
    )
    lines.append("")
    lines.append(
        "Read `crocheter-instructions.md` first, then `measurement-guide.md` "
        "before measuring anything, then `evaluation-rubric.md` before rating."
    )
    lines.append("")
    lines.append(
        f"**If you can only make 4 beanies**, make: {', '.join(MINIMUM_TRIAL_SET)}.\n"
        f"**If you can make 6**, add: "
        f"{', '.join(t for t in RECOMMENDED_EXTENDED_MINIMUM_SET if t not in MINIMUM_TRIAL_SET)}."
    )
    lines.append("")
    lines.append("## Trials")
    lines.append("")
    lines.append(
        "| Trial | Stitch | Head (cm) | Gauge (st/rnd per 10cm) | Ease | Brim | N | "
        "Fingerprint (short) |"
    )
    lines.append("|---|---|---:|---|---:|---|---:|---|")
    for row in rows:
        lines.append(
            f"| [{row.trial_id}](patterns/{row.trial_id}/review-form.md) | {row.stitch_family} | "
            f"{row.head_circumference_cm} | {row.stitches_per_10cm}/{row.rounds_per_10cm} | "
            f"{row.negative_ease_pct}% | {row.brim_type} | {row.final_body_stitch_count} | "
            f"`{row.pattern_fingerprint[:12]}…` |"
        )
    lines.append("")
    lines.append(
        "Full machine-readable trial data: [`trial-matrix.csv`](trial-matrix.csv), "
        "[`trial-matrix.json`](trial-matrix.json)."
    )
    lines.append("")
    lines.append(
        "See `docs/physical-validation-protocol.md` in the repository for the "
        "full experimental rationale, and `docs/decision-gates.md` for how "
        "results will be used."
    )
    return "\n".join(lines) + "\n"


_CROCHETER_INSTRUCTIONS = """\
# Instructions for physical testers

Thank you for testing a generated pattern. This is software-generated, not
a human-designed pattern — that is exactly what we are testing.

1. Pick a trial from `index.md` (or one assigned to you).
2. Read that trial's `patterns/<TRIAL-ID>/pattern.txt` fully before starting.
3. Make a gauge swatch first and record it in the review form's "Pre-crochet
   information" section, even if it does not match the requested gauge —
   record what you actually got, then decide whether to adjust your hook or
   proceed anyway (and record which you did).
4. Crochet the pattern as written. If something does not work as written,
   do not silently fix it and move on — make the correction, keep going, and
   write down exactly which round and what you changed in the review form's
   "During-crochet evaluation" section. A pattern that needs an undocumented
   fix is a pattern that failed for the next person.
5. Measure the finished item using `measurement-guide.md`'s methods exactly
   — the specific method matters more than which method, so following the
   same one across all trials keeps results comparable.
6. Fill in every section of `review-form.md`, including ratings, using
   `evaluation-rubric.md`'s anchors.
7. Photograph the finished item: front, side, top-down (crown), and a close
   or interior view of the brim if the trial has one. Save alongside your
   completed review form.
8. Return the completed `review-form.md` (and photos) however your
   coordinator has asked for them.

If you are unsure about anything, write down the uncertainty rather than
guessing silently — an honest "not sure" is more useful than a confident
guess that turns out wrong.
"""


def generate_expert_review_pack(output_dir: Path) -> list[TrialRow]:
    """Generate the full expert-review pack under ``output_dir``.

    Returns the compiled trial rows (useful for callers that want to print a
    summary without re-reading the generated files).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    patterns_dir = output_dir / "patterns"
    patterns_dir.mkdir(exist_ok=True)

    triples = build_trial_matrix_rows()
    rows = [row for _, _, row in triples]

    _write_trial_matrix_files(output_dir, rows)

    for trial, pattern, _row in triples:
        _write_trial_files(patterns_dir / trial.trial_id, trial, pattern)

    (output_dir / "index.md").write_text(_index_text(rows), encoding="utf-8")
    (output_dir / "crocheter-instructions.md").write_text(_CROCHETER_INSTRUCTIONS, encoding="utf-8")

    _copy_doc_if_present(output_dir, "measurement-guide.md")
    _copy_doc_if_present(
        output_dir, "evaluation-rubric.md", source_name="expert-evaluation-rubric.md"
    )

    return rows


def _repo_docs_dir() -> Path:
    # src/crochet_reconstruction/physical_validation/review_pack.py -> repo root / docs
    return Path(__file__).resolve().parents[3] / "docs"


def _copy_doc_if_present(output_dir: Path, dest_name: str, source_name: str | None = None) -> None:
    """Copy a canonical doc into the pack so it is self-contained on paper.

    docs/*.md remains the source of truth (it has the full rationale); the
    pack copy is what a tester actually carries around. If the doc has not
    been written yet, a short placeholder is written instead of failing —
    the pack must remain generatable at every stage of this phase's build.
    """
    source = _repo_docs_dir() / (source_name or dest_name)
    destination = output_dir / dest_name
    if source.exists():
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        destination.write_text(
            f"# {dest_name}\n\nNot yet written. See docs/{source_name or dest_name} "
            f"in the repository once available.\n",
            encoding="utf-8",
        )


__all__ = ["generate_expert_review_pack"]
