# Consent, privacy, retention, and withdrawal

**None of this is legal advice.** It is a plain-language draft for a small
invited pilot. Flag it for review by qualified counsel before any broader
or public launch — this is stated explicitly, not assumed.

## Consent model

`ConsentRecord` is **1:1 with a `CrochetProject`**, not with a
`Contributor` — permissions are meaningfully per-submission (a contributor
could reasonably allow one project to be used for product testing and
refuse the same for another). Every permission is an independent boolean:

- `owns_photographs` (required — a submission cannot proceed without it)
- `privacy_notice_accepted` (required)
- `research_evaluation_use`
- `product_development_use`
- `model_training_use`
- `public_demonstration_use`
- `contact_for_missing_details`
- `attribution_preference` (anonymous / handle-or-first-name / full name)

Recorded alongside: `consent_version` (bumped whenever the question set or
notice text materially changes — old records keep their original version,
never silently reinterpreted), `consented_at`, the contributor-provided
identifier at the time of consent, and `withdrawn_at`.

**Refusing model training while allowing product testing is a normal,
fully-supported combination** — this was a hard requirement, not an
afterthought, and is enforced structurally (independent columns, not one
combined flag) rather than by convention.

## What data is collected

Photographs, project/construction details, materials/gauge/measurements
(all optional, `unknown` is real), a contributor-chosen nickname, and
optionally an email address (configurable — can be disabled entirely via
`PORTAL_CONTACT_EMAIL_COLLECTION_ENABLED=false`). No other personal
information is requested. EXIF location/metadata is stripped from every
stored image copy (see `docs/portal-image-storage.md`).

## Who can see submitted data

Nobody publicly by default. Only administrators (authenticated) can view
uploaded images or contributor-entered details. A project is only ever
shown publicly if `public_demonstration_use` was explicitly granted **and**
a human decides to use it that way — the portal itself never publishes
anything automatically.

## Withdrawal

A contributor can ask (by referencing their submission code) to withdraw
at any time; an administrator performs this via the "Withdraw" action
(`services.withdraw_project`), which is allowed from any non-withdrawn
status — this is treated as a standing privacy right, not a normal
review-workflow transition (see `state_machine.py`'s module docstring for
why it's modelled separately from the approve/reject state machine).
Withdrawal:

- Sets the project status to `withdrawn` and records `consent.withdrawn_at`.
- **Automatically excludes the project from every future dataset export**
  — export always re-queries current status; nothing needs to remember to
  exclude a withdrawn project (verified by
  `tests/portal/test_services.py::test_withdraw_excludes_from_export`).
- Does **not** delete files by itself — withdrawal and deletion are
  deliberately separate actions (a withdrawn-but-retained record can still
  answer "did this person submit something," which matters for auditability
  during a pilot; permanent deletion is a stronger, separate action).

## Administrative deletion

"Delete data permanently" (`services.delete_project_data`) hard-deletes:

- All uploaded image files (originals and previews) from disk.
- All `ProjectImage` database rows.
- Free-text fields (`name_or_description`, `component_notes`,
  `free_text_notes`) and the consent record's `attribution_text`.

It **retains** a minimal tombstone: the project row (reference, status,
timestamps) and the full audit trail. This is a deliberate choice — when
deletion conflicts with wanting to prove *that* a deletion happened
(itself a reasonable auditability requirement), retain only the minimum
non-image record needed to show the deletion occurred, never the deleted
content itself.

## Retention

Data is retained for as long as the pilot is active unless withdrawn or
deleted sooner. There is no automatic time-based expiry in this phase —
that would need a policy decision (how long is appropriate?) that hasn't
been made, so it is not silently invented here.

## No public image URLs

Every image is served through an authenticated route
(`/admin/projects/{ref}/images/{id}/preview` for admins;
`/contributor/project/{ref}/images/{id}/preview` for the owning
contributor only). There is no static file mount, no signed-URL-with-long-
expiry pattern, and no other way to reach an uploaded image.
