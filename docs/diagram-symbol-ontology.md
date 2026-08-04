# Diagram symbol ontology

The bounded, canonical symbol vocabulary this slice recognises, the
deterministic classification priority order, and the confidence model. See
`src/crochet_reconstruction/diagram/ontology.py` for the authoritative
code.

## Canonical vs. display terminology

Internal identity is always the canonical (terminology-independent) name —
`single_crochet`, never a US/UK display abbreviation — mirroring the
written-pattern parser's existing separation (`docs/terminology.md`).

## Supported vocabulary (`DiagramStitchType`)

| Canonical name | Notes |
|---|---|
| `magic_ring` | Foundation ring. Structural: never becomes its own `StitchNode` — round-1 stitches get `into_ring=True` instead (matches the existing written-pattern `MagicRingOp` handling exactly). |
| `chain` | Chain-ring foundation alternative. Same structural treatment as `magic_ring` when used as a centre. |
| `slip_stitch` | Primarily recognised as a round-closure marker (maps to the existing `round_closure` edge + `ClosureKind.SLIP_STITCH_JOIN`, not a new `StitchNode`). |
| `single_crochet` | Worked stitch → `StitchFamily.SC`. |
| `half_double_crochet` | Worked stitch → `StitchFamily.HDC`. |
| `double_crochet` | Worked stitch → `StitchFamily.DC`. |
| `increase` | Worked stitch, defaults to `StitchFamily.SC` if no more specific type is given — see "Increase/decrease" below. |
| `decrease` | Same default-to-SC treatment as `increase`. |
| `join` | Explicit round-closure marker (alternative to `slip_stitch` for this purpose). |

**Reserved for a later slice** (`ReservedFutureStitchType`): `treble_crochet`,
`picot`, `puff_stitch`, `bobble`, `cluster`, `front_post`, `back_post`.
Recognising one of these labels in metadata produces an explicit
`UNSUPPORTED_SYMBOL` diagnostic (blocking, requiring a manual correction)
— never a silent best-effort mapping to something else.

### Why more members than `domain.enums.StitchFamily`

A chart needs to talk about *foundation and closure* concepts
(`magic_ring`, `chain`, `join`) that the existing `StitchGraph` schema
already represents structurally rather than as a stitch-typed node — adding
new `StitchFamily` members for them would mean compiler/geometry support
that doesn't exist and shouldn't (per `domain/enums.py`'s own documented
principle: an enum member with no compiler support is a trap, not a
feature flag). `DiagramTopologyCompiler` (`compiler.py`) converts these
structural symbol types into the existing `into_ring`/`round_closure`
mechanisms instead.

### Increase/decrease: topology, not a unique glyph

Per the brief's explicit allowance: "acceptable for increases and
decreases to be represented through topology rather than a unique glyph."
The *fact* of an increase (one parent, multiple children) or decrease
(multiple parents, one child) is always established by
`diagram/topology.py`'s parent-attachment inference — an explicit
`increase`/`decrease` symbol is one more piece of classification evidence
feeding that inference, not a bypass of it. See
`docs/diagram-topology-inference.md`.

## Aliases

Short-form aliases are accepted anywhere a canonical label is matched
(`data-stitch-type`, element `id`, CSS class, `<title>` text,
`aria-label`) — `ontology.ALIAS_TOKENS`: `sc`, `hdc`, `dc`, `ch`, `sl`/`ss`/`slst`,
`mr`/`ring`, `inc`, `dec`. Hyphens and underscores are treated as
interchangeable, matching is case-insensitive.

## Classification priority order (`ClassificationMethod`)

Highest to lowest, per `extraction.py`. A method never overrides a result
from a higher-priority method — the brief's "never let a low-confidence
geometric heuristic override explicit metadata," applied strictly:

1. `data_attribute` — `data-stitch-type="..."` on the element itself.
2. `use_reference` — a `<use href="#...">` whose *target* id/naming
   resolves to a known label (checked before the `<use>` element's own
   `id`/`class`, on the reasoning that a referenced symbol-library
   definition is stronger evidence than an arbitrary human-chosen id that
   happens to contain a recognisable substring).
3. `element_id` — the element's own `id` attribute.
4. `css_class` — any token in the element's `class` list.
5. `title` — a `<title>` child element's text.
6. `aria_label` — the `aria-label` attribute.
7. `text_label` — a free-standing `<text>` element naming a stitch type,
   unambiguously nearest to this candidate. See "Text-label association"
   below.
8. `primitive_geometry` — the bounded shape heuristic (below).
9. `unclassified` — none of the above resolved.

Containers (`<defs>`/`<symbol>`) are never scanned directly for
candidates — their content is only a candidate once instantiated via
`<use>` (otherwise the same subtree would be extracted twice: once as the
untransformed definition, once per instance). Elements explicitly marked
as connectors (`class="connector"` or `data-connector="true"`) are
recognised separately and never treated as stitch symbols — see
`docs/diagram-topology-inference.md`.

## Text-label association (`text_labels.py`)

A chart can name a symbol with a free-standing `<text>` sitting beside it
("dc", "sc") instead of carrying metadata on the element. Nothing in the SVG
says which symbol such a label belongs to, so the association is inferred
from position — which is why this method ranks below every declared-metadata
method and can never override one.

It ranks *above* `primitive_geometry` because the label's **content** is
explicit: "dc" written by the chart's author is a stronger statement about
intent than counting strokes in the artwork. Only the attachment is inferred,
not the meaning.

Only text that resolves to a known stitch type (canonical name or alias,
normalised) is considered a label at all. A chart's round numbers, stitch
counts, and titles — `3`, `18 sts`, `Round 4` — resolve to nothing and are
ignored rather than parsed. Using a chart's printed round labels to seed or
validate round numbering remains a separate, unimplemented gap
(`docs/known-limitations.md`).

