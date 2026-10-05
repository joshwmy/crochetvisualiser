"""Write a :class:`GeometryDocument` to a JSON fixture file for the viewer."""

from __future__ import annotations

import json
from pathlib import Path

from crochet_reconstruction.geometry.models import GeometryDocument


def write_geometry_json(document: GeometryDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = document.model_dump(mode="json")
    output_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return output_path
