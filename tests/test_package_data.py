"""Every non-Python file in the package must be declared as package data.

setuptools ships only ``.py`` files unless told otherwise, and an editable
install (the normal dev and test setup) reads straight from ``src/`` — so a
missing declaration passes every other test and only breaks in a built wheel
or Docker image. That is how ``grammar.lark`` once went missing from the API
image: every written-pattern compile there failed with FileNotFoundError.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
PACKAGE_ROOT = SRC / "crochet_reconstruction"


def _declared_package_data() -> set[Path]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data: dict[str, list[str]] = pyproject["tool"]["setuptools"]["package-data"]
    declared: set[Path] = set()
    for package, patterns in package_data.items():
        package_dir = SRC.joinpath(*package.split("."))
        for pattern in patterns:
            declared.update(p for p in package_dir.glob(pattern) if p.is_file())
    return declared


def _non_python_package_files() -> set[Path]:
    return {
        path
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
        and path.suffix not in {".py", ".pyc"}
        and "__pycache__" not in path.parts
    }


def test_every_non_python_package_file_is_declared_as_package_data() -> None:
    undeclared = _non_python_package_files() - _declared_package_data()

    assert not undeclared, (
        "Add these to [tool.setuptools.package-data] in pyproject.toml, or a "
        "built wheel/Docker image will not contain them: "
        + ", ".join(sorted(str(p.relative_to(SRC)) for p in undeclared))
    )
