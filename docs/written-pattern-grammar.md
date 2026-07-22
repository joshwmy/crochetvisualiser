# Written-pattern grammar and deterministic assumptions

Package: `src/crochet_reconstruction/parsing/written/` (`normalize.py`,
`grammar.lark`, `parser.py`, `syntax.py`, `convert.py`, `semantic.py`,
`diagnostics.py`).

## Pipeline

```
Raw text
  -> normalize.py       (source normalisation: phrase canonicalisation, declared-count extraction)
  -> grammar.lark + parser.py   (Lark Earley grammar -> syntax.py tree)
  -> convert.py          (semantic expansion: repeats, "around", increase/decrease stitch-type inference)
  -> semantic.py          (range expansion, section-numbering validation, stitch-count cross-checks)
  -> domain.rounds.Component / domain.operations.Operation   (existing domain model, unmodified)
  -> graph.builder.build_stitch_graph   (existing, unmodified)
  -> graph.validation.validate_graph    (existing, unmodified)
  -> geometry.layout.build_geometry     (existing, unmodified)
```

Nothing downstream of "existing domain model" was changed to accommodate
this parser — see `docs/crochet-ir-spec.md` for the two additive-only domain
changes that *were* needed (`ComponentKind.PIECE`, `StitchFamily.DC`).

## Supported syntax

| Category | Recognised forms |
|---|---|
| Stitches | `sc`/`single crochet`, `hdc`/`half double crochet`, `dc`/`double crochet` |
| Increase/decrease | `inc`/`increase`, `dec`/`decrease` |
| Foundation | `magic ring`, `magic circle` (as `"<N> <stitch> in magic ring"`) |
| Section headers | `round`/`rounds`/`rnd`/`rnds`, `row`/`rows`, with a number or `N-M` range |
| Grouping | `(a, b, ...)` parenthesised instruction lists |
| Repetition | `(...) repeat N times` / `(...) rep N times`, `around`, `in each stitch around` |
| Declared counts | `[18]`, `(18)`, `18 sts` — trailing, optional |
| Formatting | any case, extra whitespace, trailing `.`, blank lines, `#`/`//` comment lines |

Recognised **but explicitly unsupported** (grammar accepts the token, then
semantic conversion rejects it with `UNSUPPORTED_SYNTAX`, never silently
misinterpreted as something else): `ch`/`chain`, `sl st`/`slip stitch`. Both
require turning-chain/join semantics the domain model doesn't have yet
(see `docs/known-limitations.md`).

**Everything else fails as `INVALID_SYNTAX`** with a line/column pointer —
per the brief, this parser is intentionally narrow and must fail clearly
rather than guess. Phrases like "work even," "repeat from *," "increase
evenly," or "shape as established" are not recognised at all and produce
`INVALID_SYNTAX`, not a silent guess.

## Why Lark, and why regex too

Lark (`grammar.lark`) does all *structural* parsing: instruction lists,
grouping, repeat/around phrases, stitch tokens. Regex in `normalize.py` is
used only for two narrowly-scoped, documented jobs the brief explicitly
carves out as acceptable preprocessing:

1. **Phrase canonicalisation** — collapsing known multi-word synonyms
   (`"half double crochet"` → `hdc`, `"in each stitch around"` →
   `ineachstitcharound`) into single tokens *before* the grammar ever sees
   them, so the grammar itself never has to encode multi-word terminals.
2. **Section-header/declared-count extraction** — splitting off
   `"Round N:"`/`"Rows N-M:"` and a trailing `[18]`/`(18)`/`18 sts` via
   fixed, tightly-anchored patterns, so the grammar only has to parse the
   instruction-list body, not the header/footer syntax around it.

Both are complete, fixed substitution tables — not an evolving,
undocumented chain of ad-hoc regex fixes standing in for a real parser.

## Deterministic assumptions (every one required by the brief)

- **`X around` / `X in each stitch around`**: repeat count is
  `previous_round_total // consumed_per_repeat(X)` — always derived from
  the *previous round's actual stitch total*, never from the declared
  count (which is still cross-checked afterward). Non-integer division is
  a hard `INVALID_REPEAT` error, not a rounded guess.
