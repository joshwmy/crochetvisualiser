"""``DiagramTopologyCompiler``: Diagram IR (+ inferred topology) -> the
*existing* ``StitchGraph``/``Component`` types — no second graph model.

Architecture decision (brief: "Decide and document whether a diagram also
produces an existing Pattern domain object" — recorded here and in
``docs/svg-diagram-ingestion.md``): this compiler builds
:class:`~crochet_reconstruction.graph.models.StitchGraph` **directly**
(Option A), not by round-tripping through
:class:`~crochet_reconstruction.domain.pattern.Pattern`'s
``Operation``/``RepeatOp`` abstraction the way
:func:`crochet_reconstruction.graph.builder.build_stitch_graph` does for
written patterns. Two independent reasons:

1. ``graph/builder.py``'s own docstring says its left-to-right "consume the
   next unconsumed previous-round stitch" assumption is safe *only* because
   every written-pattern operation gives an aggregate count, never an
   explicit target — and explicitly warns that "a future... diagram parser
   producing ambiguous or out-of-order instructions would need a different
   resolution strategy... must not be silently reused... without
   re-examining this assumption." A diagram's topology inference (this
   package's ``topology.py``) *does* name an explicit parent for every
   stitch (via connectors, metadata, or radial projection) — strictly
   richer information than an ``Operation``'s aggregate count can carry
   without loss.
2. ``StitchNode`` already has ``diagram_symbol_reference`` and
   ``target_rule: Literal["explicit", "deterministic_left_to_right"]``
   fields with no other producer in this codebase — direct evidence this
   extension point was anticipated.

A ``list[Component]`` is still built alongside the graph, but *only* to
satisfy ``geometry.layout.build_geometry``'s existing parameter shape:
``geometry.rotational_rounds._round_placements`` reads exactly
``Component.kind``/``Round.number``/``Round.stated_total`` and nothing else
from it (verified by inspection — no other field of ``Round``/``Operation``
is read anywhere in the geometry package). This is not a second geometry
engine or a route through ``Pattern`` — it is the minimum adapter shape the
*existing, unmodified* geometry function requires.
"""

from __future__ import annotations

from dataclasses import dataclass

from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.diagram.ir import DiagramSymbol
from crochet_reconstruction.diagram.ontology import WORKED_STITCH_FAMILY
from crochet_reconstruction.diagram.topology import TopologyResult, is_worked_stitch
from crochet_reconstruction.domain.enums import (
    ClosureKind,
    ComponentKind,
    Construction,
    LoopPlacement,
)
from crochet_reconstruction.domain.operations import DecreaseOp, IncreaseOp, Operation, StitchOp
from crochet_reconstruction.domain.rounds import Component, Round
from crochet_reconstruction.graph.fingerprint import compute_graph_fingerprint
from crochet_reconstruction.graph.models import (
    Edge,
    StitchGraph,
    StitchNode,
    YarnSegment,
    stitch_height_category,
)

COMPONENT_LABEL = ComponentKind.PIECE.value


@dataclass(frozen=True)
class CompiledDiagram:
    graph: StitchGraph
    components: list[Component]


def _extract_parent_map(topology: TopologyResult) -> dict[str, list[str]]:
    parent_map: dict[str, list[str]] = {}
    for rel in topology.relationships:
        if rel.relationship_type in ("parent_attachment", "centre_attachment"):
            parent_map[rel.source_symbol_ids[0]] = list(rel.target_symbol_ids)
    return parent_map


