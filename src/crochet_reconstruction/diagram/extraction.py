"""Symbol candidate discovery and the deterministic classification
priority order (brief: "Never let a low-confidence geometric heuristic
override explicit metadata").

Priority order, highest first (see ``ontology.ClassificationMethod``):

1. ``data-stitch-type`` attribute
2. ``<use href="#...">`` whose target id/naming is a known symbol reference
3. the element's own supported id
4. the element's own supported CSS class
5. ``<title>`` child text
6. ``aria-label`` attribute
7. text-label association — **not implemented this slice** (documented
   simplification; falls through to geometry, see
   ``docs/diagram-symbol-ontology.md``)
8. primitive geometry heuristic (``classification.py``)
9. unclassified

Containers (``<defs>``/``<symbol>``) are never scanned directly — their
content is only a candidate once instantiated via ``<use>`` (see
``svg_parser.py``'s docstring on why the same subtree otherwise appears
twice). Explicit attachment/connector lines are recognised separately and
never treated as stitch symbols.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from crochet_reconstruction.diagram.classification import (
    PrimitiveClassification,
    classify_primitive,
    classify_strokes,
    extract_path_strokes,
)
from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.diagram.ir import DiagramSymbol
from crochet_reconstruction.diagram.ontology import (
    CONFIDENCE_BY_METHOD,
    ClassificationMethod,
    DiagramStitchType,
    confidence_band,
    resolve_label_token,
    resolve_reserved_future_token,
)
from crochet_reconstruction.diagram.security import SafetyLimits
from crochet_reconstruction.diagram.svg_parser import NormalizedElement

Vec2 = tuple[float, float]
BBox = tuple[float, float, float, float]

_SKIPPED_CONTAINERS = frozenset({"defs", "symbol", "title", "desc", "metadata"})
_PRIMITIVE_TAGS = frozenset({"circle", "ellipse", "rect", "path", "polyline", "polygon", "line"})
_NUMBER_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?")


@dataclass(frozen=True)
class RawConnector:
    element_path: str
    source_element_id: str | None
    from_point: Vec2
    to_point: Vec2


@dataclass
class ExtractionResult:
    symbols: list[DiagramSymbol] = field(default_factory=list)
    connectors: list[RawConnector] = field(default_factory=list)
    diagnostics: list[DiagramDiagnostic] = field(default_factory=list)


def _is_connector(attrib: dict[str, str]) -> bool:
    if attrib.get("data-connector") == "true":
        return True
    classes = attrib.get("class", "").lower().split()
    return "connector" in classes or "attachment-line" in classes


def _local_geometry_points(tag: str, attrib: dict[str, str]) -> list[Vec2]:
    try:
        if tag == "circle":
            cx, cy, r = (
                float(attrib.get("cx", 0)),
                float(attrib.get("cy", 0)),
                float(attrib.get("r", 0)),
            )
            return [(cx - r, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx + r, cy - r)]
        if tag == "ellipse":
            cx, cy = float(attrib.get("cx", 0)), float(attrib.get("cy", 0))
            rx, ry = float(attrib.get("rx", 0)), float(attrib.get("ry", 0))
            return [(cx - rx, cy - ry), (cx + rx, cy + ry), (cx - rx, cy + ry), (cx + rx, cy - ry)]
        if tag == "rect":
            x, y = float(attrib.get("x", 0)), float(attrib.get("y", 0))
            w, h = float(attrib.get("width", 0)), float(attrib.get("height", 0))
            return [(x, y), (x + w, y + h)]
        if tag == "line":
            return [
                (float(attrib.get("x1", 0)), float(attrib.get("y1", 0))),
                (float(attrib.get("x2", 0)), float(attrib.get("y2", 0))),
            ]
        if tag in ("polyline", "polygon") and "points" in attrib:
            numbers = [float(n) for n in _NUMBER_RE.findall(attrib["points"])]
            return [(numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2)]
        if tag == "path" and "d" in attrib:
            numbers = [float(n) for n in _NUMBER_RE.findall(attrib["d"])]
            return [(numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2)]
    except ValueError:
        return []
    return []


def _geometry_points(element: NormalizedElement) -> list[Vec2]:
    local = _local_geometry_points(element.tag, element.attrib)
    points = [element.transform.apply(x, y) for x, y in local]
    for child in element.children:
        points.extend(_geometry_points(child))
    return points


def _bbox_and_anchor(element: NormalizedElement) -> tuple[BBox, Vec2] | None:
    points = _geometry_points(element)
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    bbox: BBox = (min(xs), min(ys), max(xs), max(ys))
    anchor = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    return bbox, anchor


def collect_strokes_for_classification(
    element: NormalizedElement,
) -> list[tuple[Vec2, Vec2]] | None:
    """Straight-line strokes for a candidate authored as one path or as
    several sibling line-like primitives with no further relative
    transform (this project's synthetic-fixture authoring convention —
    see module docstring and ``docs/diagram-symbol-ontology.md``)."""
    if element.tag == "path" and "d" in element.attrib:
        return extract_path_strokes(element.attrib["d"])
    if element.tag == "line":
        try:
            x1, y1 = float(element.attrib.get("x1", 0)), float(element.attrib.get("y1", 0))
            x2, y2 = float(element.attrib.get("x2", 0)), float(element.attrib.get("y2", 0))
        except ValueError:
            return None
        return [((x1, y1), (x2, y2))]
    if element.tag in ("g", "use") and element.children:
        strokes: list[tuple[Vec2, Vec2]] = []
        for child in element.children:
            child_strokes = collect_strokes_for_classification(child)
            if child_strokes is None:
                return None
            strokes.extend(child_strokes)
        return strokes or None
    return None


def classify_candidate_geometry(element: NormalizedElement) -> PrimitiveClassification:
    if element.tag in ("circle", "ellipse", "rect"):
        return classify_primitive(element.tag, element.attrib)
    if (
        element.tag in ("g", "use")
        and len(element.children) == 1
        and element.children[0].tag in ("circle", "ellipse", "rect")
    ):
        return classify_primitive(element.children[0].tag, element.children[0].attrib)
    strokes = collect_strokes_for_classification(element)
    if strokes is None:
        return PrimitiveClassification(candidates=[])
    return classify_strokes(strokes)


def _try_metadata_classification(
    element: NormalizedElement,
) -> tuple[ClassificationMethod, str | None, str] | None:
    """Returns ``(method, matched_stitch_type_value_or_None, raw_token)``.

    ``matched_stitch_type_value_or_None`` is ``None`` when the token was
    recognised as *present* (so this method still wins per priority order)
    but didn't resolve to any known/reserved type — the caller turns that
    into an ``UNCLASSIFIED``/``UNSUPPORTED`` outcome without falling
    through to a lower-priority method, matching "never let a low-
    confidence heuristic override explicit metadata" even when the
    explicit metadata itself is unrecognised.
    """
    attrib = element.attrib
    if "data-stitch-type" in attrib:
        token = attrib["data-stitch-type"]
        resolved = resolve_label_token(token)
        return ClassificationMethod.DATA_ATTRIBUTE, resolved.value if resolved else None, token

    if element.tag == "use" and element.used_symbol_id:
        resolved = resolve_label_token(element.used_symbol_id)
        if resolved:
            return ClassificationMethod.USE_REFERENCE, resolved.value, element.used_symbol_id

    if "id" in attrib:
        resolved = resolve_label_token(attrib["id"])
        if resolved:
            return ClassificationMethod.ELEMENT_ID, resolved.value, attrib["id"]

    if "class" in attrib:
        for token in attrib["class"].split():
            resolved = resolve_label_token(token)
            if resolved:
                return ClassificationMethod.CSS_CLASS, resolved.value, token

    for child in element.children:
        if child.tag == "title" and child.text:
            resolved = resolve_label_token(child.text)
            return ClassificationMethod.TITLE, resolved.value if resolved else None, child.text

    if "aria-label" in attrib:
        token = attrib["aria-label"]
        resolved = resolve_label_token(token)
        return ClassificationMethod.ARIA_LABEL, resolved.value if resolved else None, token

    return None


def _make_symbol(
    element: NormalizedElement,
    *,
    symbol_index: int,
    method: ClassificationMethod,
    stitch_type_value: str | None,
    candidates: list[str],
    raw_evidence: str | None,
) -> DiagramSymbol:
    bbox_anchor = _bbox_and_anchor(element)
    if bbox_anchor is not None:
        bbox, anchor = bbox_anchor
    else:
        # No drawn geometry under this candidate (e.g. a metadata-only <g>
        # with no visible shape) — fall back to the element's own local
        # origin under its composed transform, which is where a chart
        # author's `transform="translate(x,y)"` placement is expressed.
        anchor = element.transform.apply(0.0, 0.0)
        bbox = (anchor[0], anchor[1], anchor[0], anchor[1])
    orientation_deg = math.degrees(math.atan2(element.transform.b, element.transform.a))

    resolved_type = DiagramStitchType(stitch_type_value) if stitch_type_value else None
    candidate_types = [DiagramStitchType(c) for c in candidates]
    ambiguous = resolved_type is None and len(candidate_types) > 1
    unsupported = False

    metadata_methods = (
        ClassificationMethod.DATA_ATTRIBUTE,
        ClassificationMethod.ELEMENT_ID,
        ClassificationMethod.CSS_CLASS,
        ClassificationMethod.TITLE,
        ClassificationMethod.ARIA_LABEL,
    )
    if (
        resolved_type is None
        and method in metadata_methods
        and raw_evidence
        and resolve_reserved_future_token(raw_evidence) is not None
    ):
        unsupported = True

    confidence = CONFIDENCE_BY_METHOD[method] if resolved_type is not None else 0.0
    metadata: dict[str, str] = {}
    for key in ("data-stitch-type", "id", "class", "aria-label", "data-round"):
        if key in element.attrib:
            metadata[key] = element.attrib[key]
    if raw_evidence:
        metadata["matched_token"] = raw_evidence

    return DiagramSymbol(
        symbol_id=f"svg-symbol-{symbol_index}",
        stitch_type=resolved_type,
        candidate_stitch_types=candidate_types,
        source_element_id=element.attrib.get("id"),
        source_element_path=element.element_path,
        source_metadata=metadata,
        position=anchor,
        bbox=bbox,
        anchor=anchor,
        orientation_deg=orientation_deg,
        scale=element.transform.uniform_scale,
        classification_method=method,
        confidence=confidence,
        confidence_band=confidence_band(confidence, is_manual=False),
        ambiguous=ambiguous,
        unsupported=unsupported,
    )


def _walk_for_candidates(
    element: NormalizedElement,
    *,
    result: ExtractionResult,
    limits: SafetyLimits,
    counter: list[int],
    seen_ids: dict[str, str],
) -> None:
    if element.tag in _SKIPPED_CONTAINERS:
        return
    if element.tag == "text":
        return  # round labels / free text: not treated as symbols this slice

    if _is_connector(element.attrib):
        points = _geometry_points(element)
        if len(points) >= 2:
            result.connectors.append(
                RawConnector(
                    element_path=element.element_path,
                    source_element_id=element.attrib.get("id"),
                    from_point=points[0],
                    to_point=points[-1],
                )
            )
        else:
            result.diagnostics.append(
                DiagramDiagnostic(
                    severity="warning",
                    code=DiagramDiagnosticCode.INVALID_CONNECTOR,
                    message="connector element has no resolvable geometry",
                    element_path=element.element_path,
                )
            )
        return

    metadata_match = _try_metadata_classification(element)
    if metadata_match is not None:
        method, stitch_type_value, raw_evidence = metadata_match
        _emit_symbol(
            element,
            result=result,
            limits=limits,
            counter=counter,
            seen_ids=seen_ids,
            method=method,
            stitch_type_value=stitch_type_value,
            candidates=[stitch_type_value] if stitch_type_value else [],
            raw_evidence=raw_evidence,
        )
        return

    if element.tag in _PRIMITIVE_TAGS or (element.tag in ("g", "use") and element.children):
        classification = classify_candidate_geometry(element)
        is_leaf_shape = element.tag in _PRIMITIVE_TAGS or (
            element.tag in ("g", "use")
            and all(child.tag in _PRIMITIVE_TAGS for child in element.children)
            and element.children
        )
        if is_leaf_shape and classification.candidates:
            _emit_symbol(
                element,
                result=result,
                limits=limits,
                counter=counter,
                seen_ids=seen_ids,
                method=ClassificationMethod.PRIMITIVE_GEOMETRY,
                stitch_type_value=classification.candidates[0].value
                if len(classification.candidates) == 1
                else None,
                candidates=[c.value for c in classification.candidates],
                raw_evidence=None,
            )
            return
        if is_leaf_shape and element.tag in _PRIMITIVE_TAGS:
            _emit_symbol(
                element,
                result=result,
                limits=limits,
                counter=counter,
                seen_ids=seen_ids,
                method=ClassificationMethod.UNCLASSIFIED,
                stitch_type_value=None,
                candidates=[],
                raw_evidence=None,
            )
            return

    for child in element.children:
        _walk_for_candidates(
            child, result=result, limits=limits, counter=counter, seen_ids=seen_ids
        )


def _emit_symbol(
    element: NormalizedElement,
    *,
    result: ExtractionResult,
    limits: SafetyLimits,
    counter: list[int],
    seen_ids: dict[str, str],
    method: ClassificationMethod,
    stitch_type_value: str | None,
    candidates: list[str],
    raw_evidence: str | None,
) -> None:
    if len(result.symbols) >= limits.max_symbol_candidates:
        result.diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
                message=f"symbol candidate count exceeds limit {limits.max_symbol_candidates}",
                element_path=element.element_path,
            )
        )
        return

    element_id = element.attrib.get("id")
    if element_id is not None:
        if element_id in seen_ids:
            result.diagnostics.append(
                DiagramDiagnostic(
                    severity="error",
                    code=DiagramDiagnosticCode.DUPLICATE_SYMBOL_ID,
                    message=f"element id {element_id!r} is used by more than one symbol",
                    svg_element_id=element_id,
                    element_path=element.element_path,
                )
            )
            return
        seen_ids[element_id] = element.element_path

    symbol = _make_symbol(
        element,
        symbol_index=counter[0],
        method=method,
        stitch_type_value=stitch_type_value,
        candidates=candidates,
        raw_evidence=raw_evidence,
    )
    counter[0] += 1
    result.symbols.append(symbol)

    if symbol.stitch_type is None and symbol.unsupported:
        result.diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.UNSUPPORTED_SYMBOL,
                message=f"symbol {symbol.symbol_id} uses a recognised-but-unsupported stitch type "
                f"({raw_evidence!r}) — reserved for a future slice",
                symbol_id=symbol.symbol_id,
                element_path=element.element_path,
                confidence=symbol.confidence,
                suggested_action="Correct this symbol's stitch type manually before compiling.",
            )
        )
    elif symbol.ambiguous:
        # error, not warning: an ambiguous symbol has stitch_type=None, so
        # it would otherwise be silently excluded from topology/compile
        # (is_worked_stitch(None) is False) with no build-breaking signal
        # other than this diagnostic — "never silently force an uncertain
        # symbol into a class" cuts both ways: it must not silently drop
        # one either. Compile stays blocked until corrected or explicitly
        # marked ignored.
        result.diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.AMBIGUOUS_SYMBOL,
                message=f"symbol {symbol.symbol_id} matches multiple plausible stitch types: "
                f"{', '.join(candidates)}",
                symbol_id=symbol.symbol_id,
                element_path=element.element_path,
                confidence=symbol.confidence,
                suggested_action="Choose the correct stitch type manually.",
            )
        )
    elif symbol.stitch_type is None:
        result.diagnostics.append(
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.UNCLASSIFIED_SYMBOL,
                message=f"symbol {symbol.symbol_id} could not be classified from its metadata "
                f"or shape",
                symbol_id=symbol.symbol_id,
                element_path=element.element_path,
                confidence=symbol.confidence,
                suggested_action="Assign this symbol's stitch type manually.",
            )
        )
    elif symbol.confidence < 0.5:
        result.diagnostics.append(
            DiagramDiagnostic(
                severity="info",
                code=DiagramDiagnosticCode.AMBIGUOUS_SYMBOL,
                message=f"symbol {symbol.symbol_id} was classified with low confidence "
                f"({symbol.confidence:.2f}) and should be reviewed",
                symbol_id=symbol.symbol_id,
                element_path=element.element_path,
                confidence=symbol.confidence,
                suggested_action="Review and confirm this symbol's stitch type.",
            )
        )


def extract_symbols(root: NormalizedElement, limits: SafetyLimits) -> ExtractionResult:
    result = ExtractionResult()
    counter = [0]
    seen_ids: dict[str, str] = {}
    for child in root.children:
        _walk_for_candidates(
            child, result=result, limits=limits, counter=counter, seen_ids=seen_ids
        )
    return result
