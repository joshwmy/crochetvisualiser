"""Expand a compiled :class:`Pattern` into an explicit per-stitch :class:`StitchGraph`.

Deterministic insertion-target assumption
------------------------------------------
The domain IR (see ``domain/operations.py``) records only aggregate counts
per operation — e.g. ``IncreaseOp(input=1, output=2)`` means "work 2 stitches
into 1 previous-round stitch", but does not say *which* previous-round
stitch. This builder resolves that by consuming the previous round's
stitches strictly left-to-right, in the order they were themselves worked.

This is a safe, non-arbitrary choice for every pattern this compiler
currently produces: ``crown.py``'s schedule and ``body.py``'s plain rounds
are both worked in one direction with no back-tracking, so "the next
unconsumed previous-round stitch" is the only insertion target a human
crocheter following the same instructions would ever use. It is still
recorded explicitly (``StitchNode.target_rule``) rather than presented as
IR-given fact, because a future written-pattern or diagram parser producing
ambiguous or out-of-order instructions would need a different resolution
strategy — this builder must not be silently reused for that case without
re-examining this assumption.

Every stitch in round *r* must consume exactly the previous round's stitches
with none left over and none consumed twice; this is checked defensively at
the end of each round (see ``_finish_round``) even though the validator has
already confirmed the aggregate arithmetic — a graph-level bug should fail
loudly here, not silently produce a graph with a dangling or double-consumed
parent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from crochet_reconstruction.domain.enums import (
    ClosureKind,
    ComponentKind,
    LoopPlacement,
    StitchFamily,
)
from crochet_reconstruction.domain.operations import (
    DecreaseOp,
    IncreaseOp,
    MagicRingOp,
    Operation,
    RepeatOp,
    StitchOp,
)
from crochet_reconstruction.domain.pattern import Pattern
from crochet_reconstruction.domain.rounds import Round
from crochet_reconstruction.graph.errors import GraphBuildError
from crochet_reconstruction.graph.fingerprint import compute_graph_fingerprint
from crochet_reconstruction.graph.models import (
    Edge,
    StitchGraph,
    StitchNode,
    YarnSegment,
    stitch_height_category,
)


@dataclass
class _FlatOp:
    """One non-repeat leaf operation, in working order, with provenance."""

    op: MagicRingOp | StitchOp | IncreaseOp | DecreaseOp
    source_reference: str
    repeat_group_id: str | None


@dataclass
class _BuildState:
    nodes: list[StitchNode] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    segments: list[YarnSegment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sequence_index: int = 0


def _flatten_round_operations(
    round_number: int, operations: list[Operation], component_label: str
) -> list[_FlatOp]:
    flat: list[_FlatOp] = []
    for op_index, op in enumerate(operations, start=1):
        _flatten_one(op, round_number, op_index, component_label, None, flat)
    return flat


def _flatten_one(
    op: Operation,
    round_number: int,
    op_index: int,
    component_label: str,
    repeat_group_id: str | None,
    out: list[_FlatOp],
    ref_override: str | None = None,
) -> None:
    base_ref = ref_override or f"{component_label} round {round_number} operation {op_index}"
    if isinstance(op, RepeatOp):
        for iteration in range(1, op.times + 1):
            group_id = f"{component_label}-r{round_number}-op{op_index}-rep{iteration}"
            ref = f"{base_ref} (repeat {iteration}/{op.times})"
            for child in op.body:
                _flatten_one(
                    child, round_number, op_index, component_label, group_id, out, ref_override=ref
                )
        return
    out.append(_FlatOp(op=op, source_reference=base_ref, repeat_group_id=repeat_group_id))


def build_stitch_graph(pattern: Pattern) -> StitchGraph:
    """Build the deterministic stitch graph for a compiled, validated pattern."""
    state = _BuildState()
    prev_round_ids: list[str] = []

    for component in pattern.components:
        component_label = component.kind.value
        for round_ in component.rounds:
            prev_round_ids = _build_round(state, component_label, round_, prev_round_ids)

    _add_yarn_sequence_edges(state)

    graph = StitchGraph(
        pattern_fingerprint=pattern.fingerprint,
        nodes=state.nodes,
        edges=state.edges,
        yarn_segments=state.segments,
        warnings=state.warnings,
    )
    return graph.model_copy(update={"fingerprint": compute_graph_fingerprint(graph)})


def _build_round(
    state: _BuildState,
    component_label: str,
    round_: Round,
    prev_round_ids: list[str],
) -> list[str]:
    flat_ops = _flatten_round_operations(round_.number, round_.operations, component_label)
    current_round_ids: list[str] = []
    parent_cursor = 0

    for flat in flat_ops:
        parent_cursor = _emit_leaf(
            state,
            component_label,
            round_,
            flat,
            prev_round_ids,
            parent_cursor,
            current_round_ids,
        )

    if parent_cursor != len(prev_round_ids):
        raise GraphBuildError(
            f"{component_label} round {round_.number}: consumed {parent_cursor} of "
            f"{len(prev_round_ids)} previous-round stitches — expected all of them "
            f"consumed exactly once"
        )
    if len(current_round_ids) != round_.stated_total:
        raise GraphBuildError(
            f"{component_label} round {round_.number}: produced {len(current_round_ids)} "
            f"stitches but stated_total is {round_.stated_total}"
        )

    _add_horizontal_neighbor_edges(state, current_round_ids)
    if round_.closure is ClosureKind.SLIP_STITCH_JOIN and current_round_ids:
        state.edges.append(
            Edge(
                edge_id=f"{current_round_ids[-1]}->closure->{current_round_ids[0]}",
                edge_type="round_closure",
                source_id=current_round_ids[-1],
                target_id=current_round_ids[0],
            )
        )

    return current_round_ids


def _emit_leaf(
    state: _BuildState,
    component_label: str,
    round_: Round,
    flat: _FlatOp,
    prev_round_ids: list[str],
    parent_cursor: int,
    current_round_ids: list[str],
) -> int:
    op = flat.op
    if isinstance(op, MagicRingOp):
        for _ in range(op.output):
            _append_node(
                state,
                component_label,
                round_,
                current_round_ids,
                stitch=op.stitch,
                loop=LoopPlacement.BOTH,
                parent_ids=[],
                into_ring=True,
                source_reference=flat.source_reference,
                repeat_group_id=flat.repeat_group_id,
            )
        return parent_cursor

    if isinstance(op, StitchOp):
        for _ in range(op.count):
            parent_cursor = _require_parent(
                state, component_label, round_, prev_round_ids, parent_cursor, count=1
            )
            parent_ids = [prev_round_ids[parent_cursor - 1]]
            _append_node(
                state,
                component_label,
                round_,
                current_round_ids,
                stitch=op.stitch,
                loop=op.loop,
                parent_ids=parent_ids,
                source_reference=flat.source_reference,
                repeat_group_id=flat.repeat_group_id,
            )
        return parent_cursor

    if isinstance(op, IncreaseOp):
        start = parent_cursor
        parent_cursor = _require_parent(
            state, component_label, round_, prev_round_ids, parent_cursor, count=op.input
        )
        parent_ids = prev_round_ids[start:parent_cursor]
        group_id = f"{component_label}-r{round_.number}-inc-{len(current_round_ids)}"
        for _ in range(op.output):
            _append_node(
                state,
                component_label,
                round_,
                current_round_ids,
                stitch=op.stitch,
                loop=op.loop,
                parent_ids=list(parent_ids),
                source_reference=flat.source_reference,
                repeat_group_id=flat.repeat_group_id,
                is_increase=True,
                increase_group_id=group_id,
            )
        return parent_cursor

    if isinstance(op, DecreaseOp):
        start = parent_cursor
        parent_cursor = _require_parent(
            state, component_label, round_, prev_round_ids, parent_cursor, count=op.input
        )
        parent_ids = prev_round_ids[start:parent_cursor]
        group_id = f"{component_label}-r{round_.number}-dec-{len(current_round_ids)}"
        for _ in range(op.output):
            _append_node(
                state,
                component_label,
                round_,
                current_round_ids,
                stitch=op.stitch,
                loop=op.loop,
                parent_ids=list(parent_ids),
                source_reference=flat.source_reference,
                repeat_group_id=flat.repeat_group_id,
                is_decrease=True,
                decrease_group_id=group_id,
            )
        return parent_cursor

    raise GraphBuildError(f"unhandled leaf operation type: {type(op).__name__}")


def _require_parent(
    state: _BuildState,
    component_label: str,
    round_: Round,
    prev_round_ids: list[str],
    parent_cursor: int,
    *,
    count: int,
) -> int:
    if parent_cursor + count > len(prev_round_ids):
        raise GraphBuildError(
            f"{component_label} round {round_.number}: needs {count} more previous-round "
            f"stitch(es) at cursor {parent_cursor} but only {len(prev_round_ids)} exist"
        )
    return parent_cursor + count


def _append_node(
    state: _BuildState,
    component_label: str,
    round_: Round,
    current_round_ids: list[str],
    *,
    stitch: StitchFamily,
    loop: LoopPlacement,
    parent_ids: list[str],
    source_reference: str,
    repeat_group_id: str | None,
    into_ring: bool = False,
    is_increase: bool = False,
    increase_group_id: str | None = None,
    is_decrease: bool = False,
    decrease_group_id: str | None = None,
) -> None:
    position = len(current_round_ids)
    stitch_id = f"{component_label}-r{round_.number:02d}-s{position:03d}"
    node = StitchNode(
        stitch_id=stitch_id,
        component_kind=ComponentKind(component_label),
        round_number=round_.number,
        position_in_round=position,
        sequence_index=state.sequence_index,
        stitch_type=stitch,
        stitch_height_category=stitch_height_category(stitch),
        loop_placement=loop,
        parent_stitch_ids=parent_ids,
        into_ring=into_ring,
        is_increase=is_increase,
        increase_group_id=increase_group_id,
        is_decrease=is_decrease,
        decrease_group_id=decrease_group_id,
        repeat_group_id=repeat_group_id,
        source_reference=source_reference,
    )
    state.nodes.append(node)
    current_round_ids.append(stitch_id)
    state.sequence_index += 1

    for parent_id in parent_ids:
        state.edges.append(
            Edge(
                edge_id=f"{parent_id}->insertion->{stitch_id}",
                edge_type="insertion",
                source_id=stitch_id,
                target_id=parent_id,
            )
        )


def _add_horizontal_neighbor_edges(state: _BuildState, round_ids: list[str]) -> None:
    n = len(round_ids)
    if n < 2:
        return
    for i in range(n):
        a = round_ids[i]
        b = round_ids[(i + 1) % n]
        state.edges.append(
            Edge(
                edge_id=f"{a}->neighbor->{b}",
                edge_type="horizontal_neighbor",
                source_id=a,
                target_id=b,
            )
        )


def _add_yarn_sequence_edges(state: _BuildState) -> None:
    for i in range(len(state.nodes) - 1):
        a = state.nodes[i].stitch_id
        b = state.nodes[i + 1].stitch_id
        state.edges.append(
            Edge(edge_id=f"{a}->seq->{b}", edge_type="yarn_sequence", source_id=a, target_id=b)
        )
        state.segments.append(
            YarnSegment(
                segment_id=f"seg-{a}-{b}",
                owning_stitch_id=b,
                from_stitch_id=a,
                to_stitch_id=b,
            )
        )
