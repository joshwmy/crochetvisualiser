"""Shared test fixtures and helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from crochet_reconstruction.domain.enums import BrimType, Construction, StitchFamily
from crochet_reconstruction.domain.gauge import Gauge
from crochet_reconstruction.domain.measurements import UserMeasurements
from crochet_reconstruction.domain.pattern import ProjectInput, ProjectMetadata, TemplateRef


def make_project_input(**overrides: Any) -> ProjectInput:
    """Build a valid ``ProjectInput`` (adult medium HDC beanie) with overrides.

    Overrides may target top-level fields directly (e.g. ``construction=...``)
    or nested measurement/gauge fields via ``head_circumference_cm=...`` /
    ``stitches_per_10cm=...`` for convenience in tests that only vary one value.
    """
    measurement_fields = {"head_circumference_cm", "target_height_cm", "brim_height_cm"}
    gauge_fields = {"stitch_family", "stitches_per_10cm", "rounds_per_10cm"}

    measurements: dict[str, Any] = {
        "head_circumference_cm": Decimal("56.0"),
        "target_height_cm": Decimal("21.0"),
        "brim_height_cm": Decimal("4.0"),
    }
    gauge: dict[str, Any] = {
        "stitch_family": StitchFamily.HDC,
        "stitches_per_10cm": Decimal("16.0"),
        "rounds_per_10cm": Decimal("12.0"),
    }
    top_level: dict[str, Any] = {
        "project": ProjectMetadata(project_id="test-project", title="Test Beanie"),
        "template": TemplateRef(id="top_down_basic", version="1.0.0"),
        "negative_ease_pct": Decimal("8.0"),
        "construction": Construction.CONTINUOUS,
        "brim_type": BrimType.BLO_IN_ROUND,
    }

    for key, value in overrides.items():
        if key in measurement_fields:
            measurements[key] = value
        elif key in gauge_fields:
            gauge[key] = value
        else:
            top_level[key] = value

    return ProjectInput(
        measurements=UserMeasurements(**measurements),
        gauge=Gauge(**gauge),
        **top_level,
    )
