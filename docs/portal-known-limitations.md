# Known limitations

Honest accounting of what this phase deliberately does not do, and what is
weaker than a larger production system would need. None of these are
hidden — each was a conscious scope decision for "small, controlled pilot"
per the brief, not an oversight discovered too late.

## Scale and infrastructure

- **SQLite**, not a client-server database. Fine for a small pilot with a
  handful of concurrent admins and contributors; not appropriate for
  meaningful concurrent write load. Migrating to PostgreSQL later means
  changing `PORTAL_DATABASE_URL` and re-running Alembic migrations against
  the new database — the ORM layer doesn't otherwise assume SQLite, but
  this has not been tested against Postgres.
- **In-memory rate limiting** (`security.SlidingWindowRateLimiter`). Does
  not survive a process restart and does not coordinate across multiple
  worker processes/replicas. A single-process deployment (as documented)
  is fine; a multi-replica deployment needs a shared store (Redis or
  similar) instead — not added here since the brief asks not to add Redis
  without strict justification, and a single pilot instance doesn't need
  it yet.
- **No background job queue.** Image processing happens synchronously
  during the upload request. Fine at pilot scale (images are modest,
  processing is fast); would need offloading to a queue if upload volume
  or image size grew substantially.

## Authentication and account management

- **PBKDF2, not bcrypt/argon2**, for password hashing — deliberate
  tradeoff to avoid a new dependency for a small admin pool (see
  `docs/portal-architecture.md`).
- **No password-reset flow.** An admin who forgets their password needs
  another admin (or direct database access) to help; there is no
  self-service "forgot password" email flow.
- **No invitation-revocation CLI command.** `services.revoke_invitation`
  exists and is tested, but is not yet exposed as its own
  `portal-revoke-invitation` subcommand — use a short Python shell against
  the database in the meantime (see `docs/portal-deployment.md`).
- **No 2FA.** A single password is the only admin authentication factor.

## Contributor experience

- **No cross-device draft recovery.** A contributor's in-progress
  submission lives in a browser session tied to the invitation redemption;
  losing that session (new device, cleared cookies) means starting over
  with a new invitation link. A magic-link-style recoverable draft token
  was considered and deliberately deferred — it needs its own security
  review (token scope, expiry, replay protection) that didn't fit this
  phase's scope.
- **No image-upload progress bar** beyond the browser's native per-request
  behaviour — uploads are one file per form submission, so "in progress"
  is just the page waiting on that single request. Fine for the modest
  file sizes involved; would need real client-side chunked-upload UI for
  much larger files.

## Review and dataset tooling

- **No bulk review actions** — one project reviewed at a time.
- **No project-level dataset splitting yet** (`"split": null` in every
  export record) — deliberately deferred until there's enough approved
  data for a meaningful split (see `docs/portal-dataset-export.md`).
- **No automated retention/expiry policy** — data is kept until explicitly
  withdrawn or deleted; there is no scheduled auto-deletion after N days.

## Security posture

- Every control listed in `docs/portal-architecture.md` and the original
  brief (CSRF, rate limiting, password hashing, private image serving,
  path-traversal guards, dependency pinning, non-root container) has been
  implemented and tested — but **implementing these controls does not
  constitute a completed security review.** No penetration test, dependency
  vulnerability scan, or professional security audit has been performed on
  this code. Recommended before any launch beyond a small, trusted, invited
  pilot.
- The privacy notice and consent language are explicitly **not legal
  advice** and have not been reviewed by counsel (flagged in
  `docs/portal-consent-and-privacy.md` and directly in the rendered privacy
  page itself).

## What was intentionally not built (per the brief's scope exclusions)

Public registration, social login, payments, a marketplace, any AI image
classification or stitch recognition, model training, 3D rendering,
automatic pattern generation from photos, public contributor profiles or
image galleries, complex roles/organisation management, microservices,
Kubernetes, and a separate React frontend. None of these were partially
started and abandoned — they were never begun, per explicit instruction.
