# Diagnostic codes

Shared model: `src/crochet_reconstruction/parsing/written/diagnostics.py`'s
`Diagnostic` (severity/code/message/line/column/section/source_text/
expected/actual) and `DiagnosticCode`. The same model is returned verbatim
by the compile API (`diagnostics: Diagnostic[]` in `CompileResponse`) and
rendered by the viewer's diagnostics panel.

| Code | Severity | Meaning | Example trigger |
|---|---|---|---|
| `INVALID_SYNTAX` | error | Line doesn't match section-header syntax, or its instruction body doesn't match the grammar at all. | `Round 1: 6 xyz in magic ring [6]` |
| `UNSUPPORTED_SYNTAX` | error | Grammar recognised the tokens, but semantic conversion can't represent them yet. | `Round 1: 10 ch [10]` (chain), `sl st around` (slip stitch) |
| `AMBIGUOUS_SYNTAX` | error | Reserved for a future written-parser slice handling free-text phrases ("work even," "repeat from *"). Not currently emitted — those phrases fail as `INVALID_SYNTAX` today since the grammar doesn't recognise them at all yet. |
| `UNKNOWN_ABBREVIATION` | error | Reserved; currently folded into `INVALID_SYNTAX` since an unrecognised stitch word fails grammar matching before any abbreviation-specific check runs. |
| `MISSING_FOUNDATION` | error | `around`/plain-stitch instruction on the first section, which has no previous round. | `Round 1: sc around [6]` |
| `INVALID_RANGE` | error | A `N-M` range is backwards, or the full section-number sequence has a gap/duplicate after expansion. | `Round 5-1: ...`, or `Round 1` followed by `Round 3` with no `Round 2` |
| `INVALID_REPEAT` | error | `around`/`in each stitch around` can't be resolved because the previous round's total isn't evenly divisible by the operation's consumed-stitch count, or the operation consumes zero stitches. | 5-stitch previous round, `dec around` (needs a multiple of 2) |
| `STITCH_COUNT_MISMATCH` | error | A section's declared count (`[N]`/`(N)`/`N sts`) doesn't match what its instructions actually produce. | `Round 2: inc around [999]` when the real total is 12 |
| `INSUFFICIENT_PARENT_STITCHES` | error | A section's instructions consume a different number of previous-round stitches than actually exist (too many *or* too few — both directions use this code, message text disambiguates). | `(sc, inc) repeat 3 times` needing 6 parents when only 3 exist |
| `INVALID_INCREASE` | error | A constructed `IncreaseOp` failed Pydantic validation (defensive — the parser's own arithmetic shouldn't be able to trigger this). |
| `INVALID_DECREASE` | error | Reserved analogue of `INVALID_INCREASE` for decreases; not separately distinguished today since the parser always constructs decreases with the fixed, always-valid `input=2, output=1`. |
| `GRAPH_VALIDATION_FAILURE` | error | A syntactically and semantically valid section list still failed `graph.validation.validate_graph` (defensive — should not happen for parser output that passed `semantic.py`'s own checks). |
| `GEOMETRY_GENERATION_FAILURE` | error | Geometry generation raised after a valid graph was built (defensive). |
| `INTERNAL_SERVER_FAILURE` | error | An unexpected exception was caught server-side. The client never receives the exception's message or a traceback — only this generic code and a static message; the real exception is logged server-side via Python's `logging` module. |
| `EMPTY_INPUT` | error | Source is empty, whitespace-only, or has no content after stripping blank lines/comments. |
| `INPUT_TOO_LARGE` | error | Source exceeds the API's character limit (`VISUALIZER_MAX_SOURCE_LENGTH`), or the pattern's own section count/stitch-count safety limits (`MAX_SECTION_LINES`, `MAX_TOTAL_STITCHES` in `semantic.py`). |
| `INVALID_TERMINOLOGY` | — | Not actually emitted as a `Diagnostic` — an unsupported `terminology` value is rejected by FastAPI/Pydantic request validation (HTTP 422) before compilation ever starts, since it's a request-shape error, not a compile-semantic one. Documented here because the brief lists it alongside the others. |
| `ASSUMPTION_APPLIED` | info | A deterministic default was used because the source didn't specify something (currently: the default gauge, since written patterns have no gauge field). Never blocks a successful compile **unless `options.strict` is set** — see `STRICT_MODE_BLOCKED`. |
| `STRICT_MODE_BLOCKED` | error | `options.strict` was set and the compile produced a diagnostic that would not normally block: any `warning`, or `ASSUMPTION_APPLIED`. The offending diagnostics are returned alongside this one; its message names their distinct codes. Also exists as a `DiagramDiagnosticCode` for the diagram compile path — same policy, see `docs/compile-api.md`'s "Strict mode". |

## Design notes

- **Never a raw traceback.** Every exception path in `api/service.py`
  catches broadly, logs the real exception server-side, and returns one of
  the codes above with a static, safe message — verified by
  `tests/api/test_compile_endpoint.py::test_no_traceback_leakage_on_any_response`.
- **Ordering is deterministic.** Diagnostics are appended in exactly one
  left-to-right pass over source lines (`semantic.py`); the list is never
  re-sorted, so identical input always produces an identically-ordered
  diagnostics list.
- **`INSUFFICIENT_PARENT_STITCHES` covers both directions** (too few *and*
  too many previous-round stitches consumed) rather than splitting into two
  codes, since both represent the same underlying problem — a section's
  instructions don't match its previous round — and the `expected`/`actual`
  fields already disambiguate which direction occurred.
