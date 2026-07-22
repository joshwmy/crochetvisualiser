# Contributor workflow

## Getting an invitation

An administrator generates an invitation link:

```bash
python -m crochet_reconstruction.cli portal-create-invitation --label "Crochet friend"
```

This prints a link of the form `/invite/<token>` (a full URL once combined
with your deployed domain). The token is shown **once** — only its SHA-256
hash is stored, so it cannot be recovered if lost; generate a new
invitation instead. By default an invitation is single-use and expires in
30 days (`--max-uses`, `--expiry-days` to change).

## Step by step

1. **Open the link.** The intro page explains, in plain language: this is a
   research/product-development pilot, incomplete submissions are still
   useful, only submit photos you own or have permission to use, consent
   can be withdrawn, and images are private by default.
2. **Give a nickname** (not a real name) and, optionally, an email address
   (only used if the project needs to ask about missing details — this
   collection can be disabled entirely via
   `PORTAL_CONTACT_EMAIL_COLLECTION_ENABLED=false`).
3. **Consent.** Six independent checkboxes plus the required privacy-notice
   acceptance and ownership confirmation. A contributor can, for example,
   allow research/product use while refusing model training and public
   display — these are genuinely independent, not one blanket checkbox.
4. **Project details.** Category (beanie / stitch swatch / other), craft
   type, construction direction, worked in rows/rounds, continuous/joined,
   known stitch families, notes. Every uncertain field has an explicit
   "Unknown" option — nothing is inferred or guessed.
5. **Materials, gauge, measurements.** All optional. Blank means unknown;
   it is never filled in with a guess.
6. **Photos.** Required and recommended photo types are listed with a
   plain-language description of what each one should show (see
   `routers/contributor._IMAGE_SLOTS`). Each photo is validated by its
   actual content (not its filename) before being accepted — see
   `docs/portal-image-storage.md`.
7. **Review and submit.** Shows exactly what will be submitted (own
   previews, own entered text) and any still-missing required items. A
   plain confirmation reference (e.g. `CR-7K2H-93MX`) is shown on success —
   never an internal database ID or a pattern fingerprint.

## Drafts and returning later

Every step saves as soon as it's submitted — a contributor can close the
tab and come back to the same invitation link later; if they still hold
the browser session (same device/browser, cookie not cleared), they land
on **"Your projects"** with a **Continue** link for anything still in
`draft` or `changes_requested`. There is no separate "resume" token by
design — the invitation-redemption session already grants this, and
building a second recovery mechanism would need its own security review
that's out of scope for this pilot. If a contributor loses their session
(new device, cleared cookies), a new invitation link lets them start a new
submission; recovering an old in-progress draft on a different device is a
known limitation (see `docs/portal-known-limitations.md`).

## Multiple projects

A single invitation link supports submitting more than one project — the
"Start another project" button on the project list creates a new draft
under the same contributor identity.

## What a contributor never sees

Internal database IDs, pattern fingerprints, raw JSON, validation stack
traces, or any other contributor's data. Every error message shown is
plain language (see `routers/contributor._humanize_errors`).