- **Sequential parent consumption**: increases/decreases/plain stitches
  consume the previous round's stitches strictly left-to-right — inherited
  directly from `graph.builder`'s own documented assumption (see
  `docs/stitch-graph-spec.md`); the written-pattern layer doesn't add a
  second one.
- **Increase**: fixed `input=1, output=2` per occurrence (`"3 inc"` means
  three separate increases in sequence, not one `input=3` increase).
- **Decrease**: fixed `input=2, output=1` per occurrence, same repetition
  rule for `"N dec"`.
- **Range expansion**: `"Rounds 4-6: sc around [18]"` applies the *same*
  instructions independently to rounds 4, 5, and 6 — each round is
  evaluated (and cross-checked against its own previous round) on its own,
  not divided across the range.
- **Section numbering**: after range expansion, section numbers must form
  an unbroken `1..N` sequence (order in the source text doesn't matter,
  gaps and duplicates do) — enforced as `INVALID_RANGE`.
- **Magic-ring foundation**: always the first section, consumes zero
  parent stitches; any `around`/plain-stitch instruction on the first
  section (which by definition has no previous round) is `MISSING_FOUNDATION`.
- **Construction style**: every written pattern compiles to one
  `Construction.CONTINUOUS` component (`ComponentKind.PIECE`) — there is no
  written-pattern syntax yet for joined rounds, matching the fact that the
  underlying engine has never produced `JOINED` rounds either.
- **Increase/decrease stitch type**: defaults to the pattern's "dominant"
  plain-stitch family — the first `sc`/`hdc`/`dc` token found anywhere in
  the source (or `sc` if the pattern never uses a plain stitch at all).
  Written patterns don't name a stitch type on `inc`/`dec` tokens the way
  this domain model's `IncreaseOp.stitch`/`DecreaseOp.stitch` fields
  require one; this is the one place a default is genuinely unavoidable,
  and it's recorded as an `ASSUMPTION_APPLIED` diagnostic.
- **Gauge**: a written pattern has no `ProjectInput.gauge` equivalent, so
  `DEFAULT_WRITTEN_PATTERN_GAUGE` (16 sts/10cm, 16 rows/10cm — a generic
  worsted-weight SC gauge) is used for 3D scale only. Never affects stitch
  counts or graph structure, and is always reported as an `info`-level
  `ASSUMPTION_APPLIED` diagnostic, never applied silently.

## Determinism guarantees

For identical normalised source and parser version: identical
`list[Component]` output, identical stitch IDs (via the unmodified graph
builder), identical graph/geometry fingerprints, and identically-ordered
diagnostics (always emitted in one left-to-right pass over source lines,
never re-sorted). Verified directly by
`tests/parsing/test_written_parser.py::test_deterministic_output` and
`tests/parsing/test_written_to_graph.py::test_stitch_ids_are_stable_across_recompiles`.

## Safety limits

`MAX_SECTION_LINES = 500` (section-header lines, before range expansion),
`MAX_TOTAL_STITCHES = 20_000` (checked incrementally, round by round, so a
pathological pattern fails as soon as the running total crosses the limit
rather than after fully expanding). Both produce a structured
`INPUT_TOO_LARGE` diagnostic, never an unbounded loop or an unhandled
exception. `MAX_REPEAT_TIMES` (200, from the existing
`domain.operations` module) bounds any single `repeat N times`/`RepeatOp`
regardless of source. The API layer adds a separate, independent
character-count limit (`VISUALIZER_MAX_SOURCE_LENGTH`, default 50,000) — see
`docs/compile-api.md`.

## Example fixtures

`tests/parsing/test_written_parser.py` and `test_written_to_graph.py`
contain the brief's full amigurumi example plus small hand-authored
fixtures for every documented error path (missing foundation, insufficient
parents, count mismatch, invalid range/repeat, unsupported chain/slip
stitch). No external or copyrighted pattern text is used anywhere.
