"""The viewer's TypeScript types mirror the Python schema by hand — assert it.

``viewer/src/types/diagram.ts`` and ``viewer/src/types/geometry.ts`` both say
they mirror their Python counterparts "field-for-field", but nothing enforced
it: adding a member to a Python enum left the frontend union silently narrower
than the responses it would actually receive, and ``tsc`` cannot catch that
because the drift is between two languages, not within one.

This is the same guarantee ``tests/test_schema_export.py`` gives the committed
JSON Schemas, applied to the hand-written frontend mirror. It parses the
declarations out of the ``.ts`` source rather than running ``tsc``, so it costs
a file read and needs no Node toolchain in the Python test run.

**What this does not cover**, deliberately, so the guarantee isn't overstated:

* Unions written inline inside an interface rather than as a named
  ``export type`` (``DiagramConstruction.mode``/``centre_method``/
  ``direction``). Those are checked by name below where they are stable
  one-liners, and not otherwise.
* Field-level shape — whether ``DiagramSymbol`` has every field
  ``ir.DiagramSymbol`` has, and with compatible types. A structural check of
  that belongs in generated types, not a regex.

A failure here means one side gained or lost a member. Fix the mirror; do not
relax the test.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from crochet_reconstruction.diagram.corrections import (
    CORRECTIONS_SCHEMA_VERSION,
    RelationshipOverrideAction,
)
from crochet_reconstruction.diagram.diagnostics import DiagramSeverity
from crochet_reconstruction.diagram.ir import (
    DIAGRAM_SCHEMA_VERSION,
    ConstructionMode,
    DiagramConstruction,
    InferenceMethod,
    RelationshipType,
)
from crochet_reconstruction.diagram.ontology import (
    ClassificationMethod,
    ConfidenceBand,
    DiagramStitchType,
)
from crochet_reconstruction.geometry.models import GEOMETRY_SCHEMA_VERSION

VIEWER_TYPES_DIR = Path(__file__).resolve().parents[1] / "viewer" / "src" / "types"

_STRING_LITERAL_RE = re.compile(r'"([^"]*)"')


def _read(filename: str) -> str:
    return (VIEWER_TYPES_DIR / filename).read_text(encoding="utf-8")


def _exported_union(source: str, name: str) -> set[str]:
    """Members of ``export type <name> = "a" | "b" | ...;``."""
    match = re.search(rf"export type {name} =(.*?);", source, re.DOTALL)
    assert match is not None, f"no exported type {name!r} found in the viewer types"
    return set(_STRING_LITERAL_RE.findall(match.group(1)))


def _exported_const(source: str, name: str) -> str:
    match = re.search(rf'export const {name} = "([^"]+)";', source)
    assert match is not None, f"no exported const {name!r} found in the viewer types"
    return match.group(1)


def _interface_field_literals(source: str, interface: str, field: str) -> set[str]:
    """Literals of a union written inline on one field of an interface."""
    block = re.search(rf"export interface {interface} \{{(.*?)\n\}}", source, re.DOTALL)
    assert block is not None, f"no interface {interface!r} found in the viewer types"
    line = re.search(rf"^\s*{field}: (.*)$", block.group(1), re.MULTILINE)
    assert line is not None, f"no field {field!r} on interface {interface!r}"
    return set(_STRING_LITERAL_RE.findall(line.group(1)))


@pytest.fixture(scope="module")
def diagram_ts() -> str:
    return _read("diagram.ts")


@pytest.fixture(scope="module")
def geometry_ts() -> str:
    return _read("geometry.ts")


class TestNamedUnions:
    @pytest.mark.parametrize(
        ("ts_name", "python_members"),
        [
            ("DiagramStitchType", {t.value for t in DiagramStitchType}),
            ("ClassificationMethod", {m.value for m in ClassificationMethod}),
            ("ConfidenceBand", set(get_args(ConfidenceBand))),
            ("RelationshipType", set(get_args(RelationshipType))),
            ("InferenceMethod", set(get_args(InferenceMethod))),
            ("DiagramSeverity", set(get_args(DiagramSeverity))),
            (
                "RelationshipOverrideAction",
                {a.value for a in RelationshipOverrideAction},
            ),
        ],
    )
    def test_union_matches_python(self, diagram_ts, ts_name, python_members):
        assert _exported_union(diagram_ts, ts_name) == python_members


class TestInlineUnions:
    def test_construction_mode(self, diagram_ts):
        assert _interface_field_literals(diagram_ts, "DiagramConstruction", "mode") == {
            m.value for m in ConstructionMode
        }

    def test_centre_method(self, diagram_ts):
        expected = set(
            get_args(get_args(DiagramConstruction.model_fields["centre_method"].annotation)[0])
        )
        assert (
            _interface_field_literals(diagram_ts, "DiagramConstruction", "centre_method")
            == expected
        )

    def test_direction(self, diagram_ts):
        expected = set(
            get_args(get_args(DiagramConstruction.model_fields["direction"].annotation)[0])
        )
        assert _interface_field_literals(diagram_ts, "DiagramConstruction", "direction") == expected


class TestSchemaVersionConstants:
    def test_diagram_schema_version(self, diagram_ts):
        assert _exported_const(diagram_ts, "SUPPORTED_DIAGRAM_SCHEMA_VERSION") == (
            DIAGRAM_SCHEMA_VERSION
        )

    def test_geometry_schema_version(self, geometry_ts):
        assert _exported_const(geometry_ts, "SUPPORTED_SCHEMA_VERSION") == GEOMETRY_SCHEMA_VERSION

    def test_corrections_schema_version_is_not_mirrored_as_a_constant(self, diagram_ts):
        """Recorded, not enforced: the frontend sends corrections without
        pinning CORRECTIONS_SCHEMA_VERSION, so there is no constant to compare.
        This test fails if one is ever added without being wired up here."""
        assert CORRECTIONS_SCHEMA_VERSION
        assert "CORRECTIONS_SCHEMA_VERSION" not in diagram_ts


class TestTheGuardItself:
    """A mirror test that cannot fail is worse than none — these prove the
    parsing actually reads the file rather than vacuously passing."""

    def test_missing_union_is_an_error_not_an_empty_set(self, diagram_ts):
        with pytest.raises(AssertionError):
            _exported_union(diagram_ts, "NoSuchTypeName")

    def test_a_narrower_union_would_be_detected(self, diagram_ts):
        members = _exported_union(diagram_ts, "ClassificationMethod")
        assert members - {"text_label"} != {m.value for m in ClassificationMethod}
