"""Deterministic stitch graph derived from a compiled :class:`Pattern`.

This package is additive: it reads a :class:`crochet_reconstruction.domain.pattern.Pattern`
and produces a :class:`StitchGraph` with one node per individual stitch. It
never modifies the deterministic engine (``domain``/``engine``/``validation``)
and imports from it only as a read-only consumer, the same relationship the
``rendering`` package already has with ``domain``.

The compiled ``Pattern`` records only aggregate operation counts (e.g. "8 sc"
is one ``StitchOp(count=8)``, not eight identified stitches). This package's
:mod:`builder` synthesizes per-stitch identity by expanding that operation
tree in working order and applying a documented, deterministic insertion-
target rule (left-to-right consumption of the previous round's stitches) —
see ``builder.py``'s module docstring for why this is a safe assumption for
every pattern this compiler currently produces, and why it is nonetheless
recorded as an explicit assumption rather than presented as IR-given fact.
"""

from __future__ import annotations
