"""File storage abstraction.

`StorageBackend` is deliberately narrow (save/read/delete by opaque key) so
an S3-compatible backend can implement the same interface later without
any route or service code changing. Only `LocalFileStorage` is implemented
now, per the brief's "do not implement cloud storage unless necessary."

Keys are always `(project_storage_key, stored_filename)` pairs —
`project_storage_key` is a project's `submission_reference` (opaque,
non-sequential), never its raw database ID, so directory names don't leak
how many projects exist or their creation order. `stored_filename` is
always a server-generated UUID + extension; nothing derived from a
contributor-supplied filename ever reaches the filesystem.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

_SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class UnsafeStorageKeyError(ValueError):
    """Raised when a storage key does not match the safe-character pattern.

    This is the path-traversal guard: every key is validated before being
    joined onto a base directory, so a value like ``"../../etc/passwd"``
    is rejected outright rather than relying on callers behaving.
    """


def _validate_key(key: str) -> None:
    if not _SAFE_KEY_PATTERN.match(key):
        raise UnsafeStorageKeyError(f"unsafe storage key: {key!r}")


class StorageBackend(ABC):
    @abstractmethod
    def save_original(self, project_key: str, stored_filename: str, data: bytes) -> None: ...

    @abstractmethod
    def save_preview(self, project_key: str, stored_filename: str, data: bytes) -> None: ...

    @abstractmethod
    def read_original(self, project_key: str, stored_filename: str) -> bytes: ...

    @abstractmethod
    def read_preview(self, project_key: str, stored_filename: str) -> bytes: ...

    @abstractmethod
    def delete_project_files(self, project_key: str) -> None: ...

    @abstractmethod
    def write_export(self, filename: str, data: bytes) -> Path: ...

    @abstractmethod
    def write_backup(self, filename: str, data: bytes) -> Path: ...


class LocalFileStorage(StorageBackend):
    """Stores files under ``DATA_DIR/{originals,previews,exports,backups}``.

    Never returns a path to a route handler for inclusion in an HTTP
    response — routes get bytes back and stream them, so no raw filesystem
    path is ever exposed to a client.
    """

    def __init__(
        self, originals_dir: Path, previews_dir: Path, exports_dir: Path, backups_dir: Path
    ) -> None:
        self._originals_dir = originals_dir
        self._previews_dir = previews_dir
        self._exports_dir = exports_dir
        self._backups_dir = backups_dir

    def _project_dir(self, base: Path, project_key: str) -> Path:
        _validate_key(project_key)
        directory = base / project_key
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save_original(self, project_key: str, stored_filename: str, data: bytes) -> None:
        _validate_key(stored_filename.split(".")[0])
        path = self._project_dir(self._originals_dir, project_key) / stored_filename
        path.write_bytes(data)

    def save_preview(self, project_key: str, stored_filename: str, data: bytes) -> None:
        _validate_key(stored_filename.split(".")[0])
        path = self._project_dir(self._previews_dir, project_key) / stored_filename
        path.write_bytes(data)

    def read_original(self, project_key: str, stored_filename: str) -> bytes:
        _validate_key(project_key)
        _validate_key(stored_filename.split(".")[0])
        path = self._originals_dir / project_key / stored_filename
        return path.read_bytes()

    def read_preview(self, project_key: str, stored_filename: str) -> bytes:
        _validate_key(project_key)
        _validate_key(stored_filename.split(".")[0])
        path = self._previews_dir / project_key / stored_filename
        return path.read_bytes()

    def delete_project_files(self, project_key: str) -> None:
        _validate_key(project_key)
        for base in (self._originals_dir, self._previews_dir):
            directory = base / project_key
            if directory.is_dir():
                for child in directory.iterdir():
                    child.unlink(missing_ok=True)
                directory.rmdir()

    def write_export(self, filename: str, data: bytes) -> Path:
        _validate_key(filename.split(".")[0])
        path = self._exports_dir / filename
        path.write_bytes(data)
        return path

    def write_backup(self, filename: str, data: bytes) -> Path:
        _validate_key(filename.split(".")[0])
        path = self._backups_dir / filename
        path.write_bytes(data)
        return path