Two guards, both of which **fail closed** — a rejected association falls
through to the geometry heuristic or to unclassified, exactly as before this
method existed, and never produces a guessed classification:

| Guard | Rule | Constant |
|---|---|---|
| Range | The label must be within N × the symbol's own bounding-box diagonal. Expressed relative to the symbol's own size, so it is independent of the chart's scale. | `MAX_DISTANCE_BBOX_DIAGONALS = 1.5` |
| Mutual nearest | The symbol must be the label's nearest eligible candidate **and** the label the symbol's nearest eligible label, each beating the runner-up by this factor. A label midway between two symbols classifies neither. | `AMBIGUITY_SEPARATION_RATIO = 1.5` |

A symbol with a degenerate zero-area bounding box can never be labelled —
there is no size to scale the search radius against, and falling back to an
absolute distance would make the rule depend on the chart's arbitrary scale.

Neither constant is a crochet fact; both describe chart *layout*. Loosening
them cannot silently turn an unclassified symbol into a wrong one — it would
only widen which labels are considered, and the mutual-nearest rule still has
to hold.

Extraction therefore runs in two phases (`extraction.py`): the walk collects
candidates in document order, then a second pass resolves classification once
every candidate's position is known. Symbols are still emitted in document
order, so `symbol_id` numbering is unaffected.

Worked example: `tests/diagram/fixtures/svg/text_labelled.svg`, where six
centred-cross symbols — which the geometry heuristic reads as
`single_crochet` — are labelled "dc" and compile as `double_crochet`.

## Primitive geometry heuristic (`classification.py`)

Deliberately *not* general computer vision — a small set of fixed,
deterministic shape checks against a symbol's own **local** (untransformed)
geometry, calibrated to this project's own synthetic fixture convention
(symbols authored on roughly a 10-local-unit box —
`tests/diagram/fixtures/svg/`). A chart using different artwork with no
metadata will get `unclassified` results here, which is correct, bounded
behaviour per the brief's explicit instruction, not a bug to "fix" by
guessing harder.

| Shape | Feature | Classified as |
|---|---|---|
| Circle / ellipse | — | `chain` (a loop shape) |
| Short single stroke or small `rect`/dot | length/size ≤ 3 local units | `slip_stitch` |
| Two strokes crossing near both strokes' own midpoints | — | `single_crochet` (a centred cross/+) |
| Two strokes, one vertical + one horizontal crossbar near the top (5–45% down the vertical span) | — | `half_double_crochet` (a T-shape) |
| One vertical + two horizontal crossbars | — | `double_crochet` |
| Anything else (curves, >3 strokes, off-centre/off-axis crossings) | — | `unclassified`, or `ambiguous` with multiple candidates if the shape is genuinely close to two categories |

A symbol authored as one multi-subpath `<path>` or as several sibling
`<line>`/`<path>` primitives with no further relative transform (this
project's own authoring convention — see
`extraction.py`'s `collect_strokes_for_classification`) are both accepted;
curved paths (`C`/`S`/`Q`/`T`/`A` commands) are always "too complex for
this bounded heuristic" and fall through to unclassified rather than being
approximated.

Magic-ring detection is deliberately **not** attempted via geometry alone
— distinguishing a centre ring from an ordinary chain-loop by shape would
require knowing the chart's centre first, which is circular with centre
detection itself. Only explicit metadata can mark a symbol as
`magic_ring`; a chart relying on pure geometry for its centre symbol will
have that one symbol left unclassified, requiring a one-click correction.

## Confidence model

A simple, explainable score per evidence *source* — not a machine-learning
probability, never displayed as one. `ontology.CONFIDENCE_BY_METHOD`:

| Method | Confidence |
|---|---|
| `manual_override` / `data_attribute` | 1.0 |
| `use_reference` | 0.9 |
| `element_id` / `css_class` | 0.8 |
| `title` | 0.75 |
| `aria_label` / `text_label` / `primitive_geometry` | 0.7 |
| `unclassified` | 0.0 |

An ambiguous symbol (multiple plausible primitive-geometry candidates)
also gets confidence `0.0` — a deliberately conservative choice that
forces review rather than picking a "best guess" candidate and hoping.

Displayed to the user as a band, never a raw number implying precision the
model doesn't have (`ontology.confidence_band`):

- **High** (`≥ 0.85`)
- **Medium** (`≥ 0.6`)
- **Low** (`< 0.6`)
- **Manual** (any symbol touched by a correction, regardless of its
  numeric score — corrections are never re-scored against the automatic
  scale)

`REVIEW_REQUIRED_THRESHOLD = 0.5` — the brief's "<0.5 requires review"
line — drives the analysis summary's `lowConfidenceCount` and the
frontend's confidence-colour legend, but does **not** by itself block
compile; only an actually-unresolved symbol (`stitch_type is None` —
`unclassified` or `ambiguous`) blocks compile, since those are the cases
that would otherwise silently vanish from the compiled graph (see
`diagram/pipeline.py`'s re-derivation of blocking diagnostics after
corrections).

## Craft Yarn Council / CrochetPARADE note

This ontology's canonical names and semantic mappings were authored as a
terminology and concept reference against the Craft Yarn Council's public
crochet-symbol standard and against CrochetPARADE's published semantics —
**as an ontology reference, not as redistributed artwork or code**. No
Craft Yarn Council symbol artwork and no CrochetPARADE source code is
present anywhere in this repository; every synthetic fixture symbol shape
in `tests/diagram/fixtures/svg/` was authored from scratch for this
project. See `docs/open-source-resource-adoption.md` for the full
licensing/clean-room record.
