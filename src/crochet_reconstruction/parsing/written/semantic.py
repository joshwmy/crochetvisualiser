"""Top-level orchestration: raw source -> ``list[Component]`` + diagnostics.

Pipeline stages (see module docstrings for each): source normalisation
(``normalize.py``) -> lexing/grammar parsing (``parser.py``) -> semantic
expansion + conversion into existing ``domain.operations`` (``convert.py``)
-> this module's range expansion, numbering validation, and stitch-count
cross-checks.

Every diagnostic is appended in one deterministic left-to-right pass over
the source lines — the returned list's order never depends on anything but
source order, so identical input always produces an identically-ordered
diagnostics list.
"""

from __future__ import annotations

from crochet_reconstruction.domain.enums import (
    ClosureKind,
    ComponentKind,
    Construction,
    StitchFamily,
)
from crochet_reconstruction.domain.rounds import Component, Round
from crochet_reconstruction.parsing.written.convert import (
    SemanticError,
    contains_unsupported_stitch,
    convert_section,
    infer_dominant_family,
)
from crochet_reconstruction.parsing.written.diagnostics import Diagnostic, DiagnosticCode, is_fatal
from crochet_reconstruction.parsing.written.normalize import (
    normalize_section_line,
    split_into_lines,
)
from crochet_reconstruction.parsing.written.parser import (
    InstructionSyntaxError,
    parse_instruction_body,
)
from crochet_reconstruction.parsing.written.syntax import ParsedSection

MAX_SECTION_LINES = 500
"""Safety limit: number of 'Round N:'-style lines accepted, before range expansion."""

MAX_TOTAL_STITCHES = 20_000
"""Safety limit: total stitches across the whole compiled piece.

Chosen well above the largest realistic hand-written pattern (the
1640-stitch adult beanie reference fixture) while still refusing patterns
engineered to expand into millions of stitches, per the brief's explicit
"fail safely" requirement.
"""


def parse_written_pattern(source: str) -> tuple[list[Component] | None, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []

    if not source or not source.strip():
        diagnostics.append(
            Diagnostic(
                severity="error",
                code=DiagnosticCode.EMPTY_INPUT,
                message="Pattern source is empty.",
            )
        )
        return None, diagnostics

    lines = split_into_lines(source)
    if not lines:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code=DiagnosticCode.EMPTY_INPUT,
                message="Pattern has no content after removing blank lines and comments.",
            )
        )
        return None, diagnostics

    if len(lines) > MAX_SECTION_LINES:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code=DiagnosticCode.INPUT_TOO_LARGE,
                message=f"Pattern has {len(lines)} section lines, exceeding the limit of "
                f"{MAX_SECTION_LINES}.",
                expected=MAX_SECTION_LINES,
                actual=len(lines),
            )
        )
        return None, diagnostics

    sections = _parse_sections(lines, diagnostics)
    if is_fatal(diagnostics):
        return None, diagnostics
    if not sections:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code=DiagnosticCode.EMPTY_INPUT,
                message="No valid sections found.",
            )
        )
        return None, diagnostics

    expanded = _expand_ranges(sections, diagnostics)
    if expanded is None:
        return None, diagnostics

    all_nodes = [node for _, section in expanded for node in section.instructions]
    dominant_family = infer_dominant_family(all_nodes)

    rounds = _convert_sections(expanded, dominant_family, diagnostics)
    if rounds is None:
        return None, diagnostics

    diagnostics.append(
        Diagnostic(
            severity="info",
            code=DiagnosticCode.ASSUMPTION_APPLIED,
            message="No gauge was specified in the written pattern. Using a default "
            "worsted-weight gauge (16 sts/10cm, 16 rows/10cm) for 3D scale only — "
            "stitch counts and structure are unaffected by this default.",
        )
    )

    component = Component(
        kind=ComponentKind.PIECE, construction=Construction.CONTINUOUS, rounds=rounds
    )
    return [component], diagnostics


