import pytest

from crochet_reconstruction.portal.storage import LocalFileStorage, UnsafeStorageKeyError


def test_save_and_read_original_round_trip(storage: LocalFileStorage) -> None:
    storage.save_original("CR-AAAA-BBBB", "abc123.jpg", b"fake-image-bytes")
    assert storage.read_original("CR-AAAA-BBBB", "abc123.jpg") == b"fake-image-bytes"


def test_save_and_read_preview_round_trip(storage: LocalFileStorage) -> None:
    storage.save_preview("CR-AAAA-BBBB", "abc123.jpg", b"fake-preview-bytes")
    assert storage.read_preview("CR-AAAA-BBBB", "abc123.jpg") == b"fake-preview-bytes"


def test_delete_project_files_removes_originals_and_previews(storage: LocalFileStorage) -> None:
    storage.save_original("CR-AAAA-BBBB", "abc123.jpg", b"x")
    storage.save_preview("CR-AAAA-BBBB", "abc123.jpg", b"y")
    storage.delete_project_files("CR-AAAA-BBBB")
    with pytest.raises(FileNotFoundError):
        storage.read_original("CR-AAAA-BBBB", "abc123.jpg")


@pytest.mark.parametrize(
    "malicious_key",
    [
        "../../etc/passwd",
        "..\\..\\windows",
        "/etc/passwd",
        "a/b",
        "a\\b",
        "",
    ],
)
def test_path_traversal_project_keys_are_rejected(
    storage: LocalFileStorage, malicious_key: str
) -> None:
    with pytest.raises(UnsafeStorageKeyError):
        storage.save_original(malicious_key, "abc123.jpg", b"x")


@pytest.mark.parametrize("malicious_filename", ["../evil.jpg", "a/b.jpg", "a\\b.jpg"])
def test_path_traversal_filenames_are_rejected(
    storage: LocalFileStorage, malicious_filename: str
) -> None:
    with pytest.raises(UnsafeStorageKeyError):
        storage.save_original("CR-AAAA-BBBB", malicious_filename, b"x")


def test_write_export_and_backup(storage: LocalFileStorage) -> None:
    export_path = storage.write_export("dataset.json", b'{"records": []}')
    assert export_path.read_bytes() == b'{"records": []}'

    backup_path = storage.write_backup("backup.zip", b"zip-bytes")
    assert backup_path.read_bytes() == b"zip-bytes"
