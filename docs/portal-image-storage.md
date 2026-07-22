# Image storage model

## Validation (content, not extension)

Every uploaded file is decoded with Pillow and checked before anything
else happens (`images.validate_and_process_image`):

1. Size limit (`PORTAL_MAX_UPLOAD_BYTES`, default 15 MB) checked on the raw
   bytes.
2. `Image.open(...).verify()` — rejects corrupt/truncated files.
3. Re-opened and `.load()`d to force full decode (catches issues `verify()`
   alone misses).
4. **Actual decoded format** checked against an allow-list (`JPEG`, `PNG`,
   `WEBP`) — a renamed `.gif` or any other format is rejected regardless of
   its filename or declared content-type.
5. Minimum dimension check (`PORTAL_MIN_IMAGE_DIMENSION_PX`, default 400px
   on the shorter side).
6. EXIF orientation is baked into the pixel data
   (`ImageOps.exif_transpose`), then **all metadata is stripped** by
   rebuilding a pixel-only copy (`Image.new` + `putdata`) — no EXIF, no
   GPS, no ICC profile survives into the stored copy, for both the
   original and the preview. This is a deliberately more privacy-protective
   default than "keep originals as uploaded" — see the module docstring in
   `images.py` for the tradeoff.
7. SHA-256 computed over the **cleaned** (post-strip) bytes, so files that
   are pixel-identical but differ only in metadata are still detected as
   duplicates.
8. A normalised JPEG preview (max 1600px on the long side) is generated for
   the admin gallery.

## Filenames

- The contributor's original filename is **sanitised for display/audit
  only** (`images.sanitize_original_filename` strips directory components
  and any character outside `[A-Za-z0-9._-]`) and is never used to build a
  filesystem path.
- The file actually written to disk always uses a fresh server-generated
  UUID4 + extension (`{uuid4().hex}.{ext}`).

## Storage layout

```
DATA_DIR/
├── originals/<submission_reference>/<uuid>.<ext>
├── previews/<submission_reference>/<uuid>.<ext>   (normalised JPEG)
├── exports/
├── backups/
└── quarantine/                                    (reserved, unused in Phase 1.5 —
                                                      no automatic quarantine flow
                                                      exists yet; created for the
                                                      directory-tree contract only)
```

`<submission_reference>` (e.g. `CR-7K2H-93MX`) is used as the per-project
directory name instead of the raw database ID, so directory names don't
leak how many projects exist or their creation order.

Every path segment (`storage.py`'s `_validate_key`) is checked against
`^[A-Za-z0-9_-]+$` before being joined onto a base directory — a value
like `"../../etc/passwd"` is rejected outright
(`UnsafeStorageKeyError`), not merely discouraged by convention. This is
tested directly (`tests/portal/test_storage.py`) with real path-traversal
strings.

## Duplicate detection

Exact (post-cleaning) duplicates are **flagged, not rejected** —
`ProjectImage.duplicate_of_image_id` points at the earliest matching image
(by SHA-256, across the whole database, not just the current project). An
administrator sees the flag and decides; the contributor is never blocked
from re-uploading the same photo for a different slot.

## Never used for training automatically

No code path in this repository trains, fine-tunes, or feeds uploaded
images into a model. `model_training_use` consent is recorded for future
use by a separate, explicitly-scoped process — this phase does not
implement that process.

## Storage abstraction

`storage.StorageBackend` is an ABC; `LocalFileStorage` is the only
implementation. Swapping in S3-compatible storage later means implementing
the same four read/write/delete methods — no route or service code would
need to change. Not implemented now, per the brief.