def _parse_sections(
    lines: list[tuple[int, str]], diagnostics: list[Diagnostic]
) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    for line_number, raw_text in lines:
        normalized = normalize_section_line(line_number, raw_text)
        if normalized is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.INVALID_SYNTAX,
                    message="Line does not match 'Round N:' / 'Row N:' / 'Rounds N-M:' "
                    "section-header syntax.",
                    line=line_number,
                    source_text=raw_text,
                )
            )
            continue

        try:
            instructions = parse_instruction_body(normalized.body)
        except InstructionSyntaxError as exc:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.INVALID_SYNTAX,
                    message=f"Could not parse instructions: {exc}",
                    line=line_number,
                    column=exc.column,
                    source_text=raw_text,
                )
            )
            continue

        if contains_unsupported_stitch(instructions):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.UNSUPPORTED_SYNTAX,
                    message="This section uses 'chain' or 'slip stitch' — recognized by the "
                    "grammar but not yet convertible into stitch-graph geometry.",
                    line=line_number,
                    source_text=raw_text,
                )
            )
            continue

        if normalized.number_end < normalized.number_start:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.INVALID_RANGE,
                    message=f"Section range {normalized.number_start}-{normalized.number_end} "
                    "is backwards.",
                    line=line_number,
                    source_text=raw_text,
                )
            )
            continue

        sections.append(
            ParsedSection(
                kind=normalized.kind,
                number_start=normalized.number_start,
                number_end=normalized.number_end,
                instructions=instructions,
                declared_count=normalized.declared_count,
                line=line_number,
                raw_text=raw_text,
            )
        )
    return sections


def _expand_ranges(
    sections: list[ParsedSection], diagnostics: list[Diagnostic]
) -> list[tuple[int, ParsedSection]] | None:
    expanded: list[tuple[int, ParsedSection]] = []
    for section in sections:
        for number in range(section.number_start, section.number_end + 1):
            expanded.append((number, section))
    expanded.sort(key=lambda pair: pair[0])

    seen_numbers = [n for n, _ in expanded]
    expected_numbers = list(range(1, len(expanded) + 1))
    if seen_numbers != expected_numbers:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code=DiagnosticCode.INVALID_RANGE,
                message="Section numbers must form an unbroken 1..N sequence with no gaps "
                f"or duplicates; got {seen_numbers}.",
                expected=len(expanded),
                actual=len(set(seen_numbers)),
            )
        )
        return None
    return expanded


def _convert_sections(
    expanded: list[tuple[int, ParsedSection]],
    dominant_family: StitchFamily,
    diagnostics: list[Diagnostic],
) -> list[Round] | None:
    rounds: list[Round] = []
    previous_total: int | None = None
    total_stitches_so_far = 0

    for number, section in expanded:
        try:
            converted = convert_section(section, previous_total, dominant_family)
        except SemanticError as exc:
            diagnostics.append(
                exc.to_diagnostic(line=section.line, source_text=section.raw_text, section=number)
            )
            return None

        count_mismatch = (
            section.declared_count is not None
            and converted.produced_total != section.declared_count
        )
        if count_mismatch:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.STITCH_COUNT_MISMATCH,
                    message=f"Round {number} declares {section.declared_count} stitches but "
                    f"expands to {converted.produced_total}.",
                    line=section.line,
                    section=number,
                    source_text=section.raw_text,
                    expected=section.declared_count,
                    actual=converted.produced_total,
                )
            )
            return None

        total_stitches_so_far += converted.produced_total
        if total_stitches_so_far > MAX_TOTAL_STITCHES:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=DiagnosticCode.INPUT_TOO_LARGE,
                    message=f"Pattern would produce more than {MAX_TOTAL_STITCHES} total "
                    "stitches, exceeding the safety limit.",
                    line=section.line,
                    section=number,
                    expected=MAX_TOTAL_STITCHES,
                )
            )
            return None

        rounds.append(
            Round(
                number=number,
                operations=converted.operations,
                stated_total=converted.produced_total,
                closure=ClosureKind.NONE,
            )
        )
        previous_total = converted.produced_total

    return rounds
