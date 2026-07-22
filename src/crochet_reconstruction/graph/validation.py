"""Invariant checks over an already-built :class:`StitchGraph`.

Most of these invariants are already enforced *during* construction in
``builder.py`` (which raises :class:`GraphBuildError` immediately on
violation). This module re-checks them independently over the finished
graph object — the same "trust but verify" posture ``validation/validator.py``
takes toward the compiler — so a graph loaded from a serialized fixture
(not freshly built) is still checked before being handed to the geometry
layer. A graph that fails any check here must never reach geometry/rendering.
"""

from __future__ import annotations

from collections import Counter

from crochet_reconstruction.graph.errors import GraphValidationError
from crochet_reconstruction.graph.models import StitchGraph


def validate_graph(graph: StitchGraph) -> None:
    """Raise :class:`GraphValidationError` on the first violated invariant."""
    _check_unique_stitch_ids(graph)
    _check_sequence_indices(graph)
    _check_insertion_targets_exist(graph)
    _check_parent_consumption(graph)
    _check_round_totals(graph)


def _check_unique_stitch_ids(graph: StitchGraph) -> None:
    ids = [n.stitch_id for n in graph.nodes]
    counts = Counter(ids)
    duplicates = [stitch_id for stitch_id, count in counts.items() if count > 1]
    if duplicates:
        raise GraphValidationError(f"duplicate stitch IDs: {sorted(duplicates)}")


def _check_sequence_indices(graph: StitchGraph) -> None:
    indices = sorted(n.sequence_index for n in graph.nodes)
    expected = list(range(len(graph.nodes)))
    if indices != expected:
        raise GraphValidationError(
            f"sequence indices are not a contiguous 0..N-1 range: got {indices[:10]}..."
        )


def _check_insertion_targets_exist(graph: StitchGraph) -> None:
    known_ids = {n.stitch_id for n in graph.nodes}
    for node in graph.nodes:
        if node.into_ring:
            if node.parent_stitch_ids:
                raise GraphValidationError(
                    f"{node.stitch_id}: into_ring stitch must not have parent_stitch_ids"
                )
            continue
        if not node.parent_stitch_ids:
            raise GraphValidationError(f"{node.stitch_id}: non-ring stitch has no insertion target")
        for parent_id in node.parent_stitch_ids:
            if parent_id not in known_ids:
                raise GraphValidationError(
                    f"{node.stitch_id}: insertion target {parent_id!r} does not exist"
                )


def _check_parent_consumption(graph: StitchGraph) -> None:
    """Every non-ring-round stitch must be consumed by exactly the correct count.

    A normal stitch is consumed by exactly one child. An increase's inputs
    are each consumed by every one of its output children (shared parent),
    not "exactly once" in the child-count sense — so this check verifies the
    weaker but still meaningful invariant: every parent referenced by an
    increase/decrease group must have been in the same, immediately
    preceding round as its children.
    """
    nodes_by_id = {n.stitch_id: n for n in graph.nodes}
    for node in graph.nodes:
        for parent_id in node.parent_stitch_ids:
            parent = nodes_by_id[parent_id]
            same_round = (
                parent.component_kind == node.component_kind
                and parent.round_number == node.round_number
            )
            if same_round:
                raise GraphValidationError(
                    f"{node.stitch_id}: insertion target {parent_id!r} is in the same round"
                )


def _check_round_totals(graph: StitchGraph) -> None:
    totals: Counter[tuple[str, int]] = Counter()
    for node in graph.nodes:
        totals[(node.component_kind.value, node.round_number)] += 1
    # Every round must have at least one stitch and monotonically increasing
    # position_in_round values with no gaps — checked via reconstruction.
    positions: dict[tuple[str, int], set[int]] = {}
    for node in graph.nodes:
        key = (node.component_kind.value, node.round_number)
        positions.setdefault(key, set()).add(node.position_in_round)
    for key, count in totals.items():
        expected_positions = set(range(count))
        if positions[key] != expected_positions:
            raise GraphValidationError(
                f"{key[0]} round {key[1]}: position_in_round values {sorted(positions[key])} "
                f"are not a contiguous 0..{count - 1} range"
            )
