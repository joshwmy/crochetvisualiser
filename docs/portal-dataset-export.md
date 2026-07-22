# Dataset export

## What qualifies

`services.export_approved_projects` includes a project only if **all** of:

- `status == approved` (a `submitted`, `under_review`, `changes_requested`,
  `rejected`, or `withdrawn` project is never included).
- Its consent record is not withdrawn (`consent.withdrawn_at is None`) —
  belt-and-suspenders alongside the status check, since withdrawal always
  moves status away from `approved` anyway.
- At least one of `research_evaluation_use` or `product_development_use`
  was granted. A project consented only for, say, public demonstration
  (with both of those refused) is excluded from this experiment-dataset
  export — this export is specifically for research/product-development
  use, not a general "everything approved" dump.

**The dataset index is always regenerated from current approval state.**
Nothing in this codebase manually edits or appends to it — running the
export again after a withdrawal simply produces a smaller index, with no
special-case code needed to "remember" the exclusion.

## Running it

```bash
# CLI (recommended for scripted/scheduled use):
python -m crochet_reconstruction.cli portal-export-approved --output build/approved_dataset/

# Or from the admin UI: /admin/export
```

## Output shape

```
<output>/
├── approved_dataset.json
└── images/
    └── <submission_reference>/
        └── <image_type>_<uuid>.jpg   (preview copies only — never raw originals)
```

`approved_dataset.json` — one record per project:

```json
{
  "records": [
    {
      "object_id": "CR-7K2H-93MX",
      "craft_type": "crochet",
      "project_category": "beanie",
      "verified_stitch_labels": ["sc"],
      "allowed_uses": {
        "research_evaluation_use": true,
        "product_development_use": true,
        "model_training_use": false,
        "public_demonstration_use": false
      },
      "data_quality_status": "ok",
      "consent_version": "1.0",
      "attribution_preference": "anonymous",
      "attribution_text": null,
      "split": null,
      "images": [
        {"image_type": "front", "preview_filename": "...", "width": 1600, "height": 1600, "format": "JPEG", "sha256": "...", "is_duplicate": false}
      ],
      "trial_links": [
        {"trial_id": "BV-001", "pattern_fingerprint": "...", "physical_result_id": null, "validated": true}
      ]
    }
  ]
}
```

`object_id` deliberately matches the grouping-key convention in
`experiments/crochet_vs_knitting/dataset-schema.json` (`object_id` /
`split`), so a future dataset-splitting or annotation pipeline can treat
portal exports and any other collected images with one consistent
convention: **every image sharing an `object_id` must stay in the same
split** — never split individual views of the same physical item across
train/val/test.

## Project-level splitting

`"split": null` for every record in this phase — deliberately left blank
until there is enough approved data for a meaningful split, per the
brief's explicit instruction ("the first version may leave split
assignment blank"). When implemented, the split assignment must be made
**once per `object_id`**, never per image — see
`experiments/crochet_vs_knitting/split-policy.md` for the policy this
export is designed to be compatible with.

## Verified vs. contributor-provided values in the export

`craft_type` / `project_category` in the export come from the **latest
approval decision's verified value if one was recorded**, falling back to
the contributor's original value only if no reviewer verification exists.
This is the one place the export prefers a reviewer's judgement over the
contributor's raw answer — appropriate here because the export is
specifically feeding a labelled dataset, where a reviewer-confirmed label
is more valuable than an unverified contributor guess. The contributor's
original values are never lost — they remain on the `CrochetProject`
row in the database, untouched.
