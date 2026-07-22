"""Stitch-graph data model: one node per individual worked stitch.

Schema is versioned independently of :data:`crochet_reconstruction.domain.pattern.SCHEMA_VERSION`
since the graph is a derived representation, not the source of truth — the
compiled ``Pattern`` remains authoritative; this graph must always be
reproducible from it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crochet_reconstruction.domain.enums import ComponentKind, LoopPlacement, StitchFamily

GRAPH_SCHEMA_VERSION = "0.1.0"

EdgeType = Literal["yarn_sequence", "insertion", "horizontal_neighbor", "round_closure"]
YarnSegmentType = Literal["connector"]
StitchHeightCategory = Literal["short", "medium", "tall"]

_HEIGHT_CATEGORY_BY_STITCH: dict[StitchFamily, StitchHeightCategory] = {
    StitchFamily.SC: "short",
    StitchFamily.HDC: "medium",
    StitchFamily.DC: "tall",
}


def stitch_height_category(stitch: StitchFamily) -> StitchHeightCategory:
    """Coarse relative-height bucket for a stitch family.

    A simplification for the first geometry slice — real relative stitch
    heights (sc ~1x, hdc ~1.5x, dc ~2x) belong in the geometry layer's
    dimension tables, not here. This mapping only needs to grow when a new
    ``StitchFamily`` member is added upstream.
    """
    return _HEIGHT_CATEGORY_BY_STITCH[stitch]


class StitchNode(BaseModel):
    """One individually identified worked stitch."""

    model_config = ConfigDict(frozen=True)

    stitch_id: str = Field(description='Stable ID, e.g. "body-r04-s018".')
    component_kind: ComponentKind
    round_number: int = Field(ge=1)
    position_in_round: int = Field(ge=0, description="0-indexed position within the round.")
    sequence_index: int = Field(ge=0, description="0-indexed global working order.")
    stitch_type: StitchFamily
    stitch_height_category: StitchHeightCategory
    loop_placement: LoopPlacement
    parent_stitch_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Insertion targets: previous-round stitch IDs this stitch is worked into. "
            "Empty only for a magic-ring starting stitch, whose target is the ring "
            "itself, not a prior stitch — see `into_ring`."
        ),
    )
    into_ring: bool = Field(
        default=False, description="True for round-1 stitches worked into a magic ring."
    )
    yarn_id: str = Field(default="main", description="Phase 1 supports solid-colour single yarn.")
    colour_id: str = Field(default="main")
    is_increase: bool = False
    increase_group_id: str | None = None
    is_decrease: bool = False
    decrease_group_id: str | None = None
    repeat_group_id: str | None = Field(
        default=None, description="ID of the RepeatOp iteration this stitch belongs to, if any."
    )
    source_reference: str = Field(description='e.g. "crown round 3 operation 2 (repeat 4/8)".')
    diagram_symbol_reference: str | None = None
    target_rule: Literal["explicit", "deterministic_left_to_right"] = "deterministic_left_to_right"


class YarnSegment(BaseModel):
    """A simplified structural piece of yarn path owned by one stitch.

    The first slice models only a single ``connector`` segment per
    yarn-sequence edge (previous stitch -> this stitch). Richer semantic
    segmentation (entry/lower-loop/post/upper-loop/exit) is deferred to a
    later slice, per the data model note in the geometry/rendering spec —
    this type is intentionally narrow, not final.
    """

    model_config = ConfigDict(frozen=True)

    segment_id: str
    owning_stitch_id: str
    segment_type: YarnSegmentType = "connector"
    from_stitch_id: str | None = None
    to_stitch_id: str


class Edge(BaseModel):
    model_config = ConfigDict(frozen=True)

    edge_id: str
    edge_type: EdgeType
    source_id: str
    target_id: str


class StitchGraph(BaseModel):
    """The complete deterministic stitch graph for one compiled pattern."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = GRAPH_SCHEMA_VERSION
    pattern_fingerprint: str | None
    nodes: list[StitchNode]
    edges: list[Edge]
    yarn_segments: list[YarnSegment]
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str | None = None
