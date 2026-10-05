"""2D affine transform composition for SVG coordinate normalisation.

Every extracted coordinate must go through exactly one of these composed
matrices before it reaches ``extraction.py`` — never the raw element-local
``d``/``cx``/``cy`` numbers, per the brief's "Do not infer topology from raw
element coordinates without applying transforms."

Deliberately not a general SVG-to-screen renderer: only the operations a
"clean vector chart" (this project's only supported profile) plausibly uses
are implemented — ``translate``/``rotate``/``scale``/``matrix``/``skewX``/
``skewY``, nested ``<g>``/``<use>`` composition, and ``viewBox`` normalised
with a simple uniform-scale-plus-translate mapping (no
``preserveAspectRatio`` slicing/meet-vs-slice handling — see
``docs/svg-diagram-ingestion.md``, "Known limitations").
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_TRANSFORM_FN_RE = re.compile(r"(\w+)\s*\(([^)]*)\)")
_NUMBER_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?")


class TransformParseError(ValueError):
    pass


@dataclass(frozen=True)
class Matrix2D:
    """Row-major 2D affine matrix: x' = a*x + c*y + e, y' = b*x + d*y + f."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def compose(self, other: Matrix2D) -> Matrix2D:
        """``self.compose(other)`` applies ``other`` first, then ``self`` —
        i.e. for a parent-then-child chain, call
        ``parent_total.compose(child_own)``."""
        return Matrix2D(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            e=self.a * other.e + self.c * other.f + self.e,
            f=self.b * other.e + self.d * other.f + self.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def apply_vector(self, x: float, y: float) -> tuple[float, float]:
        """Transform a direction (ignores translation) — for orientation/scale features."""
        return (self.a * x + self.c * y, self.b * x + self.d * y)

    @property
    def uniform_scale(self) -> float:
        """Geometric-mean scale factor, for symbols where only a single scale
        number is meaningful (bounding-box/orientation features)."""
        sx = math.hypot(self.a, self.b)
        sy = math.hypot(self.c, self.d)
        return math.sqrt(max(sx * sy, 1e-12))


IDENTITY = Matrix2D()


def translate(tx: float, ty: float = 0.0) -> Matrix2D:
    return Matrix2D(1, 0, 0, 1, tx, ty)


def scale(sx: float, sy: float | None = None) -> Matrix2D:
    return Matrix2D(sx, 0, 0, sy if sy is not None else sx, 0, 0)


def rotate(degrees: float, cx: float = 0.0, cy: float = 0.0) -> Matrix2D:
    theta = math.radians(degrees)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    rot = Matrix2D(cos_t, sin_t, -sin_t, cos_t, 0, 0)
    if cx == 0.0 and cy == 0.0:
        return rot
    return translate(cx, cy).compose(rot).compose(translate(-cx, -cy))


def skew_x(degrees: float) -> Matrix2D:
    return Matrix2D(1, 0, math.tan(math.radians(degrees)), 1, 0, 0)


def skew_y(degrees: float) -> Matrix2D:
    return Matrix2D(1, math.tan(math.radians(degrees)), 0, 1, 0, 0)


def parse_transform_list(value: str, *, max_functions: int) -> Matrix2D:
    """Parse an SVG ``transform`` attribute value into one composed matrix.

    Functions within one attribute compose left-to-right (SVG spec):
    ``"translate(10,0) rotate(45)"`` means translate-then-rotate in the
    child's local frame, i.e. ``translate.compose(rotate)``.
    """
    result = IDENTITY
    for count, match in enumerate(_TRANSFORM_FN_RE.finditer(value), start=1):
        if count > max_functions:
            raise TransformParseError(f"too many transform functions (> {max_functions})")
        name = match.group(1)
        args = [float(n) for n in _NUMBER_RE.findall(match.group(2))]
        fn_matrix = _apply_named_transform(name, args)
        result = result.compose(fn_matrix)
    return result


def _apply_named_transform(name: str, args: list[float]) -> Matrix2D:
    if name == "translate":
        if not args:
            raise TransformParseError("translate() requires at least 1 argument")
        return translate(args[0], args[1] if len(args) > 1 else 0.0)
    if name == "scale":
        if not args:
            raise TransformParseError("scale() requires at least 1 argument")
        return scale(args[0], args[1] if len(args) > 1 else None)
    if name == "rotate":
        if not args:
            raise TransformParseError("rotate() requires at least 1 argument")
        cx, cy = (args[1], args[2]) if len(args) >= 3 else (0.0, 0.0)
        return rotate(args[0], cx, cy)
    if name == "skewX":
        if not args:
            raise TransformParseError("skewX() requires 1 argument")
        return skew_x(args[0])
    if name == "skewY":
        if not args:
            raise TransformParseError("skewY() requires 1 argument")
        return skew_y(args[0])
    if name == "matrix":
        if len(args) != 6:
            raise TransformParseError("matrix() requires exactly 6 arguments")
        return Matrix2D(*args)
    raise TransformParseError(f"unsupported transform function: {name!r}")


@dataclass(frozen=True)
class ViewBox:
    min_x: float
    min_y: float
    width: float
    height: float


def parse_viewbox(value: str) -> ViewBox:
    parts = [float(n) for n in _NUMBER_RE.findall(value)]
    if len(parts) != 4:
        raise TransformParseError(f"viewBox must have exactly 4 numbers, got {len(parts)}")
    return ViewBox(*parts)


def viewbox_normalisation_matrix(view_box: ViewBox, width: float, height: float) -> Matrix2D:
    """Map ``viewBox`` user-space coordinates onto a ``width``x``height``
    normalised canvas. Uniform-scale approximation of ``xMidYMid meet`` — the
    only ``preserveAspectRatio`` behaviour this profile supports (see module
    docstring)."""
    if view_box.width <= 0 or view_box.height <= 0:
        raise TransformParseError("viewBox width/height must be positive")
    scale_factor = min(width / view_box.width, height / view_box.height)
    offset_x = (width - view_box.width * scale_factor) / 2
    offset_y = (height - view_box.height * scale_factor) / 2
    return (
        translate(offset_x, offset_y)
        .compose(scale(scale_factor))
        .compose(translate(-view_box.min_x, -view_box.min_y))
    )
