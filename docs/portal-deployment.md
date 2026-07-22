# Deployment, backup/restore, and production checklist

## Local development

```bash
pip install -e ".[dev,portal]"
cp .env.example .env               # fill in PORTAL_SECRET_KEY at minimum
export $(cat .env | xargs)         # or use your process manager's env loading
alembic upgrade head
python -m crochet_reconstruction.cli portal-create-admin --username admin
python -m crochet_reconstruction.cli portal-create-invitation --label "First tester"
uvicorn crochet_reconstruction.portal.app:create_app --factory --reload
```

Visit `http://127.0.0.1:8000/invite/<token>` and `http://127.0.0.1:8000/admin/login`.

## Migrations

```bash
alembic upgrade head          # apply all pending migrations
alembic revision --autogenerate -m "description"   # after changing models.py
```

The database URL always comes from `PORTAL_DATABASE_URL` /
`PORTAL_DATA_DIR` (see `alembic/env.py`) — never hardcode a URL in
`alembic.ini`.

## Docker

```bash
docker build -t crochet-portal .
docker run -d \
  --name crochet-portal \
  -p 8000:8000 \
  -v crochet_portal_data:/data \
  --env-file .env \
  -e PORTAL_ENVIRONMENT=production \
  crochet-portal
```

The container's `CMD` runs `alembic upgrade head` before starting
`uvicorn`, so migrations are always applied on startup. The image runs as a
non-root user (`portal`, uid 1000); `/data` is the only writable directory.

**`/data` must be a persistent volume.** Most container hosting platforms
give you ephemeral local disk by default — if you deploy somewhere that
doesn't mount a real persistent volume at `/data`, **every image and the
entire SQLite database is lost on redeploy/restart.** This is stated
explicitly because it is the single most consequential misconfiguration
possible for this app.

`docker-compose.yml` is provided for local production-like testing (one
service, one named volume — no second database container, since SQLite is
a file on the same volume).

## Reverse proxy / HTTPS

Run behind a reverse proxy (nginx, Caddy, or your platform's built-in one)
that terminates TLS and forwards to port 8000. The app sets
`Strict-Transport-Security` only when `PORTAL_ENVIRONMENT=production`, and
sets the session cookie `Secure` flag from the same setting
(`https_only=settings.is_production` in `app.py`) — do not set
`PORTAL_ENVIRONMENT=production` without HTTPS actually in front of it, or
the browser will refuse to send the session cookie back.

## First-admin setup

```bash
python -m crochet_reconstruction.cli portal-create-admin --username <name>
```

Prompts for a password (hidden, ≥12 characters) if not supplied via
`--password` or `PORTAL_ADMIN_PASSWORD`. Run this once per admin account
needed; there is no self-service admin registration.

## Invitation generation

```bash
python -m crochet_reconstruction.cli portal-create-invitation \
  --label "Descriptive note for your own records" \
  --expiry-days 30 \
  --max-uses 1
```

The printed link/token is shown once. Revoking an invitation is currently
a service-layer operation (`services.revoke_invitation`) without its own
CLI subcommand — a known limitation for this phase (see
`docs/portal-known-limitations.md`); revoke via a short Python shell
against the same database if needed before adding a dedicated command.

## Backup and restore

```bash
python -m crochet_reconstruction.cli portal-backup --output backups/
```

Writes a timestamped `.zip` of the **entire `PORTAL_DATA_DIR`** (database +
all originals/previews) to the given output directory. This is a simple
file-level backup, not a live/hot database backup — for a busy production
system you would want SQLite's own backup API or point-in-time snapshots
instead; for a small pilot, stopping writes briefly (or accepting a small
inconsistency window) and zipping the directory is an acceptable tradeoff,
documented here rather than assumed safe.

**Restore**: stop the app, replace the contents of `PORTAL_DATA_DIR` with
the unzipped backup contents, restart. There is no automated restore
command in this phase — this is a manual, infrequent operation for a small
pilot and did not warrant its own CLI surface yet.

Schedule `portal-backup` via cron/your platform's scheduler; it is not
run automatically by the app itself.

## Production configuration checklist

- [ ] `PORTAL_ENVIRONMENT=production`
- [ ] `PORTAL_SECRET_KEY` set to a real generated value (not the dev
      auto-generated ephemeral one — the app refuses to start in
      production without this set)
- [ ] `PORTAL_DATA_DIR` points at a genuinely persistent volume — verified
      by actually restarting the container and confirming data survives
- [ ] HTTPS terminated in front of the app (reverse proxy)
- [ ] At least one admin account created; its password recorded somewhere
      safe (there is no password-reset flow in this phase — see known
      limitations)
- [ ] `.env` is not committed to version control (`.gitignore` already
      excludes it)
- [ ] A backup has been taken and a restore has been rehearsed at least
      once before relying on this in a real pilot
- [ ] Privacy notice and consent copy reviewed by whoever is legally
      responsible for this pilot (see `docs/portal-consent-and-privacy.md`)
- [ ] Dependency versions pinned (see `pyproject.toml`'s `portal` extra —
      upper-bounded ranges, not unpinned floats)
