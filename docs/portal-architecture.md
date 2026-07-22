# Portal architecture

## Why this exists

Phase 1/1.5 built a deterministic pattern engine and physical-validation
tooling with **no image handling, no contributor identity, no consent
model, and no web interface at all** (confirmed by direct repository audit,
not assumed). This portal is the smallest thing that fills that gap for a
small, invited pilot — not a rebuild of anything that existed.

## What it reuses vs. adds

**Reused, unchanged:** `domain/`, `engine/`, `validation/`, `rendering/`,
`physical_validation/`. The only touch point is
`services.link_physical_trial`, which imports
`physical_validation.trial_matrix.TRIAL_MATRIX` and `compile_trial` to
validate a `trial_id`/`pattern_fingerprint` pair against the live engine —
the exact same pattern `physical_validation.ingestion.verify_against_trial_matrix`
already used.

**Added:** everything under `src/crochet_reconstruction/portal/`, plus
`alembic/`, `Dockerfile`, `docker-compose.yml`, `.env.example`, and four new
CLI subcommands (`portal-create-admin`, `portal-create-invitation`,
`portal-export-approved`, `portal-backup`).

## Dependency boundary

The deterministic engine's core install (`pip install .`) still pulls in
only `pydantic`. FastAPI, SQLAlchemy, Pillow, Jinja2, and Alembic are all
behind the `portal` extra (`pip install ".[portal]"`). `cli.py`'s
`portal-*` subcommands import these lazily, inside the function body, so
running `generate`/`expert-review-pack`/`evaluate` never requires the
portal extra to be installed.

## Layers

```
Contributor browser / Administrator browser
                  ↓
routers/contributor.py, routers/admin.py   (HTTP only: parse request, call a
                  ↓                          service, render a template)
services.py                                 (all business rules live here)
                  ↓
models.py (SQLAlchemy) + schemas.py (Pydantic input validation)
                  ↓
storage.py (files) + db.py (SQLite via SQLAlchemy)
```

Routes never contain business rules and never issue raw queries with
decision logic embedded — every state transition, validation rule, and
side effect (audit logging, file writes) happens in `services.py`, which is
independently unit-testable without an HTTP client (see
`tests/portal/test_services.py`).

## Data model

| Entity | Purpose |
|---|---|
| `AdminUser` | Reviewer account (PBKDF2 password hash). |
| `Invitation` | Hashed token, expiry, use count/limit. |
| `Contributor` | Created on first invitation redemption; minimal (a display name, optional email). |
| `CrochetProject` | One submission. Contributor-entered project/construction details live directly on this row. |
| `ProjectMetadata` | 1:1. Materials, gauge, measurements — all nullable, `unknown` is a first-class value. |
| `ConsentRecord` | 1:1 per project (not per contributor — permissions are meaningfully per-submission). Every permission is its own boolean column. |
| `ProjectImage` | One row per uploaded photo: type, dimensions, format, SHA-256, duplicate flag. Never a raw filesystem path. |
| `PhysicalTrialLink` | Optional link to a generated trial (`trial_id` + `pattern_fingerprint`), validated against the live engine. |
| `ReviewDecision` | One row per admin action (approve/reject/changes_requested/note). Reviewer-confirmed values live only here — never overwrite the contributor's original row. |
| `AuditEvent` | Append-only. `detail` is a short text field; **never** holds image bytes. |

## Password hashing choice

PBKDF2-HMAC-SHA256 via the stdlib `hashlib`, 600,000 iterations, instead of
bcrypt/argon2 — a deliberate tradeoff to avoid adding a new dependency for
a small, low-account-count admin pool. Documented here so it is a decision,
not an oversight; revisit if the admin pool grows or if a security review
recommends otherwise.

## Storage abstraction

`storage.StorageBackend` is an ABC (`save_original`, `save_preview`,
`read_original`, `read_preview`, `delete_project_files`, `write_export`,
`write_backup`). `LocalFileStorage` is the only implementation. An
S3-compatible backend can be added later by implementing the same
interface — no route or service code would need to change. This is **not
implemented** now, per the brief's instruction not to add cloud storage
unless the deployment needs it.

## Sessions and CSRF

Starlette's signed-cookie `SessionMiddleware` (secret from
`PORTAL_SECRET_KEY`) backs both admin sessions and the contributor's
in-progress-submission session. CSRF uses a synchronizer token stored in
that same session and checked on every state-changing POST
(`auth.validate_csrf`).

## Rate limiting

`security.SlidingWindowRateLimiter` is a small in-memory limiter applied to
admin login and image uploads. It is explicitly **pilot-grade**: it does
not survive a process restart and does not coordinate across multiple
worker processes. For anything beyond a small invited pilot, put a
reverse-proxy-level rate limit in front of this (see
`docs/portal-deployment.md`).
