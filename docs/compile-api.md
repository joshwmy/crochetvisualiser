# Compile API

Package: `src/crochet_reconstruction/api/` (`app.py`, `config.py`,
`schemas.py`, `service.py`, `routers/visualizer.py`). Separate from
`portal/` — no shared routers, database, or session middleware; the two
FastAPI apps share nothing except being built with FastAPI.

## Endpoints

### `GET /healthz`
`{"status": "ok"}` — no dependencies checked (this API has none: no
database, no file storage).

### `POST /api/visualizer/compile`

Request (camelCase on the wire; Pydantic model `CompileRequest`):

```json
{
  "source": "Round 1: 6 sc in magic ring [6]\n...",
  "terminology": "US",
  "options": { "strict": false }
}
```

- `source` — required. No Pydantic `max_length` (an oversized value is
  handled as a structured `INPUT_TOO_LARGE` diagnostic, not an HTTP 422 —
  see "Error handling philosophy" below).
- `terminology` — `Literal["US"]`, default `"US"`. Any other value is a
  `422` (a request-shape error, not a compile-semantic one).
- `options.strict` — default `false`. When `true`, blocks a compile that only
  succeeded because something was assumed or flagged. See "Strict mode" below.

Response (`CompileResponse`), success:

```json
{
  "success": true,
  "pattern": { "components": [ /* domain.rounds.Component, serialized */ ] },
  "stitchGraph": { /* graph.models.StitchGraph, serialized */ },
  "geometry": { /* geometry.models.GeometryDocument, serialized */ },
  "diagnostics": [ /* zero or more info/warning Diagnostic objects */ ],
  "summary": {
    "sectionCount": 8,
    "stitchCount": 108,
    "componentCount": 1,
    "graphFingerprint": "...",
    "geometryFingerprint": "..."
  }
}
```

`pattern` is `{"components": [...]}`, **not** a full beanie `Pattern` —
see `docs/crochet-ir-spec.md` for why a written pattern has no
`ProjectInput`/`CalculatedParameters` equivalent to populate honestly.

Response, failure (`success: false`): `pattern`/`stitchGraph`/`geometry`/
`summary` are all `null`; `diagnostics` has at least one `severity: "error"`
entry. See `docs/diagnostic-codes.md` for the full code catalogue.

### `POST /api/visualizer/diagram/analyse`

Package addition: `diagram_schemas.py`, `diagram_service.py`,
`routers/diagram.py` — a separate router module from `visualizer.py`
(same app, same `/api/visualizer` prefix family, different sub-path), kept
apart so the two input paths' request/response shapes never mix in one
file. Full detail in `docs/svg-diagram-ingestion.md`.

Request (`DiagramAnalyseRequest`):

```json
{ "svgSource": "<svg xmlns=\"...\">...</svg>", "options": { "constructionMode": "circular", "strict": false } }
```

