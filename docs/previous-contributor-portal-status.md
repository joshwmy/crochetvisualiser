# Contributor portal: status after the pivot

## What happened

The project's primary goal changed from "reconstruct a pattern from photos
of a finished object" to "visualise a supplied pattern in interactive 3D."
The contributor submission portal (`src/crochet_reconstruction/portal/`,
`alembic/`, `Dockerfile`, `docker-compose.yml`, `docs/portal-*.md`,
`tests/portal/`) existed to collect a labelled photo dataset for the
*previous* direction's eventual image-recognition work. That work is no
longer the current priority (see `docs/product-boundary.md` and the
project-pivot note in the main `README.md`).

## What was done with it

**Nothing was deleted.** Per explicit instruction, the portal is preserved:

- The full pre-pivot state (portal, physical-validation tooling, engine —
  everything) was committed to the `main` branch (commit `09ebf5c`,
  "Preserve crochet reconstruction prototype before scientific 3D
  visualizer pivot") before any pivot work began.
- All pivot work happens on the `pattern-to-scientific-3d-visualizer`
  branch. `main` remains a complete, working snapshot of the portal-era
  state, recoverable at any time (`git checkout main`).
- No portal file was modified, renamed, or removed during the pivot. The
  portal's own test suite (`tests/portal/`, ~100 tests) still passes
  unchanged — it was not touched, only left alone.
- The portal's dependencies (FastAPI, SQLAlchemy, Alembic, Pillow,
  itsdangerous) remain behind the `portal` extra in `pyproject.toml` and
  are **not** imported by anything in the new `graph`/`geometry` packages
  or the `viewer/` — the two efforts remain cleanly separated, exactly as
  they were designed to be before the pivot (see `docs/portal-architecture.md`,
  "the deterministic pattern engine has zero dependency on this").

## Reusability if the portal is revisited later

The brief noted authentication, project persistence, database models,
upload handling, and administrative tooling "may be reusable later." That
remains true and unchanged — nothing about the graph/geometry/viewer work
in this pivot precludes resuming the portal, migrating it, or repurposing
its consent/review/storage infrastructure for a future
"upload your finished object photo for reference" feature, should that
become relevant again. It is paused, not abandoned.

## If you need the portal today

```bash
git log --oneline main | grep -i portal   # portal-era commit history
git show main:docs/portal-architecture.md # read portal docs from that commit
```

Or simply check out `main` in a separate worktree — the portal's own
`docs/portal-deployment.md` instructions are unchanged and still accurate
for that branch.
