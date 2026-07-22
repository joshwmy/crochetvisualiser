# Administrator workflow

## Creating an account

```bash
python -m crochet_reconstruction.cli portal-create-admin --username reviewer1
```

Prompts for a password (hidden input; minimum 12 characters) if
`--password` and `PORTAL_ADMIN_PASSWORD` are both unset. Multiple admin
accounts are supported — there is no single shared login.

## Signing in

`/admin/login` — username/password, CSRF-protected, rate-limited
(`PORTAL_RATE_LIMIT_MAX_ATTEMPTS` per `PORTAL_RATE_LIMIT_WINDOW_SECONDS`,
per source IP). Sessions last `PORTAL_SESSION_MAX_AGE_SECONDS` (default 8
hours).

## Reviewing a submission

1. **`/admin/pending`** lists every project in `submitted` or
   `under_review` status.
2. Open a project's detail page. Contributor-provided values (project
   details, materials, gauge, measurements, consent) are shown clearly
   separated from **reviewer-confirmed values** (verified craft type,
   category, stitch labels — populated only once a reviewer sets them).
   Nothing here ever overwrites the contributor's original answer.
3. **Private image gallery**: every photo is served through
   `/admin/projects/{ref}/images/{id}/preview`, which requires an
   authenticated admin session — there is no other path to an uploaded
   image anywhere in the app (no static file serving, no public URL).
4. **Start review** moves `submitted` → `under_review`.
5. **Record a decision**: Approve / Request changes / Reject / Note-only.
   - *Approve* moves the project to `approved` and snapshots the
     consent-derived allowed uses onto the decision record.
   - *Request changes* moves it to `changes_requested`, unlocking it for
     the contributor to edit and resubmit.
   - *Reject* is terminal for this submission.
   - *Note* records verified labels or comments **without** changing
     status — use this to correct/add verified stitch labels after
     approval without re-running the approve action.
6. **Physical-trial link**: enter a `trial_id` and `pattern_fingerprint`;
   the portal validates both against the live deterministic engine
   (`physical_validation.trial_matrix`) before accepting the link — a
   stale or made-up fingerprint is rejected, not silently stored.
7. **Withdraw** — sets the project (and its consent record) to withdrawn.
   Files are *not* deleted — see "Delete data permanently" for that.
8. **Delete data permanently** — hard-deletes uploaded images and
   free-text fields, keeping only a minimal tombstone (reference, status,
   audit trail) so the audit log can still prove a deletion happened. This
   is irreversible; the confirmation dialog says so.
9. **Audit history** — every action on this project, actor, and timestamp.
   Never contains image content.

## Exporting the approved dataset

`/admin/export` (or `portal-export-approved` from the CLI — see
`docs/portal-dataset-export.md`) writes every currently-approved,
non-withdrawn, consented-for-research-or-product-use project to a JSON
index plus copied preview images. Nothing else ever writes to the dataset
index — it is always regenerated from current approval state, never
hand-edited.
