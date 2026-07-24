"""Versioned correction/override model and its deterministic application.

Application order (documented, not incidental — brief: "Deterministic
application order"):

1. ``constructionOverrides`` — centre/direction/start feed straight back
   into :func:`diagram.topology.infer_topology`, since changing any of them
   can invalidate round clustering and parent attachment entirely. A full
   topology re-run is the only correct way to apply them.
2. ``symbolOverrides`` — applied to the symbol list *before* that same
   topology re-run, so a corrected stitch type/round also participates in
   parent-attachment/round-clustering for every other symbol (a symbol that
   was ambiguous can be fixed and then correctly acts as a neighbour's
   parent).
3. ``relationshipOverrides`` — applied *after* the topology re-run, as
   final, explicit edits layered on top of (re-)inferred relationships —
   they never feed back into inference itself, which is what keeps this
   step order-independent and idempotent (re-applying the same correction
   set twice is a no-op).

No server-side persistence: a :class:`DiagramCorrectionSet` is only ever
carried in a single compile request/response round-trip (brief: "No
server-side persistence required").
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.diagram.ir import DiagramDocument, DiagramSymbol
from crochet_reconstruction.diagram.ontology import ClassificationMethod, DiagramStitchType

CORRECTIONS_SCHEMA_VERSION = "1.0.0"


class SymbolOverride(BaseModel):
    model_config = ConfigDict(frozen=True)

    stitch_type: DiagramStitchType | None = None
    round_index: int | None = None
    sequence_index: int | None = None
    """Desired 0-based working-order position *within the symbol's own
    round* (after any ``round_index`` override) — not a global ordinal.
    Applied as a bounded reinsertion into the round's already-inferred
    angular order (see ``topology._apply_sequence_pins``); does not move a
    symbol across rounds and clamps out-of-range values to the round's
    valid index range."""
    ignored: bool | None = None
    round_start: bool | None = None
    round_closure: bool | None = None


class RelationshipOverrideAction(StrEnum):
    SET_PARENT = "set_parent"
    REMOVE_PARENT = "remove_parent"
    ADD_PARENT = "add_parent"
    SET_CHILDREN = "set_children"
    CONFIRM = "confirm"
    RESTORE_AUTOMATIC = "restore_automatic"


class RelationshipOverride(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol_id: str
    action: RelationshipOverrideAction
    parent_symbol_ids: list[str] = Field(default_factory=list)
    child_symbol_ids: list[str] = Field(default_factory=list)


class ConstructionOverrides(BaseModel):
    model_config = ConfigDict(frozen=True)

    centre: tuple[float, float] | None = None
    direction: Literal["clockwise", "counterclockwise"] | None = None
    start_symbol_id: str | None = None
    round_tolerance: float | None = None


class DiagramCorrectionSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = CORRECTIONS_SCHEMA_VERSION
    symbol_overrides: dict[str, SymbolOverride] = Field(default_factory=dict)
    relationship_overrides: list[RelationshipOverride] = Field(default_factory=list)
    construction_overrides: ConstructionOverrides | None = None


def apply_symbol_overrides(
    document: DiagramDocument, corrections: DiagramCorrectionSet
) -> tuple[list[DiagramSymbol], list[DiagramDiagnostic]]:
    """Step 2 of the application order (see module docstring). Returns the
    corrected symbol list (ignored symbols excluded entirely) plus any
    conflict diagnostics."""
    diagnostics: list[DiagramDiagnostic] = []
    known_ids = {s.symbol_id for s in document.symbols}
    for symbol_id in corrections.symbol_overrides:
        if symbol_id not in known_ids:
            diagnostics.append(
                DiagramDiagnostic(
                    severity="error",
                    code=DiagramDiagnosticCode.MANUAL_CORRECTION_CONFLICT,
                    message=f"symbol override references unknown symbol id {symbol_id!r}",
                    symbol_id=symbol_id,
                )
            )

    corrected: list[DiagramSymbol] = []
    for symbol in document.symbols:
        override = corrections.symbol_overrides.get(symbol.symbol_id)
        if override is None:
            corrected.append(symbol)
            continue
        if override.ignored:
            continue
        update: dict[str, object] = {"user_override": True}
        if override.stitch_type is not None:
            update["stitch_type"] = override.stitch_type
            update["candidate_stitch_types"] = [override.stitch_type]
            update["classification_method"] = ClassificationMethod.MANUAL_OVERRIDE
            update["confidence"] = 1.0
            update["confidence_band"] = "manual"
            update["ambiguous"] = False
            update["unsupported"] = False
        if override.round_index is not None:
            update["round_index"] = override.round_index
        if override.sequence_index is not None:
            update["sequence_index"] = override.sequence_index
        if override.round_start is not None:
            update["round_start"] = override.round_start
        if override.round_closure is not None:
            update["round_closure"] = override.round_closure
        corrected.append(symbol.model_copy(update=update))

    return corrected, diagnostics


def apply_relationship_overrides(
    parent_map: dict[str, list[str]],
    corrections: DiagramCorrectionSet,
    known_symbol_ids: set[str],
) -> tuple[dict[str, list[str]], list[DiagramDiagnostic]]:
    """Step 3: final explicit edits over an already-(re-)inferred
    ``child_symbol_id -> [parent_symbol_id, ...]`` map. ``RESTORE_AUTOMATIC``
    and ``CONFIRM`` are no-ops on the map itself (the map already *is* the
    freshly re-inferred automatic result at this point) — they exist so the
    frontend/API round-trip can record user intent without this function
    needing separate "was this automatic" bookkeeping.
    """
    diagnostics: list[DiagramDiagnostic] = []
    result = {k: list(v) for k, v in parent_map.items()}

    for override in corrections.relationship_overrides:
        if override.symbol_id not in known_symbol_ids:
            diagnostics.append(
                DiagramDiagnostic(
                    severity="error",
                    code=DiagramDiagnosticCode.MANUAL_CORRECTION_CONFLICT,
                    message=f"relationship override references unknown symbol id "
                    f"{override.symbol_id!r}",
                    symbol_id=override.symbol_id,
                )
            )
            continue
        unknown_parents = [p for p in override.parent_symbol_ids if p not in known_symbol_ids]
        if unknown_parents:
            diagnostics.append(
                DiagramDiagnostic(
                    severity="error",
                    code=DiagramDiagnosticCode.MANUAL_CORRECTION_CONFLICT,
                    message=f"relationship override for {override.symbol_id!r} references unknown "
                    f"parent id(s) {unknown_parents}",
                    symbol_id=override.symbol_id,
                )
            )
            continue

        if override.action is RelationshipOverrideAction.SET_PARENT:
            result[override.symbol_id] = list(override.parent_symbol_ids)
        elif override.action is RelationshipOverrideAction.ADD_PARENT:
            existing = result.setdefault(override.symbol_id, [])
            for parent_id in override.parent_symbol_ids:
                if parent_id not in existing:
                    existing.append(parent_id)
        elif override.action is RelationshipOverrideAction.REMOVE_PARENT:
            existing = result.setdefault(override.symbol_id, [])
            result[override.symbol_id] = [
                p for p in existing if p not in override.parent_symbol_ids
            ]
        elif override.action is RelationshipOverrideAction.SET_CHILDREN:
            for child_id in override.child_symbol_ids:
                if child_id not in known_symbol_ids:
                    diagnostics.append(
                        DiagramDiagnostic(
                            severity="error",
                            code=DiagramDiagnosticCode.MANUAL_CORRECTION_CONFLICT,
                            message=f"relationship override references unknown child id "
                            f"{child_id!r}",
                            symbol_id=child_id,
                        )
                    )
                    continue
                existing = result.setdefault(child_id, [])
                if override.symbol_id not in existing:
                    existing.append(override.symbol_id)
        # CONFIRM / RESTORE_AUTOMATIC: no-op on the map, see docstring.

    return result, diagnostics
