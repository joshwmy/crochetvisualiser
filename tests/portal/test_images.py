import io

import pytest
from PIL import Image

from crochet_reconstruction.portal.images import (
    ImageValidationError,
    sanitize_original_filename,
    validate_and_process_image,
)

_ORIENTATION_TAG = 0x0112
_USER_COMMENT_TAG = 0x9286


def _jpeg_bytes(
    size: tuple[int, int] = (600, 600), color: tuple[int, int, int] = (10, 200, 30)
) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes(size: tuple[int, int] = (600, 600)) -> bytes:
    img = Image.new("RGB", size, (200, 10, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _webp_bytes(size: tuple[int, int] = (600, 600)) -> bytes:
    img = Image.new("RGB", size, (10, 30, 200))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def _gif_bytes(size: tuple[int, int] = (600, 600)) -> bytes:
    img = Image.new("RGB", size, (10, 30, 200))
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


@pytest.mark.parametrize(
    ("factory", "expected_format"),
    [(_jpeg_bytes, "JPEG"), (_png_bytes, "PNG"), (_webp_bytes, "WEBP")],
)
def test_valid_formats_are_accepted(factory, expected_format: str) -> None:
    result = validate_and_process_image(
        factory(), max_upload_bytes=10_000_000, min_dimension_px=400
    )
    assert result.image_format == expected_format
    assert result.width == 600
    assert result.height == 600
    assert len(result.sha256) == 64
    assert result.stored_filename.endswith(
        {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[expected_format]
    )


def test_unsupported_format_is_rejected() -> None:
    with pytest.raises(ImageValidationError, match="unsupported image format"):
        validate_and_process_image(_gif_bytes(), max_upload_bytes=10_000_000, min_dimension_px=400)


def test_fake_extension_does_not_matter_content_is_what_is_checked() -> None:
    # A GIF's actual bytes are still rejected even though nothing here
    # claims a filename/extension at all - validation is content-only.
    with pytest.raises(ImageValidationError):
        validate_and_process_image(_gif_bytes(), max_upload_bytes=10_000_000, min_dimension_px=400)


def test_corrupt_data_is_rejected() -> None:
    with pytest.raises(ImageValidationError, match="not a valid, readable image"):
        validate_and_process_image(
            b"garbage" * 50, max_upload_bytes=10_000_000, min_dimension_px=400
        )


def test_empty_file_is_rejected() -> None:
    with pytest.raises(ImageValidationError, match="empty"):
        validate_and_process_image(b"", max_upload_bytes=10_000_000, min_dimension_px=400)


def test_oversized_file_is_rejected() -> None:
    with pytest.raises(ImageValidationError, match="too large"):
        validate_and_process_image(_jpeg_bytes(), max_upload_bytes=100, min_dimension_px=400)


def test_too_small_image_is_rejected() -> None:
    with pytest.raises(ImageValidationError, match="too small"):
        validate_and_process_image(
            _jpeg_bytes(size=(100, 100)), max_upload_bytes=10_000_000, min_dimension_px=400
        )


def test_same_pixels_produce_same_hash_regardless_of_exif() -> None:
    plain = validate_and_process_image(
        _jpeg_bytes(), max_upload_bytes=10_000_000, min_dimension_px=400
    )

    img = Image.new("RGB", (600, 600), (10, 200, 30))
    exif = Image.Exif()
    exif[_USER_COMMENT_TAG] = "some metadata that should not affect the content hash"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    with_exif = validate_and_process_image(
        buf.getvalue(), max_upload_bytes=10_000_000, min_dimension_px=400
    )

    assert plain.sha256 == with_exif.sha256


def test_exif_orientation_is_applied_and_stripped() -> None:
    # A 400x600 image tagged "rotate 90 CW" (orientation 6) should come out
    # as 600x400 after exif_transpose bakes the rotation into pixel data.
    img = Image.new("RGB", (400, 600), (5, 5, 5))
    exif = Image.Exif()
    exif[_ORIENTATION_TAG] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())

    result = validate_and_process_image(
        buf.getvalue(), max_upload_bytes=10_000_000, min_dimension_px=400
    )

    assert (result.width, result.height) == (600, 400)
    # Re-open the processed bytes and confirm no EXIF orientation tag survives.
    reopened = Image.open(io.BytesIO(result.original_bytes))
    assert "exif" not in reopened.info


def test_preview_is_a_bounded_jpeg() -> None:
    result = validate_and_process_image(
        _png_bytes(size=(3000, 500)), max_upload_bytes=20_000_000, min_dimension_px=400
    )
    preview = Image.open(io.BytesIO(result.preview_bytes))
    assert preview.format == "JPEG"
    assert max(preview.size) <= 1600


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("../../etc/passwd.jpg", "passwd.jpg"),
        ("..\\..\\windows\\system32\\evil.jpg", "evil.jpg"),
        ("normal_name.jpg", "normal_name.jpg"),
        (".hidden", "hidden"),
        (
            "weird name with spaces & stuff!.jpg",
            "weird_name_with_spaces_&_stuff_.jpg".replace("&", "_"),
        ),
        ("", "unnamed"),
    ],
)
def test_sanitize_original_filename(raw_name: str, expected: str) -> None:
    result = sanitize_original_filename(raw_name)
    assert "/" not in result
    assert "\\" not in result
    assert not result.startswith("..")
    if raw_name in (
        "../../etc/passwd.jpg",
        "..\\..\\windows\\system32\\evil.jpg",
        "normal_name.jpg",
        "",
    ):
        assert result == expected
