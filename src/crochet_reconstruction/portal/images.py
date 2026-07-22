"""Image content validation and processing.

Every check here operates on *decoded pixel data*, not the file extension
or declared content-type — a `.jpg` file that Pillow cannot decode as an
image is rejected regardless of what the browser claimed it was.

Privacy default: both the stored original and the generated preview have
EXIF metadata stripped and orientation baked into the pixel data. The
brief allows keeping raw originals "when there is a documented reason" —
the default here is the more privacy-protective one (strip always);
switching to retaining raw EXIF-bearing originals would need its own
documented justification (e.g. a dispute-resolution requirement) and is
not implemented.
"""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from dataclasses import dataclass

from PIL import Image, ImageOps

ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

_FORMAT_TO_EXTENSION = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

_PREVIEW_MAX_DIMENSION = 1600
_PREVIEW_JPEG_QUALITY = 85
_ORIGINAL_JPEG_QUALITY = 92

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class ImageValidationError(ValueError):
    """Raised for any image that fails validation. The message is safe to
    show to a contributor (no internal paths, no stack details)."""


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    stored_filename: str
    original_bytes: bytes
    preview_bytes: bytes
    width: int
    height: int
    image_format: str
    byte_size: int
    sha256: str


def sanitize_original_filename(name: str) -> str:
    """For display/audit only — never used to build a filesystem path."""
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", base).lstrip(".")
    return cleaned[:200] or "unnamed"


def _strip_metadata(image: Image.Image) -> Image.Image:
    """Return a pixel-only copy with no EXIF/ICC/GPS info attached."""
    clean = Image.new(image.mode, image.size)
    clean.putdata(list(image.getdata()))
    return clean


def validate_and_process_image(
    raw_bytes: bytes,
    *,
    max_upload_bytes: int,
    min_dimension_px: int,
) -> ProcessedImage:
    if len(raw_bytes) == 0:
        raise ImageValidationError("uploaded file is empty")
    if len(raw_bytes) > max_upload_bytes:
        raise ImageValidationError(
            f"file is too large ({len(raw_bytes)} bytes; maximum is {max_upload_bytes} bytes)"
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            probe.verify()
    except Exception as exc:  # Pillow raises many different exception types here
        raise ImageValidationError("file is not a valid, readable image") from exc

    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()  # type: ignore[no-untyped-call]  # Pillow's stub omits this signature
    except Exception as exc:
        raise ImageValidationError("file is not a valid, readable image") from exc

    image_format = image.format
    if image_format not in ALLOWED_FORMATS:
        raise ImageValidationError(
            f"unsupported image format {image_format!r}; allowed: "
            f"{', '.join(sorted(ALLOWED_FORMATS))}"
        )

    width, height = image.size
    if min(width, height) < min_dimension_px:
        raise ImageValidationError(
            f"image is too small ({width}x{height}px; minimum dimension is {min_dimension_px}px)"
        )

    oriented = ImageOps.exif_transpose(image) or image
    if oriented.mode not in ("RGB", "L"):
        oriented = oriented.convert("RGB")
    clean = _strip_metadata(oriented)

    original_buffer = io.BytesIO()
    save_kwargs = {"quality": _ORIGINAL_JPEG_QUALITY} if image_format == "JPEG" else {}
    clean.save(original_buffer, format=image_format, **save_kwargs)
    original_bytes = original_buffer.getvalue()

    preview_image = clean.copy()
    preview_image.thumbnail((_PREVIEW_MAX_DIMENSION, _PREVIEW_MAX_DIMENSION))
    preview_buffer = io.BytesIO()
    if preview_image.mode != "RGB":
        preview_image = preview_image.convert("RGB")
    preview_image.save(preview_buffer, format="JPEG", quality=_PREVIEW_JPEG_QUALITY)
    preview_bytes = preview_buffer.getvalue()

    sha256 = hashlib.sha256(original_bytes).hexdigest()
    extension = _FORMAT_TO_EXTENSION[image_format]
    stored_filename = f"{uuid.uuid4().hex}.{extension}"

    return ProcessedImage(
        stored_filename=stored_filename,
        original_bytes=original_bytes,
        preview_bytes=preview_bytes,
        width=clean.size[0],
        height=clean.size[1],
        image_format=image_format,
        byte_size=len(original_bytes),
        sha256=sha256,
    )
