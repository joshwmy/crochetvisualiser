"""Circular/radial topology inference: centre, rounds, order, parents,
increase/decrease grouping.

Produces the full semantic relationship set (parent attachment, yarn
sequence, horizontal neighbour, round closure, increase/decrease group,
centre attachment) — ``compiler.py`` only *translates* these into
``StitchGraph`` primitives, it does not re-derive them. This keeps exactly
one place in the codebase that decides "what is this chart's topology."

Parent-attachment algorithm (radial/proportional projection): when round
*r* has ``child_count`` symbols and round *r-1* has ``parent_count``, every
child index is mapped to a parent index (or contiguous block of parent
indices) by simple proportional distribution — the same "evenly spread N
things over M slots" idea as ``graph/builder.py``'s left-to-right consumption,
but driven by this round's actual angular symbol order rather than a
written pattern's aggregate operation counts. Growing (``child_count >
parent_count``) naturally produces one parent shared by several children
(increase); shrinking naturally produces one child consuming a contiguous
angular block of several parents (decrease) — contiguous by construction,
so ``NON_ADJACENT_DECREASE_PARENTS`` can only fire when an explicit
connector or correction overrides this default. See
``docs/diagram-topology-inference.md`` for the worked examples this
algorithm was checked against.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.diagram.extraction import RawConnector
from crochet_reconstruction.diagram.ir import (
    DiagramConstruction,
    DiagramRelationship,
    DiagramRound,
    DiagramSymbol,
)
from crochet_reconstruction.diagram.ontology import STRUCTURAL_STITCH_TYPES, DiagramStitchType
from crochet_reconstruction.diagram.security import SafetyLimits

Vec2 = tuple[float, float]

CONNECTOR_MATCH_TOLERANCE = 6.0
"""Normalised-unit distance within which a connector endpoint snaps to a symbol anchor."""

_FOUNDATION_TYPES = frozenset({DiagramStitchType.MAGIC_RING, DiagramStitchType.CHAIN})


def is_worked_stitch(stitch_type: DiagramStitchType | None) -> bool:
    return stitch_type is not None and stitch_type not in STRUCTURAL_STITCH_TYPES


@dataclass
class _MutableSymbol:
    symbol_id: str
    stitch_type: DiagramStitchType | None
    position: Vec2
    explicit_round: int | None
    round_start: bool
    round_closure: bool
    round_index: int | None = None
    sequence_index: int | None = None
    angle: float = 0.0
    radius: float = 0.0


@dataclass
class TopologyResult:
    construction: DiagramConstruction
    rounds: list[DiagramRound] = field(default_factory=list)
    relationships: list[DiagramRelationship] = field(default_factory=list)
    round_index_by_symbol: dict[str, int] = field(default_factory=dict)
    sequence_index_by_symbol: dict[str, int] = field(default_factory=dict)
    round_start_symbol_ids: set[str] = field(default_factory=set)
    round_closure_symbol_ids: set[str] = field(default_factory=set)
    diagnostics: list[DiagramDiagnostic] = field(default_factory=list)


def _distance(a: Vec2, b: Vec2) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _detect_centre(
    symbols: list[_MutableSymbol],
    construction: DiagramConstruction,
    diagnostics: list[DiagramDiagnostic],
) -> tuple[Vec2, str] | None:
    if construction.centre is not None:
        return construction.centre, construction.centre_method or "user_specified"

    foundation = [s for s in symbols if s.stitch_type in _FOUNDATION_TYPES]
    if len(foundation) == 1:
        return foundation[0].position, "explicit_symbol"
    if len(foundation) > 1:
        diagnostics.append(
            DiagramDiagnostic(
                severity="warning",
                code=DiagramDiagnosticCode.AMBIGUOUS_CENTRE,
                message=f"{len(foundation)} foundation-ring symbols found; using the first "
                f"({foundation[0].symbol_id}) as the chart centre",
                symbol_id=foundation[0].symbol_id,
                suggested_action="Set the chart centre explicitly if this is wrong.",
            )
        )
        return foundation[0].position, "explicit_symbol"

    worked = [s for s in symbols if is_worked_stitch(s.stitch_type)]
    if not worked:
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.MISSING_CENTRE,
                message="no foundation-ring symbol and no classified worked stitches to estimate "
                "a centre from",
                suggested_action="Mark the chart centre explicitly (magic ring/chain ring symbol "
                "or a manual centre correction).",
            )
        )
        return None

    cx = sum(s.position[0] for s in worked) / len(worked)
    cy = sum(s.position[1] for s in worked) / len(worked)
    return (cx, cy), "geometric_estimate"


def _cluster_rounds(
    symbols: list[_MutableSymbol], tolerance: float | None, diagnostics: list[DiagramDiagnostic]
) -> None:
    """Assign ``round_index`` (1-based) to every symbol with a known
    ``radius``, honouring explicit per-symbol round metadata first."""
    explicit = [s for s in symbols if s.explicit_round is not None]
    for s in explicit:
        s.round_index = s.explicit_round

    remaining = sorted((s for s in symbols if s.explicit_round is None), key=lambda s: s.radius)
    if not remaining:
        return

    radii = [s.radius for s in remaining]
    gaps = [radii[i + 1] - radii[i] for i in range(len(radii) - 1)]
    default_tolerance = (sum(gaps) / len(gaps)) * 1.5 if gaps else 1.0
    # A floor of 1% of the largest radius absorbs ordinary floating-point/
    # hand-authored-coordinate noise between symbols that are meant to be
    # the same round — without this floor, a round where most gaps are
    # exactly 0 (perfectly placed symbols) sets the gap-average tolerance
    # so tight that a single symbol off by a fraction of a percent (a
    # realistic amount of imprecision even in "clean" vector art) splits
    # off into a false extra round. 1% is a documented, overridable
    # default (``construction.round_tolerance``), not a hidden magic
    # number — see docs/diagram-topology-inference.md.
    noise_floor = max(radii) * 0.01 if radii else 0.0
    effective_tolerance = (
        tolerance if tolerance is not None else max(default_tolerance, noise_floor, 1e-6)
    )

    explicit_round_numbers = [s.explicit_round for s in explicit if s.explicit_round is not None]
    next_round = max(explicit_round_numbers, default=0) + 1
    clusters: list[list[_MutableSymbol]] = [[remaining[0]]]
    for prev, curr in zip(remaining, remaining[1:], strict=False):
        if curr.radius - prev.radius > effective_tolerance:
            clusters.append([])
        clusters[-1].append(curr)

    for cluster in clusters:
        if len(cluster) == 1 and len(clusters) > 1:
            diagnostics.append(
                DiagramDiagnostic(
                    severity="warning",
                    code=DiagramDiagnosticCode.ROUND_CLUSTERING_AMBIGUITY,
                    message=f"symbol {cluster[0].symbol_id} forms a round of its own by radial "
                    f"distance clustering — verify this is intentional",
                    symbol_id=cluster[0].symbol_id,
                    suggested_action="Assign this symbol's round explicitly if it belongs with a "
                    "neighbouring round.",
                )
            )
        for s in cluster:
            s.round_index = next_round
        next_round += 1


def _apply_sequence_pins(
    ordered: list[_MutableSymbol], pins: dict[str, int]
) -> list[_MutableSymbol]:
    """Reinsert any pinned symbol at its corrected 0-based position within
    this round's already-computed order, clamped to the valid range.

    This is the bounded, deterministic sequence-index correction: a pin only
    ever moves a symbol *within* the round it was already assigned to (round
    membership itself is governed by ``round_index``/``explicit_round``, a
    separate correction) — it never invents a global, gap-tolerant ordinal.
    Multiple pins in the same round are applied in ascending target-index
    order so the result does not depend on symbol-id iteration order
    (idempotent/deterministic — see corrections.py's module docstring).
    """
    round_pins = {sid: idx for sid, idx in pins.items() if any(s.symbol_id == sid for s in ordered)}
    if not round_pins:
        return ordered

    result = [s for s in ordered if s.symbol_id not in round_pins]
    pinned_symbols = sorted(
        (s for s in ordered if s.symbol_id in round_pins), key=lambda s: round_pins[s.symbol_id]
    )
    for symbol in pinned_symbols:
        target = max(0, min(round_pins[symbol.symbol_id], len(result)))
        result.insert(target, symbol)
    return result


def _order_round(
    symbols: list[_MutableSymbol],
    centre: Vec2,
    direction: str,
    start_symbol_id: str | None,
    sequence_pins: dict[str, int] | None = None,
) -> list[_MutableSymbol]:
    for s in symbols:
        s.angle = math.atan2(s.position[1] - centre[1], s.position[0] - centre[0])
    ordered = sorted(symbols, key=lambda s: (s.angle, s.symbol_id))
    if direction == "counterclockwise":
        ordered = list(reversed(ordered))

    start_id = start_symbol_id or next((s.symbol_id for s in ordered if s.round_start), None)
    if start_id is not None:
        ids = [s.symbol_id for s in ordered]
        if start_id in ids:
            offset = ids.index(start_id)
            ordered = ordered[offset:] + ordered[:offset]

    if sequence_pins:
        ordered = _apply_sequence_pins(ordered, sequence_pins)
    return ordered


def _distribute(child_count: int, parent_count: int, index: int) -> tuple[int, int]:
    """Half-open ``[start, end)`` parent-index block for child ``index`` out
    of ``child_count``, distributed proportionally over ``parent_count``."""
    start = (index * parent_count) // child_count
    end = ((index + 1) * parent_count) // child_count
    return start, max(end, start + 1)


def _resolve_connectors(
    symbols: list[_MutableSymbol],
    connectors: list[RawConnector],
    diagnostics: list[DiagramDiagnostic],
) -> dict[str, list[str]]:
    """``child_symbol_id -> [parent_symbol_id, ...]`` from explicit connector
    geometry — highest-priority evidence, overriding proportional projection
    for exactly the symbols it names."""
    explicit_parents: dict[str, list[str]] = {}
    for connector in connectors:
        from_symbol = min(
            symbols, key=lambda s: _distance(s.position, connector.from_point), default=None
        )
        to_symbol = min(
            symbols, key=lambda s: _distance(s.position, connector.to_point), default=None
        )
        if (
            from_symbol is None
            or to_symbol is None
            or _distance(from_symbol.position, connector.from_point) > CONNECTOR_MATCH_TOLERANCE
            or _distance(to_symbol.position, connector.to_point) > CONNECTOR_MATCH_TOLERANCE
        ):
            diagnostics.append(
                DiagramDiagnostic(
                    severity="warning",
                    code=DiagramDiagnosticCode.INVALID_CONNECTOR,
                    message=f"connector at {connector.element_path} does not land on any known "
                    f"symbol within tolerance",
                    element_path=connector.element_path,
                    suggested_action="Snap the connector's endpoints to symbol anchors.",
                )
            )
            continue
        # Parent = whichever endpoint is nearer the chart centre in round
        # order; the outer/later symbol is the child.
        parent, child = (
            (from_symbol, to_symbol)
            if (from_symbol.round_index or 0) < (to_symbol.round_index or 0)
            else (to_symbol, from_symbol)
        )
        explicit_parents.setdefault(child.symbol_id, []).append(parent.symbol_id)
    return explicit_parents


def infer_topology(
    symbols_in: list[DiagramSymbol],
    connectors: list[RawConnector],
    construction: DiagramConstruction,
    limits: SafetyLimits,
    *,
    explicit_parent_overrides: dict[str, list[str]] | None = None,
    sequence_pins: dict[str, int] | None = None,
) -> TopologyResult:
    """``explicit_parent_overrides`` lets a corrected re-run (``pipeline.py``'s
    compile path, which has no raw SVG/connector geometry — only the
    previously analysed ``DiagramDocument``) re-supply connector-derived
    parent bindings from the original analysis without needing that raw
    geometry again. Analyse-time callers pass ``connectors`` instead and
    leave this ``None``.

    ``sequence_pins`` (``symbol_id -> desired 0-based index within its own
    round``) carries manual sequence-index corrections into round ordering
    — see ``_apply_sequence_pins`` for the exact, bounded semantics."""
    diagnostics: list[DiagramDiagnostic] = []

    mutable = [
        _MutableSymbol(
            symbol_id=s.symbol_id,
            stitch_type=s.stitch_type,
            position=s.position,
            explicit_round=s.round_index if s.round_index is not None else _read_explicit_round(s),
            round_start=s.round_start,
            round_closure=s.round_closure,
        )
        for s in symbols_in
    ]

    if construction.mode.value != "circular":
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.UNSUPPORTED_CHART_CONSTRUCTION,
                message=f"construction mode {construction.mode.value!r} is not supported this "
                f"slice — only circular/radial charts are",
            )
        )
        return TopologyResult(construction=construction, diagnostics=diagnostics)

    centre_result = _detect_centre(mutable, construction, diagnostics)
    if centre_result is None:
        return TopologyResult(construction=construction, diagnostics=diagnostics)
    centre, centre_method = centre_result

    for s in mutable:
        s.radius = _distance(s.position, centre)

    # Only worked stitches are clustered into numbered rounds — the
    # foundation ring/chain (if any) is round 0 conceptually (referenced
    # directly by symbol id via centre_attachment) and must never consume a
    # round-number slot, or every real round number would be off by one.
    relevant = [s for s in mutable if is_worked_stitch(s.stitch_type)]
    _cluster_rounds(relevant, construction.round_tolerance, diagnostics)

    round_numbers = sorted({s.round_index for s in relevant if s.round_index is not None})

    direction = construction.direction or "clockwise"
    ordered_by_round: dict[int, list[_MutableSymbol]] = {}
    for round_number in round_numbers:
        members = [
            s for s in relevant if s.round_index == round_number and is_worked_stitch(s.stitch_type)
        ]
        start_id = construction.start_symbol_id if round_number == round_numbers[0] else None
        ordered_by_round[round_number] = _order_round(
            members, centre, direction, start_id, sequence_pins
        )

    total_stitches = sum(len(v) for v in ordered_by_round.values())
    if total_stitches > limits.max_inferred_stitches:
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
                message=f"inferred stitch count {total_stitches} exceeds limit "
                f"{limits.max_inferred_stitches}",
            )
        )
        return TopologyResult(construction=construction, diagnostics=diagnostics)

    explicit_parents = _resolve_connectors(mutable, connectors, diagnostics)
    if explicit_parent_overrides:
        explicit_parents.update(explicit_parent_overrides)

    relationships: list[DiagramRelationship] = []
    round_index_by_symbol: dict[str, int] = {}
    sequence_index_by_symbol: dict[str, int] = {}
    round_start_symbol_ids: set[str] = set()
    round_closure_symbol_ids: set[str] = set()
    seq = 0
    rel_counter = 0

    def next_rel_id() -> str:
        nonlocal rel_counter
        rel_counter += 1
        return f"rel-{rel_counter:05d}"

    foundation_id = next((s.symbol_id for s in mutable if s.stitch_type in _FOUNDATION_TYPES), None)

    diagram_rounds: list[DiagramRound] = []
    for round_number in round_numbers:
        members = ordered_by_round[round_number]
        symbol_ids = [s.symbol_id for s in members]
        for i, s in enumerate(members):
            round_index_by_symbol[s.symbol_id] = round_number
            sequence_index_by_symbol[s.symbol_id] = seq
            seq += 1
            if i == 0:
                round_start_symbol_ids.add(s.symbol_id)

            explicit = explicit_parents.get(s.symbol_id)
            if explicit:
                parent_ids = explicit
                method = "explicit_connector"
                confidence = 1.0
            elif round_number == round_numbers[0]:
                parent_ids = [foundation_id] if foundation_id else []
                method = "explicit_metadata" if foundation_id else "nearest_previous_round"
                confidence = (
                    0.9 if centre_method in ("explicit_symbol", "explicit_metadata") else 0.5
                )
                relationships.append(
                    DiagramRelationship(
                        relationship_id=next_rel_id(),
                        source_symbol_ids=[s.symbol_id],
                        target_symbol_ids=parent_ids,
                        relationship_type="centre_attachment",
                        inference_method=method,  # type: ignore[arg-type]
                        confidence=confidence,
                        evidence=f"round-1 symbol attaches to chart centre ({centre_method})",
                    )
                )
                continue
            else:
                prev_round = ordered_by_round[round_numbers[round_numbers.index(round_number) - 1]]
                if not prev_round:
                    parent_ids = []
                    method = "nearest_previous_round"
                    confidence = 0.0
                else:
                    start, end = _distribute(len(members), len(prev_round), i)
                    parent_ids = [prev_round[j].symbol_id for j in range(start, end)]
                    method = "radial_projection"
                    confidence = 0.5

            if not parent_ids:
                diagnostics.append(
                    DiagramDiagnostic(
                        severity="error",
                        code=DiagramDiagnosticCode.MISSING_PARENT,
                        message=f"symbol {s.symbol_id} has no resolvable parent in the previous "
                        f"round",
                        symbol_id=s.symbol_id,
                        round_index=round_number,
                        suggested_action="Add an explicit connector or manual parent correction.",
                    )
                )
            relationships.append(
                DiagramRelationship(
                    relationship_id=next_rel_id(),
                    source_symbol_ids=[s.symbol_id],
                    target_symbol_ids=parent_ids,
                    relationship_type="parent_attachment",
                    inference_method=method,  # type: ignore[arg-type]
                    confidence=confidence,
                    evidence=f"{method} from round {round_number - 1} to round {round_number}",
                )
            )

        for i in range(len(members)):
            a, b = members[i], members[(i + 1) % len(members)]
            if len(members) > 1:
                relationships.append(
                    DiagramRelationship(
                        relationship_id=next_rel_id(),
                        source_symbol_ids=[a.symbol_id],
                        target_symbol_ids=[b.symbol_id],
                        relationship_type="horizontal_neighbor",
                        inference_method="radial_projection",
                        confidence=1.0,
                        evidence="adjacent in angular round order",
                    )
                )

        closure_symbol = next((s for s in members if s.round_closure), None)
        if closure_symbol is not None:
            round_closure_symbol_ids.add(closure_symbol.symbol_id)
            relationships.append(
                DiagramRelationship(
                    relationship_id=next_rel_id(),
                    source_symbol_ids=[symbol_ids[-1]],
                    target_symbol_ids=[symbol_ids[0]],
                    relationship_type="round_closure",
                    inference_method="explicit_metadata",
                    confidence=1.0,
                    evidence=f"explicit round-closure symbol {closure_symbol.symbol_id}",
                )
            )

        diagram_rounds.append(
            DiagramRound(
                round_index=round_number,
                symbol_ids=symbol_ids,
                centre_distance_avg=sum(s.radius for s in members) / len(members)
                if members
                else None,
                start_symbol_id=symbol_ids[0] if symbol_ids else None,
                closure=closure_symbol is not None,
            )
        )

    for i in range(len(round_numbers) - 1):
        a_round = ordered_by_round[round_numbers[i]]
        b_round = ordered_by_round[round_numbers[i + 1]]
        if a_round and b_round:
            relationships.append(
                DiagramRelationship(
                    relationship_id=next_rel_id(),
                    source_symbol_ids=[a_round[0].symbol_id],
                    target_symbol_ids=[b_round[0].symbol_id],
                    relationship_type="yarn_sequence",
                    inference_method="radial_projection",
                    confidence=1.0,
                    evidence="round-to-round working order",
                )
            )

    if len(relationships) > limits.max_inferred_edges:
        diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
                message=f"inferred relationship count exceeds limit {limits.max_inferred_edges}",
            )
        )
        return TopologyResult(construction=construction, diagnostics=diagnostics)

    updated_construction = construction.model_copy(
        update={
            "centre": centre,
            "centre_method": centre_method,
            "direction": direction,
        }
    )

    return TopologyResult(
        construction=updated_construction,
        rounds=diagram_rounds,
        relationships=relationships,
        round_index_by_symbol=round_index_by_symbol,
        sequence_index_by_symbol=sequence_index_by_symbol,
        round_start_symbol_ids=round_start_symbol_ids,
        round_closure_symbol_ids=round_closure_symbol_ids,
        diagnostics=diagnostics,
    )


def _read_explicit_round(symbol: DiagramSymbol) -> int | None:
    raw = symbol.source_metadata.get("data-round")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
