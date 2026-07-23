"""Hardened SVG parsing, sanitisation, safety-limit enforcement, and
transform-normalisation into a :class:`NormalizedDocument`.

Security posture: **any** violation (disallowed tag/attribute, external
reference, oversized/over-nested/over-counted content, unparseable
transform) fails the **whole** document with a structured diagnostic. No
partial "strip the bad bits and continue" mode — a document this hardened
parser can't fully vouch for never reaches symbol extraction, let alone the
frontend (see ``docs/svg-security.md``, "Fail closed, not strip-and-hope").

Uses ``defusedxml`` (MIT-licensed, the standard Python answer to XXE/entity-
expansion/DTD attacks — see ``docs/open-source-resource-adoption.md``) with
DTDs, external entities, and external references all explicitly forbidden,
on top of this module's own element-count/nesting/coordinate/path-command
bounds, which ``defusedxml`` itself does not enforce.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError as DefusedParseError
from defusedxml.ElementTree import fromstring as defused_fromstring

from crochet_reconstruction.diagram.diagnostics import DiagramDiagnostic, DiagramDiagnosticCode
from crochet_reconstruction.diagram.security import (
    DISALLOWED_ATTRIBUTE_PREFIXES,
    DISALLOWED_TAGS,
    DISALLOWED_VALUE_SUBSTRINGS,
    HREF_ATTRIBUTES,
    SafetyLimits,
)
from crochet_reconstruction.diagram.transforms import (
    IDENTITY,
    Matrix2D,
    TransformParseError,
    ViewBox,
    parse_transform_list,
    parse_viewbox,
)

_NUMBER_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?")
_PATH_COMMAND_RE = re.compile(r"[MLHVCSQTAZmlhvcsqtaz]")
_PX_SUFFIX_RE = re.compile(r"px\s*$")


class SvgSecurityError(Exception):
    """Raised internally during the walk; always caught and converted to a
    :class:`DiagramDiagnostic` by :func:`parse_svg` — never propagated."""

    def __init__(
        self, code: DiagramDiagnosticCode, message: str, *, element_path: str | None = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.element_path = element_path


@dataclass(frozen=True)
class NormalizedElement:
    """One SVG element with its tag/attributes as authored, plus the fully
    composed transform (root viewBox normalisation * every ancestor
    transform * this element's own) needed to place its geometry in the
    single normalised coordinate system every downstream stage uses."""

    tag: str
    attrib: dict[str, str]
    children: list[NormalizedElement]
    transform: Matrix2D
    element_path: str
    text: str | None = None
    used_symbol_id: str | None = None


@dataclass(frozen=True)
class NormalizedDocument:
    root: NormalizedElement
    width: float
    height: float
    view_box: ViewBox
    fingerprint: str


@dataclass
class _WalkState:
    limits: SafetyLimits
    element_count: int = 0
    use_count: int = 0
    id_map: dict[str, ET.Element] = field(default_factory=dict)


def _local_tag(element: ET.Element) -> str:
    tag = element.tag
    if isinstance(tag, str) and "}" in tag:
        return tag.rsplit("}", 1)[1]
    return str(tag)


def _local_attrib(element: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in element.attrib.items():
        local = key.rsplit("}", 1)[1] if "}" in key else key
        out[local] = value
    return out


def _check_numbers(text: str, limits: SafetyLimits, element_path: str) -> None:
    for raw in _NUMBER_RE.findall(text):
        try:
            value = float(raw)
        except ValueError:
            continue
        if abs(value) > limits.max_coordinate_magnitude:
            raise SvgSecurityError(
                DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE,
                f"coordinate magnitude {value} exceeds limit {limits.max_coordinate_magnitude}",
                element_path=element_path,
            )


def _check_disallowed_attrs(
    attrib: dict[str, str], limits: SafetyLimits, element_path: str
) -> None:
    for key, value in attrib.items():
        lower_key = key.lower()
        if (
            any(lower_key.startswith(p) for p in DISALLOWED_ATTRIBUTE_PREFIXES)
            and lower_key != "opacity"
        ):
            raise SvgSecurityError(
                DiagramDiagnosticCode.UNSAFE_SVG_CONTENT,
                f"disallowed event-handler-like attribute {key!r}",
                element_path=element_path,
            )
        lower_value = value.lower()
        if any(bad in lower_value for bad in DISALLOWED_VALUE_SUBSTRINGS):
            raise SvgSecurityError(
                DiagramDiagnosticCode.UNSAFE_SVG_CONTENT,
                f"disallowed value content in attribute {key!r}",
                element_path=element_path,
            )
        if len(value) > 20_000:
            raise SvgSecurityError(
                DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE,
                f"attribute {key!r} value implausibly long ({len(value)} chars)",
                element_path=element_path,
            )
    for href_attr in HREF_ATTRIBUTES:
        if href_attr in attrib:
            href = attrib[href_attr]
            if not href.startswith("#"):
                raise SvgSecurityError(
                    DiagramDiagnosticCode.UNSUPPORTED_EXTERNAL_REFERENCE,
                    f"non-local reference {href!r} is not permitted",
                    element_path=element_path,
                )


def _index_ids(root: ET.Element, id_map: dict[str, ET.Element], limits: SafetyLimits) -> None:
    """Iterative (not recursive) so a maliciously deep — not just
    maliciously wide — document can never raise Python's own
    ``RecursionError`` before this module's own element-count/nesting
    checks (enforced later, in ``_walk``) get a chance to reject it with a
    structured diagnostic instead."""
    stack = [root]
    visited = 0
    # A generous multiple of max_element_count: this pass runs before
    # `_walk`'s own precise per-element accounting, so it only needs to
    # bound total work here, not produce the exact diagnostic — `_walk`
    # still raises the authoritative TOO_MANY_ELEMENTS error afterward.
    hard_cap = limits.max_element_count * 4
    while stack:
        element = stack.pop()
        visited += 1
        if visited > hard_cap:
            raise SvgSecurityError(
                DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
                f"element count exceeds limit {limits.max_element_count}",
            )
        element_id = element.attrib.get("id")
        if element_id is not None:
            id_map[element_id] = element
        stack.extend(element)


def _own_transform(attrib: dict[str, str], limits: SafetyLimits, element_path: str) -> Matrix2D:
    raw = attrib.get("transform")
    if not raw:
        return IDENTITY
    try:
        return parse_transform_list(raw, max_functions=limits.max_transform_nesting)
    except TransformParseError as exc:
        raise SvgSecurityError(
            DiagramDiagnosticCode.TRANSFORM_FAILURE, str(exc), element_path=element_path
        ) from exc


def _walk(
    element: ET.Element,
    *,
    state: _WalkState,
    parent_transform: Matrix2D,
    element_path: str,
    depth: int,
    use_chain: frozenset[str],
) -> NormalizedElement:
    state.element_count += 1
    if state.element_count > state.limits.max_element_count:
        raise SvgSecurityError(
            DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
            f"element count exceeds limit {state.limits.max_element_count}",
            element_path=element_path,
        )
    if depth > state.limits.max_nesting_depth:
        raise SvgSecurityError(
            DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE,
            f"nesting depth exceeds limit {state.limits.max_nesting_depth}",
            element_path=element_path,
        )

    tag = _local_tag(element)
    if tag in DISALLOWED_TAGS:
        raise SvgSecurityError(
            DiagramDiagnosticCode.UNSAFE_SVG_CONTENT,
            f"disallowed element <{tag}>",
            element_path=element_path,
        )

    attrib = _local_attrib(element)
    _check_disallowed_attrs(attrib, state.limits, element_path)

    if tag == "path" and "d" in attrib:
        command_count = len(_PATH_COMMAND_RE.findall(attrib["d"]))
        if command_count > state.limits.max_path_commands_per_element:
            raise SvgSecurityError(
                DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE,
                f"path has {command_count} commands, exceeding limit "
                f"{state.limits.max_path_commands_per_element}",
                element_path=element_path,
            )
        _check_numbers(attrib["d"], state.limits, element_path)

    for numeric_attr in (
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "width",
        "height",
    ):
        if numeric_attr in attrib:
            _check_numbers(attrib[numeric_attr], state.limits, element_path)

    text = (element.text or "").strip() or None
    if text and len(text) > state.limits.max_text_node_chars:
        raise SvgSecurityError(
            DiagramDiagnosticCode.UNSUPPORTED_SVG_FEATURE,
            f"text node has {len(text)} characters, exceeding limit "
            f"{state.limits.max_text_node_chars}",
            element_path=element_path,
        )

    own_transform = _own_transform(attrib, state.limits, element_path)
    total_transform = parent_transform.compose(own_transform)

    children: list[NormalizedElement] = []

    if tag == "use":
        href = attrib.get("href") or attrib.get("xlink:href")
        target_id = href[1:] if href else None
        state.use_count += 1
        if state.use_count > state.limits.max_use_references:
            raise SvgSecurityError(
                DiagramDiagnosticCode.TOO_MANY_ELEMENTS,
                f"<use> reference count exceeds limit {state.limits.max_use_references}",
                element_path=element_path,
            )
        if target_id is None or target_id not in state.id_map:
            raise SvgSecurityError(
                DiagramDiagnosticCode.INVALID_SVG,
                f"<use> references unknown id {target_id!r}",
                element_path=element_path,
            )
        if target_id in use_chain:
            raise SvgSecurityError(
                DiagramDiagnosticCode.TRANSFORM_FAILURE,
                f"cyclic <use> reference via id {target_id!r}",
                element_path=element_path,
            )
        use_offset = Matrix2D(
            1, 0, 0, 1, float(attrib.get("x", 0) or 0), float(attrib.get("y", 0) or 0)
        )
        instance_transform = total_transform.compose(use_offset)
        target = state.id_map[target_id]
        normalized_target = _walk(
            target,
            state=state,
            parent_transform=instance_transform,
            element_path=f"{element_path}/use->#{target_id}",
            depth=depth + 1,
            use_chain=use_chain | {target_id},
        )
        if "id" in normalized_target.attrib:
            # A <use> instance is a *clone* of the referenced <defs>
            # element, not the element itself — per-instance uniqueness
            # (extraction.py's DUPLICATE_SYMBOL_ID check) must not fire
            # just because two separate <use href="#same-symbol"/> chart
            # placements both clone an element whose original definition
            # happens to carry an id. The definition itself (still walked
            # once for whatever purpose, e.g. direct id lookup) keeps its
            # id; only this per-instance copy drops it.
            stripped_attrib = {k: v for k, v in normalized_target.attrib.items() if k != "id"}
            normalized_target = replace(normalized_target, attrib=stripped_attrib)
        children = [normalized_target]
    else:
        for index, child in enumerate(element):
            child_tag = _local_tag(child)
            child_path = f"{element_path}/{child_tag}[{index}]"
            children.append(
                _walk(
                    child,
                    state=state,
                    parent_transform=total_transform,
                    element_path=child_path,
                    depth=depth + 1,
                    use_chain=use_chain,
                )
            )

    return NormalizedElement(
        tag=tag,
        attrib=attrib,
        children=children,
        transform=total_transform,
        element_path=element_path,
        text=text,
        used_symbol_id=target_id if tag == "use" else None,
    )


def _parse_length(value: str | None, fallback: float) -> float:
    if not value:
        return fallback
    stripped = _PX_SUFFIX_RE.sub("", value.strip())
    try:
        return float(stripped)
    except ValueError:
        return fallback


def parse_svg(
    source: str, limits: SafetyLimits
) -> tuple[NormalizedDocument | None, list[DiagramDiagnostic]]:
    """Parse, sanitise, and transform-normalise an untrusted SVG source.

    Returns ``(None, diagnostics)`` with at least one error-severity
    diagnostic on any failure — never raises.
    """
    source_bytes = source.encode("utf-8")
    if len(source_bytes) > limits.max_source_bytes:
        return None, [
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.SOURCE_TOO_LARGE,
                message=f"SVG source is {len(source_bytes)} bytes, exceeding the limit of "
                f"{limits.max_source_bytes}.",
            )
        ]

    try:
        root = defused_fromstring(
            source_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except DefusedXmlException as exc:
        return None, [
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.UNSAFE_SVG_CONTENT,
                message=f"SVG document rejected by the hardened XML parser: {exc}",
            )
        ]
    except (DefusedParseError, ET.ParseError) as exc:
        return None, [
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.INVALID_SVG,
                message=f"SVG document is not well-formed XML: {exc}",
            )
        ]

    if _local_tag(root) != "svg":
        return None, [
            DiagramDiagnostic(
                severity="error",
                code=DiagramDiagnosticCode.INVALID_SVG,
                message=f"root element must be <svg>, found <{_local_tag(root)}>",
            )
        ]

    root_attrib = _local_attrib(root)
    try:
        if "viewBox" in root_attrib:
            view_box = parse_viewbox(root_attrib["viewBox"])
        else:
            width = _parse_length(root_attrib.get("width"), 0.0)
            height = _parse_length(root_attrib.get("height"), 0.0)
            if width <= 0 or height <= 0:
                raise TransformParseError("SVG has neither a viewBox nor positive width/height")
            view_box = ViewBox(0.0, 0.0, width, height)
        if (
            view_box.width > limits.max_viewbox_dimension
            or view_box.height > limits.max_viewbox_dimension
        ):
            raise TransformParseError(
                f"viewBox dimensions exceed limit {limits.max_viewbox_dimension}"
            )
    except TransformParseError as exc:
        return None, [
            DiagramDiagnostic(
                severity="error", code=DiagramDiagnosticCode.INVALID_SVG, message=str(exc)
            )
        ]

    width = _parse_length(root_attrib.get("width"), view_box.width)
    height = _parse_length(root_attrib.get("height"), view_box.height)

    from crochet_reconstruction.diagram.transforms import viewbox_normalisation_matrix

    try:
        root_transform = viewbox_normalisation_matrix(view_box, width, height)
    except TransformParseError as exc:
        return None, [
            DiagramDiagnostic(
                severity="error", code=DiagramDiagnosticCode.TRANSFORM_FAILURE, message=str(exc)
            )
        ]

    state = _WalkState(limits=limits)
    try:
        _index_ids(root, state.id_map, limits)
    except SvgSecurityError as exc:
        return None, [
            DiagramDiagnostic(
                severity="error", code=exc.code, message=exc.message, element_path=exc.element_path
            )
        ]

    try:
        normalized_root = _walk(
            root,
            state=state,
            parent_transform=root_transform,
            element_path="svg",
            depth=0,
            use_chain=frozenset(),
        )
    except SvgSecurityError as exc:
        return None, [
            DiagramDiagnostic(
                severity="error", code=exc.code, message=exc.message, element_path=exc.element_path
            )
        ]

    fingerprint = hashlib.sha256(source_bytes).hexdigest()
    document = NormalizedDocument(
        root=normalized_root,
        width=width,
        height=height,
        view_box=view_box,
        fingerprint=fingerprint,
    )
    return document, []
