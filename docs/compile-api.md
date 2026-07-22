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
  "options": { "strict": true }
}
```

- `source` — required. No Pydantic `max_length` (an oversized value is
  handled as a structured `INPUT_TOO_LARGE` diagnostic, not an HTTP 422 —
  see "Error handling philosophy" below).
- `terminology` — `Literal["US"]`, default `"US"`. Any other value is a
  `422` (a request-shape error, not a compile-semantic one).
- `options.strict` — accepted, currently has no behavioural effect
  (reserved for a future stricter interpretation mode). Documented, not
  silently ignored.

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