def compile_diagram_to_stitch_graph(
    symbols: list[DiagramSymbol],
    topology: TopologyResult,
    parent_map: dict[str, list[str]] | None = None,
) -> tuple[CompiledDiagram | None, list[DiagramDiagnostic]]:
    diagnostics: list[DiagramDiagnostic] = []
    symbols_by_id = {s.symbol_id: s for s in symbols}
    effective_parent_map = parent_map if parent_map is not None else _extract_parent_map(topology)

    if not topology.rounds:
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.GRAPH_VALIDATION_FAILURE,
                message="topology inference produced no rounds — nothing to compile",
            )
        )
        return None, diagnostics

    first_round_index = topology.rounds[0].round_index
    stitch_id_by_symbol: dict[str, str] = {}
    nodes: list[StitchNode] = []
    edges: list[Edge] = []
    rounds: list[Round] = []
    sequence_index = 0
    prev_round_ids: list[str] = []

    for diagram_round in topology.rounds:
        member_ids = diagram_round.symbol_ids
        if not member_ids:
            continue

        parent_usage: dict[str, int] = {}
        for symbol_id in member_ids:
            parents = effective_parent_map.get(symbol_id, [])
            if len(parents) == 1:
                parent_usage[parents[0]] = parent_usage.get(parents[0], 0) + 1

        round_ids: list[str] = []
        operations: list[Operation] = []

        for position, symbol_id in enumerate(member_ids):
            symbol = symbols_by_id.get(symbol_id)
            if (
                symbol is None
                or symbol.stitch_type is None
                or not is_worked_stitch(symbol.stitch_type)
            ):
                diagnostics.append(
                    DiagramDiagnostic(
                        severity="error",
                        code=DiagramDiagnosticCode.UNCLASSIFIED_SYMBOL,
                        message=f"symbol {symbol_id} has no resolved worked-stitch type and "
                        f"cannot be compiled — correct it before compiling",
                        symbol_id=symbol_id,
                        round_index=diagram_round.round_index,
                    )
                )
                return None, diagnostics

            family = WORKED_STITCH_FAMILY[symbol.stitch_type]
            stitch_id = f"{COMPONENT_LABEL}-r{diagram_round.round_index:02d}-s{position:03d}"
            stitch_id_by_symbol[symbol_id] = stitch_id
            round_ids.append(stitch_id)

            into_ring = diagram_round.round_index == first_round_index
            parent_symbol_ids = [] if into_ring else effective_parent_map.get(symbol_id, [])
            parent_stitch_ids: list[str] = []
            for parent_symbol_id in parent_symbol_ids:
                parent_stitch_id = stitch_id_by_symbol.get(parent_symbol_id)
                if parent_stitch_id is None:
                    diagnostics.append(
                        DiagramDiagnostic(
                            severity="error",
                            code=DiagramDiagnosticCode.MISSING_PARENT,
                            message=f"symbol {symbol_id}'s parent {parent_symbol_id} was not "
                            f"compiled (missing or in a later round)",
                            symbol_id=symbol_id,
                            round_index=diagram_round.round_index,
                        )
                    )
                    return None, diagnostics
                parent_stitch_ids.append(parent_stitch_id)

            is_increase = (
                not into_ring
                and len(parent_stitch_ids) == 1
                and parent_usage.get(parent_symbol_ids[0], 0) > 1
            )
            is_decrease = not into_ring and len(parent_stitch_ids) > 1
            increase_group_id = (
                f"{COMPONENT_LABEL}-r{diagram_round.round_index:02d}-inc-{parent_symbol_ids[0]}"
                if is_increase
                else None
            )
            decrease_group_id = (
                f"{COMPONENT_LABEL}-r{diagram_round.round_index:02d}-dec-{position:03d}"
                if is_decrease
                else None
            )

            if is_decrease and len(parent_stitch_ids) > 1 and prev_round_ids:
                indices = [prev_round_ids.index(p) for p in parent_stitch_ids]
                if not _is_circularly_contiguous(indices, len(prev_round_ids)):
                    diagnostics.append(
                        DiagramDiagnostic(
                            severity="warning",
                            code=DiagramDiagnosticCode.NON_ADJACENT_DECREASE_PARENTS,
                            message=f"symbol {symbol_id}'s decrease parents are not angularly "
                            f"adjacent in the previous round",
                            symbol_id=symbol_id,
                            round_index=diagram_round.round_index,
                            suggested_action="Verify this decrease's parent stitches manually.",
                        )
                    )

            node = StitchNode(
                stitch_id=stitch_id,
                component_kind=ComponentKind.PIECE,
                round_number=diagram_round.round_index,
                position_in_round=position,
                sequence_index=sequence_index,
                stitch_type=family,
                stitch_height_category=stitch_height_category(family),
                loop_placement=LoopPlacement.BOTH,
                parent_stitch_ids=parent_stitch_ids,
                into_ring=into_ring,
                is_increase=is_increase,
                increase_group_id=increase_group_id,
                is_decrease=is_decrease,
                decrease_group_id=decrease_group_id,
                source_reference=f"diagram round {diagram_round.round_index} symbol {symbol_id} "
                f"({symbol.classification_method.value}, confidence {symbol.confidence:.2f})",
                diagram_symbol_reference=symbol_id,
                target_rule="explicit",
            )
            nodes.append(node)
            sequence_index += 1

            for parent_stitch_id in parent_stitch_ids:
                edges.append(
                    Edge(
                        edge_id=f"{parent_stitch_id}->insertion->{stitch_id}",
                        edge_type="insertion",
                        source_id=stitch_id,
                        target_id=parent_stitch_id,
                    )
                )

            if is_increase:
                operations.append(
                    IncreaseOp(stitch=family, input=1, output=parent_usage[parent_symbol_ids[0]])
                )
            elif is_decrease:
                operations.append(DecreaseOp(stitch=family, input=len(parent_stitch_ids), output=1))
            else:
                operations.append(StitchOp(stitch=family, count=1))

        n = len(round_ids)
        if n > 1:
            for i in range(n):
                a, b = round_ids[i], round_ids[(i + 1) % n]
                edges.append(
                    Edge(
                        edge_id=f"{a}->neighbor->{b}",
                        edge_type="horizontal_neighbor",
                        source_id=a,
                        target_id=b,
                    )
                )
        if diagram_round.closure and round_ids:
            edges.append(
                Edge(
                    edge_id=f"{round_ids[-1]}->closure->{round_ids[0]}",
                    edge_type="round_closure",
                    source_id=round_ids[-1],
                    target_id=round_ids[0],
                )
            )

        rounds.append(
            Round(
                number=diagram_round.round_index,
                operations=operations,
                stated_total=len(round_ids),
                closure=ClosureKind.SLIP_STITCH_JOIN if diagram_round.closure else ClosureKind.NONE,
            )
        )
        prev_round_ids = round_ids

    unreachable = _find_unreachable(nodes)
    if unreachable:
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.DISCONNECTED_COMPONENT,
                message=f"{len(unreachable)} stitch(es) have no traceable parent chain back to "
                f"the foundation ring — this slice supports one primary connected component "
                f"only ({', '.join(unreachable[:5])}{'...' if len(unreachable) > 5 else ''})",
                suggested_action="Correct the parent relationship(s) or remove the disconnected "
                "symbols.",
            )
        )
        return None, diagnostics

    segments: list[YarnSegment] = []
    for i in range(len(nodes) - 1):
        a, b = nodes[i].stitch_id, nodes[i + 1].stitch_id
        edges.append(
            Edge(edge_id=f"{a}->seq->{b}", edge_type="yarn_sequence", source_id=a, target_id=b)
        )
        segments.append(
            YarnSegment(
                segment_id=f"seg-{a}-{b}", owning_stitch_id=b, from_stitch_id=a, to_stitch_id=b
            )
        )

    if not nodes:
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.GRAPH_VALIDATION_FAILURE,
                message="no worked-stitch nodes were compiled",
            )
        )
        return None, diagnostics

    graph = StitchGraph(
        pattern_fingerprint=None,
        nodes=nodes,
        edges=edges,
        yarn_segments=segments,
        warnings=[],
    )
    graph = graph.model_copy(update={"fingerprint": compute_graph_fingerprint(graph)})

    components = [
        Component(kind=ComponentKind.PIECE, construction=Construction.CONTINUOUS, rounds=rounds)
    ]
    return CompiledDiagram(graph=graph, components=components), diagnostics


