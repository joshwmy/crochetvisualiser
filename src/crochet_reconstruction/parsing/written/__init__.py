"""Deterministic written-pattern parser: text -> ``list[Component]`` + diagnostics.

Public entry point: :func:`crochet_reconstruction.parsing.written.semantic.parse_written_pattern`.
See ``docs/written-pattern-grammar.md`` for supported syntax and every
documented simplifying assumption.
"""

from __future__ import annotations

from crochet_reconstruction.parsing.written.semantic import parse_written_pattern

__all__ = ["parse_written_pattern"]
