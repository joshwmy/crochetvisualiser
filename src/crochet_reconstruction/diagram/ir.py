"""Versioned Diagram IR: the parsed-and-interpreted-but-not-yet-StitchGraph
representation of one SVG crochet chart.

Distinct from :class:`crochet_reconstruction.graph.models.StitchGraph` on
purpose (brief: "Do not confuse Diagram IR with StitchGraph") — this IR
carries spatial/provenance/confidence information (bounding boxes,
classification method, per-symbol evidence) that has no meaning once a
pattern is expressed as worked stitches. ``diagram/compiler.py`` is the one
place that translates from this IR into the existing ``StitchGraph``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic
from crochet_reconstruction.diagram.ontology import (
    ClassificationMethod,
    ConfidenceBand,
    DiagramStitchType,
)

DIAGRAM_SCHEMA_VERSION = "1.0.0"

Vec2 = tuple[float, float]
BBox = tuple[float, float, float, float]
"""(min_x, min_y, max_x, max_y) in the document's normalised coordinate system."""


class ConstructionMode(StrEnum):
    """Only ``CIRCULAR`` is implemented this slice (brief: "first topology
    implementation should target circular or radial charts"). ``ROW`` is
    reserved so the schema does not need a breaking change later, the same
    pattern ``domain.enums.Construction.JOINED`` already uses — selecting a
    chart this pipeline detects as row/flat-panel construction produces an
    explicit ``UNSUPPORTED_CHART_CONSTRUCTION`` diagnostic, never a silent
    best-effort circular interpretation."""

    CIRCULAR = "circular"
    ROW = "row"


RelationshipType = Literal[
    "parent_attachment",
    "yarn_sequence",
    "horizontal_neighbor",
    "explicit_connector",
    "round_closure",
    "increase_group",
    "decrease_group",
    "centre_attachment",
]

InferenceMethod = Literal[
    "explicit_connector",
    "explicit_metadata",
    "manual_override",
    "radial_projection",
    "nearest_previous_round",
]


class DiagramSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["svg_diagram"] = "svg_diagram"
    fingerprint: str
    width: float
    height: float
    view_box: BBox


class DiagramConstruction(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: ConstructionMode
    centre: Vec2 | None = None
    centre_method: (
        Literal["explicit_metadata", "explicit_symbol", "user_specified", "geometric_estimate"]
        | None
    ) = None
    direction: Literal["clockwise", "counterclockwise"] | None = None
    start_symbol_id: str | None = None
    round_tolerance: float | None = None
    """Radial-distance clustering tolerance, in the document's own
    normalised coordinate units (not cm — a diagram has no gauge)."""


class DiagramSymbol(BaseModel):
    """One extracted-and-classified chart symbol.

    See ``docs/diagram-ir-spec.md`` for the field-by-field rationale;
    ``symbol_id`` is derived deterministically from the source element's
    path in the document (never a random UUID) so re-analysing the same SVG
    reproduces identical IDs — a precondition for corrections keyed by
    ``symbol_id`` to remain valid across re-analysis.
    """

    model_config = ConfigDict(frozen=True)

    symbol_id: str
    stitch_type: DiagramStitchType | None
    candidate_stitch_types: list[DiagramStitchType] = Field(default_factory=list)
    source_element_id: str | None
    source_element_path: str
    source_metadata: dict[str, str] = Field(default_factory=dict)
    position: Vec2
    bbox: BBox
    anchor: Vec2
    orientation_deg: float
    scale: float
    round_index: int | None = None
    sequence_index: int | None = None
    classification_method: ClassificationMethod
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    user_override: bool = False
    ambiguous: bool = False
    unsupported: bool = False
    round_start: bool = False
    round_closure: bool = False
    geometry_fingerprint: str | None = None


class DiagramRelationship(BaseModel):
    model_config = ConfigDict(frozen=True)

    relationship_id: str
    source_symbol_ids: list[str]
    target_symbol_ids: list[str]
    relationship_type: RelationshipType
    inference_method: InferenceMethod
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    user_override: bool = False


class DiagramRound(BaseModel):
    model_config = ConfigDict(frozen=True)

    round_index: int = Field(ge=1)
    symbol_ids: list[str]
    centre_distance_avg: float | None
    start_symbol_id: str | None
    closure: bool


class DiagramDocument(BaseModel):
    """The complete Diagram IR for one analysed SVG chart."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = DIAGRAM_SCHEMA_VERSION
    source: DiagramSource
    construction: DiagramConstruction
    symbols: list[DiagramSymbol]
    relationships: list[DiagramRelationship]
    rounds: list[DiagramRound]
    diagnostics: list[DiagramDiagnostic] = Field(default_factory=list)
    fingerprint: str | None = None
