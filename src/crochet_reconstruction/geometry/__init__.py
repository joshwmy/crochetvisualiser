"""Analytical geometry-placement layer for a compiled stitch graph.

Operates on :class:`crochet_reconstruction.graph.models.StitchGraph`.

This package computes an approximate three-dimensional position and local
coordinate frame for every stitch node, and simplified curve control points
for every yarn segment. It is a read-only consumer of ``graph`` (and, through
it, ``domain``) — it never touches ``engine`` or ``validation`` and never
feeds back into the deterministic pattern math.

What this package is, precisely:

* **Deterministic crochet topology** (who connects to whom) comes entirely
  from the ``graph`` package and is not altered here.
* **Analytical shape approximation** (this package) places stitches using
  closed-form trigonometric formulas driven by gauge and stitch counts — no
  simulation, no iterative solving.
* **Constraint relaxation** (position-based dynamics, spring/curve-length
  constraints, collision correction) is explicitly out of scope for this
  slice; the data model here does not preclude adding it as a later
  refinement pass over the same node positions.
* **Visual rendering** (materials, lighting, procedural yarn meshes) is the
  browser viewer's job, not this package's.
* **Physical simulation** (yarn drape, tension, fibre behaviour) is not
  attempted anywhere in this codebase.

See ``docs/geometry-transfer-spec.md`` for the JSON schema this package
exports and the assumptions it documents.
"""

from __future__ import annotations
