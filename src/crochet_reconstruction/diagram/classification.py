"""Bounded, deterministic primitive-geometry classification.

Only used once every metadata-based classification method (data attribute,
use-reference, id, class, title, aria-label) has found nothing — the lowest
rung of ``ontology.ClassificationMethod``'s priority order. This is
deliberately not general computer vision: it recognises exactly the small,
fixed set of straight-line/circle shapes this project's own synthetic
symbol fixtures use (``tests/fixtures/diagram/svg/``), authored on a local
~10-unit coordinate box per symbol (see ``docs/diagram-symbol-ontology.md``,
"Primitive geometry convention"). A chart using different symbol artwork
without semantic metadata will get ``UNCLASSIFIED`` results here, which is
correct, bounded behaviour, not a bug — the brief explicitly forbids forcing
an uncertain symbol into a class.

Local (untransformed) element geometry is used for every feature below —
never the composed document transform — because a symbol's own proportions
(is this a cross or a T?) are authored in its local coordinate space and are
already independent of where/how it is scaled and rotated onto the chart;
that scale/rotation only matters for *placing* the symbol, not classifying
its shape (see ``diagram/transforms.py``'s module docstring).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from crochet_reconstruction.diagram.ontology import DiagramStitchType

Vec2 = tuple[float, float]

_PATH_TOKEN_RE = re.compile(r"([MmLlZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")

SHORT_BAR_MAX_LENGTH = 3.0
"""Local units. A single straight stroke no longer than this is a compact
slip-stitch marker, per this project's synthetic fixture convention."""

CROSS_MIDPOINT_TOLERANCE = 1.2
"""Local units. How close two strokes' crossing point must be to *both*
strokes' own midpoints to read as a centred cross/plus (single crochet)."""

HDC_CROSSBAR_TOP_RATIO = (0.05, 0.45)
"""Where (0=top, 1=bottom) a single crossbar must sit along the vertical
stroke to read as a T-shape (half double crochet) rather than a cross."""

AXIS_TOLERANCE = 0.5
"""Local units of allowed deviation from purely vertical/horizontal."""


@dataclass(frozen=True)
class PrimitiveClassification:
    candidates: list[DiagramStitchType]
    """Empty means unclassified. More than one means ambiguous."""

    features: dict[str, float | int | str] = field(default_factory=dict)


