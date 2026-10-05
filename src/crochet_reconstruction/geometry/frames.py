"""Local coordinate frames and quaternion orientation, in pure Python.

No numpy/scipy dependency is introduced here — every quantity is a plain
``float`` 3-tuple and the rotation-matrix-to-quaternion conversion is the
standard closed-form (Shepperd's method), which is exact and branch-stable
for the orthonormal frames this module always receives.
"""

from __future__ import annotations

import math

from crochet_reconstruction.geometry.models import Quat, Vec3


def normalize(v: Vec3) -> Vec3:
    length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if length == 0:
        raise ValueError("cannot normalize a zero-length vector")
    return (v[0] / length, v[1] / length, v[2] / length)


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def radial_frame(angle_radians: float) -> tuple[Vec3, Vec3, Vec3]:
    """Tangent/normal/binormal for a point on a vertical cylinder/cone at ``angle_radians``.

    * ``tangent``: direction of increasing angle (around the fabric).
    * ``normal``: radially outward (away from the fabric surface) — a
      simplification that ignores local crown slope; see the geometry
      package docstring's "analytical shape approximation" note.
    * ``binormal``: vertical, through the stitch height. Derived as
      ``tangent x normal`` so the frame is always orthonormal by
      construction, never independently guessed.
    """
    tangent = (-math.sin(angle_radians), math.cos(angle_radians), 0.0)
    normal = (math.cos(angle_radians), math.sin(angle_radians), 0.0)
    binormal = normalize(cross(tangent, normal))
    return tangent, normal, binormal


def frame_to_quaternion(tangent: Vec3, normal: Vec3, binormal: Vec3) -> Quat:
    """Convert an orthonormal (tangent, normal, binormal) basis to a unit quaternion.

    Columns of the rotation matrix are (tangent, normal, binormal) mapping
    local X/Y/Z axes to world space. Uses Shepperd's method for numerical
    stability across all rotation angles.
    """
    m00, m01, m02 = tangent[0], normal[0], binormal[0]
    m10, m11, m12 = tangent[1], normal[1], binormal[1]
    m20, m21, m22 = tangent[2], normal[2], binormal[2]

    trace = m00 + m11 + m22
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m21 - m12) * s
        y = (m02 - m20) * s
        z = (m10 - m01) * s
    elif m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s

    length = math.sqrt(x * x + y * y + z * z + w * w)
    return (x / length, y / length, z / length, w / length)
