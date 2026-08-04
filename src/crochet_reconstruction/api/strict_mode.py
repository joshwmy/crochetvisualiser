"""What ``options.strict`` means, defined once for both compile paths.

The written-pattern and SVG-diagram pipelines deliberately keep separate
diagnostic types (see ``diagram/diagnostics.py``'s module docstring for why).
The *policy* over those diagnostics is not pipeline-specific, though, so it
lives here rather than being written twice and drifting.

Strict mode blocks a compile that only succeeded because something was
**assumed or flagged**:

* any ``warning``-severity diagnostic, and
* the written path's ``ASSUMPTION_APPLIED`` info diagnostic, which records
  that a default gauge was substituted for one the pattern never stated.

``ASSUMPTION_APPLIED`` is info rather than warning because a normal compile
is perfectly happy to apply it — but a caller asking for strict interpretation
is precisely a caller who does not want an unstated value quietly filled in,
so it counts here despite its severity.

``error`` diagnostics are not this module's business: they already block in
both modes, strict or not.

**Default is ``strict=False``**, which preserves the pre-strict behaviour
exactly. Enabling it is opt-in — see docs/compile-api.md's "Strict mode".
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class _Diagnostic(Protocol):
    """Structural type covering both pipelines' diagnostic models.

    ``code`` is compared as a string: both concrete enums are ``StrEnum``, and
    only the written pipeline has an ``ASSUMPTION_APPLIED`` member at all, so
    a string comparison is the one way to express the shared rule without
    importing both enums and branching on which flavour arrived.
    """

    @property
    def severity(self) -> str: ...

    @property
    def code(self) -> str: ...


ASSUMPTION_APPLIED_CODE = "ASSUMPTION_APPLIED"


def strict_blocking_diagnostics[DiagnosticT: _Diagnostic](
    diagnostics: Sequence[DiagnosticT],
) -> list[DiagnosticT]:
    """The diagnostics that strict mode refuses to let through.

    Generic over the concrete diagnostic type so each caller gets its own type
    back rather than a widened one — the written path keeps ``Diagnostic``, the
    diagram path keeps ``DiagramDiagnostic``, and neither needs a cast to put
    the result back into its own response model.

    Returns them in their original order — diagnostic ordering is deterministic
    in both pipelines and must stay that way (see ``docs/diagnostic-codes.md``).
    Empty when strict mode has nothing to object to, in which case the compile
    proceeds exactly as it would with ``strict=False``.
    """
    return [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.severity == "warning" or str(diagnostic.code) == ASSUMPTION_APPLIED_CODE
    ]


def strict_block_message(blocking: Sequence[_Diagnostic]) -> str:
    """Human-readable summary naming the codes that caused the block.

    Lists codes rather than restating each message: the offending diagnostics
    are still returned alongside this one, so repeating their text here would
    duplicate what the client already has.
    """
    codes = sorted({str(diagnostic.code) for diagnostic in blocking})
    return (
        f"Strict mode: {len(blocking)} diagnostic(s) that would not block a normal "
        f"compile were treated as blocking ({', '.join(codes)}). "
        "Re-send with options.strict = false to compile anyway."
    )