def _points_of(command: str, args: list[float]) -> list[Vec2]:
    if command in "Mm":
        return [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
    if command in "Ll":
        return [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
    return []


def extract_path_strokes(d: str) -> list[tuple[Vec2, Vec2]] | None:
    """Straight-line (M/L/Z only) subpaths as ``(start, end)`` pairs.

    Returns ``None`` if the path uses any curve command or a subpath has
    other than exactly two points — both are "too complex for this bounded
    heuristic", not an error; the caller falls back to unclassified.
    """
    tokens = _PATH_TOKEN_RE.findall(d)
    subpaths: list[list[Vec2]] = []
    current: list[Vec2] = []
    current_command: str | None = None
    pending_numbers: list[float] = []

    def flush() -> None:
        nonlocal current, current_command, pending_numbers
        if current_command is not None and pending_numbers:
            current.extend(_points_of(current_command, pending_numbers))
        pending_numbers = []

    for command_char, number_str in tokens:
        if command_char:
            if command_char in "Zz":
                flush()
                if current:
                    subpaths.append(current)
                current = []
                current_command = None
                continue
            if command_char not in "MmLl":
                return None  # curve or unsupported command: too complex
            flush()
            if command_char in "Mm" and current:
                subpaths.append(current)
                current = []
            current_command = command_char
        else:
            pending_numbers.append(float(number_str))
    flush()
    if current:
        subpaths.append(current)

    strokes: list[tuple[Vec2, Vec2]] = []
    for subpath in subpaths:
        if len(subpath) != 2:
            return None
        strokes.append((subpath[0], subpath[1]))
    return strokes or None


def _length(a: Vec2, b: Vec2) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _midpoint(a: Vec2, b: Vec2) -> Vec2:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _segment_intersection(p1: Vec2, p2: Vec2, p3: Vec2, p4: Vec2) -> Vec2 | None:
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return (px, py)


def _is_vertical(a: Vec2, b: Vec2) -> bool:
    return abs(a[0] - b[0]) <= AXIS_TOLERANCE and _length(a, b) > AXIS_TOLERANCE


def _is_horizontal(a: Vec2, b: Vec2) -> bool:
    return abs(a[1] - b[1]) <= AXIS_TOLERANCE and _length(a, b) > AXIS_TOLERANCE


def _classify_two_strokes(strokes: list[tuple[Vec2, Vec2]]) -> PrimitiveClassification:
    (a1, a2), (b1, b2) = strokes
    crossing = _segment_intersection(a1, a2, b1, b2)
    if crossing is None:
        return PrimitiveClassification(candidates=[])

    mid_a, mid_b = _midpoint(a1, a2), _midpoint(b1, b2)
    dist_to_mid_a = _length(crossing, mid_a)
    dist_to_mid_b = _length(crossing, mid_b)

    if dist_to_mid_a <= CROSS_MIDPOINT_TOLERANCE and dist_to_mid_b <= CROSS_MIDPOINT_TOLERANCE:
        return PrimitiveClassification(
            candidates=[DiagramStitchType.SINGLE_CROCHET],
            features={"stroke_count": 2, "shape": "cross"},
        )

    vertical = a1 if _is_vertical(a1, a2) else (b1 if _is_vertical(b1, b2) else None)
    if vertical is not None:
        v1, v2 = (a1, a2) if _is_vertical(a1, a2) else (b1, b2)
        h1, h2 = (b1, b2) if _is_vertical(a1, a2) else (a1, a2)
        if _is_horizontal(h1, h2):
            top, bottom = (v1, v2) if v1[1] <= v2[1] else (v2, v1)
            span = _length(top, bottom)
            if span > 1e-6:
                ratio = _length(top, crossing) / span
                if HDC_CROSSBAR_TOP_RATIO[0] <= ratio <= HDC_CROSSBAR_TOP_RATIO[1]:
                    return PrimitiveClassification(
                        candidates=[DiagramStitchType.HALF_DOUBLE_CROCHET],
                        features={"stroke_count": 2, "shape": "T", "crossbar_ratio": ratio},
                    )

    return PrimitiveClassification(
        candidates=[DiagramStitchType.SINGLE_CROCHET, DiagramStitchType.HALF_DOUBLE_CROCHET],
        features={"stroke_count": 2, "shape": "ambiguous"},
    )


def _classify_three_strokes(strokes: list[tuple[Vec2, Vec2]]) -> PrimitiveClassification:
    verticals = [s for s in strokes if _is_vertical(*s)]
    horizontals = [s for s in strokes if _is_horizontal(*s)]
    if len(verticals) == 1 and len(horizontals) == 2:
        v1, v2 = verticals[0]
        top, bottom = (v1, v2) if v1[1] <= v2[1] else (v2, v1)
        span = _length(top, bottom)
        crossbar_positions = []
        for h1, h2 in horizontals:
            hy = (h1[1] + h2[1]) / 2
            crossbar_positions.append((hy - top[1]) / span if span > 1e-6 else 0.0)
        if all(0.0 <= p <= 1.0 for p in crossbar_positions):
            return PrimitiveClassification(
                candidates=[DiagramStitchType.DOUBLE_CROCHET],
                features={"stroke_count": 3, "shape": "T-double"},
            )
    return PrimitiveClassification(
        candidates=[], features={"stroke_count": 3, "shape": "unrecognised"}
    )


def classify_strokes(strokes: list[tuple[Vec2, Vec2]]) -> PrimitiveClassification:
    """Classify a set of straight-line strokes gathered from one candidate
    symbol (whether authored as one multi-subpath ``<path>`` or several
    sibling ``<line>``/``<path>`` primitives — see ``extraction.py``'s
    ``collect_strokes_for_classification``)."""
    if len(strokes) == 1:
        length = _length(*strokes[0])
        if length <= SHORT_BAR_MAX_LENGTH:
            return PrimitiveClassification(
                candidates=[DiagramStitchType.SLIP_STITCH],
                features={"stroke_count": 1, "length": length},
            )
        return PrimitiveClassification(
            candidates=[], features={"stroke_count": 1, "length": length}
        )
    if len(strokes) == 2:
        return _classify_two_strokes(strokes)
    if len(strokes) == 3:
        return _classify_three_strokes(strokes)
    return PrimitiveClassification(candidates=[], features={"stroke_count": len(strokes)})


def classify_primitive(tag: str, attrib: dict[str, str]) -> PrimitiveClassification:
    """Classify one leaf geometric primitive by its own local shape."""
    if tag in ("circle", "ellipse"):
        return PrimitiveClassification(
            candidates=[DiagramStitchType.CHAIN], features={"shape": "loop"}
        )

    if tag == "rect":
        try:
            width = float(attrib.get("width", 0))
            height = float(attrib.get("height", 0))
        except ValueError:
            return PrimitiveClassification(candidates=[])
        if max(width, height) <= SHORT_BAR_MAX_LENGTH:
            return PrimitiveClassification(
                candidates=[DiagramStitchType.SLIP_STITCH], features={"shape": "dot"}
            )
        return PrimitiveClassification(candidates=[])

    if tag == "path" and "d" in attrib:
        strokes = extract_path_strokes(attrib["d"])
        if strokes is None:
            return PrimitiveClassification(candidates=[])
        return classify_strokes(strokes)

    if tag == "line":
        try:
            x1, y1 = float(attrib.get("x1", 0)), float(attrib.get("y1", 0))
            x2, y2 = float(attrib.get("x2", 0)), float(attrib.get("y2", 0))
        except ValueError:
            return PrimitiveClassification(candidates=[])
        return classify_strokes([((x1, y1), (x2, y2))])

    return PrimitiveClassification(candidates=[])
