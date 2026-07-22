"""Parsers that produce the existing domain representation from other sources.

Every parser here (currently only ``written/``, for typed US-terminology
crochet instructions) is a *producer* of ``list[Component]`` + a
:class:`crochet_reconstruction.domain.gauge.Gauge` — the same inputs
``graph.builder.build_stitch_graph`` and ``geometry.layout.build_geometry``
already accept from the beanie compiler. No parser here defines a
competing Pattern, StitchGraph, or geometry model; see
``docs/crochet-ir-spec.md``.
"""

from __future__ import annotations