def _find_unreachable(nodes: list[StitchNode]) -> list[str]:
    """Stitch IDs with no parent-chain path back to a round-1 (``into_ring``)
    node — this project's single-centre topology model normally guarantees
    every node reaches round 1 in exactly ``round_number - 1`` hops, so a
    failure here means an explicit connector or manual correction created a
    parent reference outside that chain (``DISCONNECTED_COMPONENT``)."""
    by_id = {n.stitch_id: n for n in nodes}
    unreachable: list[str] = []
    for node in nodes:
        if node.into_ring:
            continue
        current = node
        visited: set[str] = set()
        reached_ring = False
        for _ in range(len(nodes) + 1):
            if current.into_ring:
                reached_ring = True
                break
            if not current.parent_stitch_ids or current.stitch_id in visited:
                break
            visited.add(current.stitch_id)
            parent = by_id.get(current.parent_stitch_ids[0])
            if parent is None:
                break
            current = parent
        if not reached_ring:
            unreachable.append(node.stitch_id)
    return unreachable


def _is_circularly_contiguous(indices: list[int], n: int) -> bool:
    """Whether ``indices`` (positions within a round of ``n`` stitches) form
    one contiguous angular block, allowing wraparound past index ``n - 1``
    back to ``0`` — used to flag ``NON_ADJACENT_DECREASE_PARENTS``."""
    if len(indices) <= 1 or n <= 0:
        return True
    ordered = sorted(indices)
    gaps = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
    gaps.append(n - ordered[-1] + ordered[0])
    non_adjacent_gaps = [g for g in gaps if g != 1]
    expected_wrap_gap = n - len(indices) + 1
    return len(non_adjacent_gaps) <= 1 and (
        not non_adjacent_gaps or non_adjacent_gaps[0] == expected_wrap_gap
    )
