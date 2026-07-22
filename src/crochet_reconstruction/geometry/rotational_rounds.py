"""Rotational analytical layout: flat circles, domed crowns, cylindrical bodies.

Applies to any pattern made of rounds worked in a circle — the crown/body/
brim component kinds used by the current beanie template are simply the
first three instances of that shape, not a hardcoded special case. A future
category (tube, sphere, motif) would get its own module here rather than
extending this one with `if component_kind == ...` branches.

Documented geometric assumptions (all analytical, not measured or simulated):

1. **Radius from stitch count**: a round's circumference is approximated as
   ``stitch_count / stitches_per_cm``, and radius as ``circumference / 2π``
   (treats the round as a perfect circle of evenly-spaced stitches — real
   fabric is not perfectly circular, especially near the increases).
2. **Row height**: constant ``1 / rounds_per_cm`` per round, applied
   uniformly across crown, body, and brim — real crochet fabric can compress
   or stretch slightly differently across a curved crown vs. a flat body,
   which this ignores.
3. **Crown dome shape**: modelled as a hemispherical cap,
   ``z = dome_height * sqrt(max(0, 1 - (r / r_max)^2))``, where
   ``dome_height = r_max * DOME_FLATNESS_FACTOR``. This is a visual
   approximation chosen to produce a recognisable rounded crown that meets
   the body at ``z = 0`` with continuous radius — it is not derived from the
   stitch counts themselves and has no claim to matching a real crown's
   curvature.
4. **Angular placement**: stitches within a round are spaced evenly by
   position index (``angle = 2π * position / count``), which — because
   parent and child stitches are emitted in matching left-to-right order —
   already keeps an increase's children and a decrease's consumed parents
   close in angle without any separate proximity solve.
5. **Yarn diameter**: not part of the domain gauge model, so approximated as
   ``0.5 / stitches_per_cm`` (half a stitch-width) when not explicitly
   overridden — a rough visual default, not a measured yarn property.

None of this feeds back into the deterministic engine; it is a one-way,
read-only consumer of a component list and gauge — not the full ``Pattern``,
since ``Pattern.input``/``Pattern.calculated`` carry beanie-sizing fields
this module never reads (see ``graph/builder.py``'s equivalent note).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from crochet_reconstruction.domain.enums import ComponentKind
from crochet_reconstruction.domain.gauge import Gauge
from crochet_reconstruction.domain.rounds import Component
from crochet_reconstruction.geometry.frames import frame_to_quaternion, radial_frame
from crochet_reconstruction.geometry.models import StitchGeometry, Vec3
from crochet_reconstruction.graph.models import StitchGraph, StitchNode

DOME_FLATNESS_FACTOR = 0.6
DEFAULT_YARN_DIAMETER_FRACTION_OF_STITCH_WIDTH = 0.5


@dataclass(frozen=True)
class _RoundPlacement:
    radius_cm: float
    z_cm: float
    stitch_count: int


def default_yarn_diameter_cm(stitches_per_cm: float) -> float:
    return DEFAULT_YARN_DIAMETER_FRACTION_OF_STITCH_WIDTH / stitches_per_cm


def _round_placements(
    components: list[Component], gauge: Gauge
) -> dict[tuple[str, int], _RoundPlacement]:
    stitches_per_cm = float(gauge.stitches_per_cm)
    rounds_per_cm = float(gauge.rounds_per_cm)
    row_height_cm = 1.0 / rounds_per_cm

    radii: dict[tuple[str, int], float] = {}
    counts: dict[tuple[str, int], int] = {}
    ordered_keys: list[tuple[str, int]] = []
    crown_keys: list[tuple[str, int]] = []

    for component in components:
        for round_ in component.rounds:
            key = (component.kind.value, round_.number)
            circumference_cm = round_.stated_total / stitches_per_cm
            radius_cm = circumference_cm / (2 * math.pi)
            radii[key] = radius_cm
            counts[key] = round_.stated_total
            ordered_keys.append(key)
            if component.kind is ComponentKind.CROWN:
                crown_keys.append(key)

    max_crown_radius = max((radii[k] for k in crown_keys), default=0.0)
    dome_height_cm = max_crown_radius * DOME_FLATNESS_FACTOR

    placements: dict[tuple[str, int], _RoundPlacement] = {}
    running_z = 0.0
    for key in ordered_keys:
        radius_cm = radii[key]
        if key in crown_keys and max_crown_radius > 0:
            ratio = radius_cm / max_crown_radius
            z_cm = dome_height_cm * math.sqrt(max(0.0, 1.0 - ratio**2))
        elif key in crown_keys:
            z_cm = 0.0
        else:
            running_z -= row_height_cm
            z_cm = running_z
        placements[key] = _RoundPlacement(radius_cm=radius_cm, z_cm=z_cm, stitch_count=counts[key])

    return placements


def place_stitches(
    components: list[Component], gauge: Gauge, graph: StitchGraph
) -> dict[str, StitchGeometry]:
    """Compute a :class:`StitchGeometry` record for every node in ``graph``."""
    placements = _round_placements(components, gauge)
    result: dict[str, StitchGeometry] = {}

    for node in graph.nodes:
        key = (node.component_kind.value, node.round_number)
        placement = placements[key]
        angle = 2 * math.pi * node.position_in_round / placement.stitch_count
        position: Vec3 = (
            placement.radius_cm * math.cos(angle),
            placement.radius_cm * math.sin(angle),
            placement.z_cm,
        )
        tangent, normal, binormal = radial_frame(angle)
        orientation = frame_to_quaternion(tangent, normal, binormal)

        result[node.stitch_id] = StitchGeometry(
            stitch_id=node.stitch_id,
            component_id=node.component_kind.value,
            stitch_type=node.stitch_type,
            round_index=node.round_number,
            sequence_index=node.sequence_index,
            position=position,
            orientation=orientation,
            tangent=tangent,
            normal=normal,
            binormal=binormal,
            loop_placement=node.loop_placement,
            colour_id=node.colour_id,
            yarn_id=node.yarn_id,
            parent_stitch_ids=node.parent_stitch_ids,
            is_increase=node.is_increase,
            is_decrease=node.is_decrease,
            source_reference=node.source_reference,
        )

    return result


def stitch_node_lookup(graph: StitchGraph) -> dict[str, StitchNode]:
    return {n.stitch_id: n for n in graph.nodes}