Response (`DiagramAnalyseResponse`) — note `diagram` is the deep
`DiagramDocument` payload and stays **snake_case** internally (only the
wrapper's own top-level keys are camelCase — see
`api/diagram_schemas.py`'s module docstring):

```json
{
  "success": true,
  "diagram": { "schema_version": "1.0.0", "symbols": [ /* snake_case fields */ ], "...": "..." },
  "diagnostics": [ /* zero or more DiagramDiagnostic objects */ ],
  "summary": { "symbolCount": 18, "classifiedCount": 17, "unclassifiedCount": 1, "roundCount": 3, "lowConfidenceCount": 2, "readyToCompile": false }
}
```

`success: false` happens only when the SVG itself couldn't be parsed
safely (`diagram: null`) — a successfully parsed-but-imperfect chart
(unclassified symbols, low confidence) still returns `success: true` with
`summary.readyToCompile: false`, since analysis itself succeeded even
though compiling would currently be blocked.

### `POST /api/visualizer/diagram/compile`

Request (`DiagramCompileRequest`):

```json
{ "diagram": { /* the DiagramDocument returned by analyse, possibly hand-edited */ }, "corrections": { /* DiagramCorrectionSet, see docs/diagram-corrections.md */ }, "options": { "strict": false } }
```

Response (`DiagramCompileResponse`) — reuses the written-pattern
`CompileResponse`'s summary shape, plus `sourceKind`/`diagram`:

```json
{
  "success": true,
  "sourceKind": "svg_diagram",
  "diagram": { /* the corrected, re-inferred DiagramDocument */ },
  "stitchGraph": { /* graph.models.StitchGraph, unchanged type */ },
  "geometry": { /* geometry.models.GeometryDocument, unchanged type */ },
  "diagnostics": [],
  "summary": { "sectionCount": 3, "stitchCount": 42, "componentCount": 1, "graphFingerprint": "...", "geometryFingerprint": "..." }
}
```

Blocked by unresolved errors (an uncorrected unclassified/ambiguous
symbol, a graph-validation failure, ...): `stitchGraph`/`geometry`/
`summary` are `null`, `diagnostics` carries the blocking error(s), and
`diagram` still carries the (corrected, re-inferred) document so the
frontend can show the user exactly what's still wrong without re-analysing
from scratch.

Neither diagram endpoint stores the submitted SVG or corrections
server-side — see `docs/diagram-corrections.md`, "No server-side
persistence."

## Strict mode

`options.strict` (`api/strict_mode.py` — one policy, shared by both compile
paths so the two can't drift). It blocks a compile that **only succeeded
because something was assumed or flagged**:

- any `warning`-severity diagnostic, and
- the written path's `ASSUMPTION_APPLIED` info diagnostic, which records that
  the default gauge was substituted for one the pattern never stated.

`ASSUMPTION_APPLIED` is `info` rather than `warning` because a normal compile
is perfectly happy to apply it — but a caller asking for strict interpretation
is precisely one who doesn't want an unstated value quietly filled in, so it
counts here despite its severity. `error` diagnostics are not strict mode's
business: they already block in both modes.

| Endpoint | Default | `strict: true` effect |
|---|---|---|
| `POST /compile` | `false` | Blocks with `STRICT_MODE_BLOCKED`; `pattern`/`stitchGraph`/`geometry`/`summary` all `null`. |
| `POST /diagram/analyse` | `false` | Withholds `summary.readyToCompile` only. **Never fails the analysis** — reporting what the chart contains is analysis's job, and refusing would leave the user nothing to correct in 2D review. |
| `POST /diagram/compile` | `false` | Blocks with `STRICT_MODE_BLOCKED`; `diagram` is still returned so the user can see and fix what was objected to. |

**The default is `false`, which reproduces exactly the behaviour this field
had while it was a documented no-op.** It previously defaulted to `true`, so
implementing it under the old default would have started failing every
existing caller — including the viewer, which sends no `options` at all and
therefore takes the `false` default. Strict is opt-in.

The strict check runs **last**, only once the pipeline has otherwise
succeeded: strict turns an otherwise-valid compile into a refusal, so running
it earlier would mask genuine errors behind a strictness complaint. The
blocking diagnostics are returned alongside `STRICT_MODE_BLOCKED`, whose
message names the distinct codes rather than repeating their text.

## Error handling philosophy

- **Structural request errors** (malformed JSON, invalid `terminology`,
  wrong field types) → FastAPI's own `422` response. Not our envelope —
  these mean the client sent something that isn't a valid request at all.
- **Compile-semantic errors** (empty input, oversized input, unsupported
  syntax, count mismatches, internal failures) → `200` with
  `success: false` and structured diagnostics. These are legitimate,
  expected outcomes of compiling *some* input, not request bugs.
- **Never a traceback.** Every exception in `api/service.py` is caught,
  logged server-side (`logging.getLogger(__name__).exception(...)`), and
  translated to a generic, safe message with `INTERNAL_SERVER_FAILURE`.

## Safety limits

| Limit | Where | Default |
|---|---|---|
| Request character count | `ApiSettings.max_source_length` (`VISUALIZER_MAX_SOURCE_LENGTH`) | 50,000 |
| Section-header lines | `parsing.written.semantic.MAX_SECTION_LINES` | 500 |
| Total stitches (checked incrementally per round) | `parsing.written.semantic.MAX_TOTAL_STITCHES` | 20,000 |
| Single `repeat N times` | `domain.operations.MAX_REPEAT_TIMES` (existing, unmodified) | 200 |
| Nested repeat depth | `domain.operations.MAX_REPEAT_DEPTH` (existing, unmodified) | 4 |

A pattern engineered to expand into millions of stitches fails with
`INPUT_TOO_LARGE` as soon as the running total crosses the limit — it never
attempts the full expansion first.

The diagram endpoints have their own, separate limit set
(`diagram.security.SafetyLimits`) sized for SVG byte content rather than
pattern-text character count — see `docs/svg-security.md` for the full
table and threat model.

## Configuration

Environment variables (`api/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `VISUALIZER_ENVIRONMENT` | `development` | Informational; no environment-gated behaviour differs today (no secrets, no debug endpoints to hide). |
| `VISUALIZER_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allow-list. Must be set explicitly for any non-local deployment. |
| `VISUALIZER_MAX_SOURCE_LENGTH` | `50000` | See limits table above. |

No `.env` file is read automatically — these are plain OS environment
variables, consistent with this API having no secrets to keep out of
version control in the first place.

## Running it

```bash
pip install -e ".[dev,api]"
uvicorn crochet_reconstruction.api.app:create_app --factory --reload --port 8000
```

`GET http://localhost:8000/healthz` should return `{"status": "ok"}`.

## JSON Schema

`CompileRequest`/`CompileResponse`/`Diagnostic` (plus `StitchGraph` and
`GeometryDocument`, which `CompileResponse` embeds) are Pydantic v2 models.
Their JSON Schema is now committed as versioned files under `schemas/`,
generated reproducibly by `crochet_reconstruction.api.schema_export` and
match-tested (`tests/test_schema_export.py`) so a committed copy can never
silently drift from the models it describes. See
`docs/schema-artifacts.md` for the generation command and compatibility
policy, and `docs/open-source-resource-adoption.md`'s JSON Schema entry for
why this differs from the written-pattern slice's original "generate on
demand, don't commit" decision (this completion audit raised the bar).
