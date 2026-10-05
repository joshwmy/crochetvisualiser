"""Canonical crochet-symbol ontology for diagram ingestion.

Internal identity is always the canonical (terminology-independent) name —
e.g. ``single_crochet``, never a US/UK display abbreviation. This mirrors
the written-pattern parser's existing separation between internal
``StitchFamily`` identity and display terminology (``docs/terminology.md``);
this module is the diagram-side equivalent for the symbols a chart can
carry, not a replacement for ``StitchFamily``.

Scope decision — why this ontology has more members than
``domain.enums.StitchFamily``: a chart needs to talk about *foundation and
closure* symbols (magic ring, chain ring, slip-stitch join) that never
become their own ``StitchNode`` in the existing graph schema — a magic ring
is represented by ``StitchNode.into_ring``, and a slip-stitch join by a
``round_closure`` edge plus ``ClosureKind.SLIP_STITCH_JOIN``, both already
modelled. ``DiagramTopologyCompiler`` (``diagram/compiler.py``) converts
``MAGIC_RING``/``CHAIN_RING`` symbols into ``into_ring=True`` on round-1
nodes and ``SLIP_STITCH``-as-closure symbols into that edge, rather than
adding new ``StitchFamily`` members with no compiler/geometry support behind
them — see ``domain/enums.py``'s own docstring for why an unsupported enum
member is treated as a trap, not a feature flag, in this codebase.

``INCREASE``/``DECREASE`` are real ontology entries (per the brief's
explicit symbol list) but resolve to an underlying worked-stitch family
(default: single crochet) at compile time — the *fact* of an increase or
decrease is still established by topology (parent/child fan-out), per the
brief's "acceptable... through topology rather than a unique glyph". An
explicit increase/decrease glyph is one more piece of classification
evidence, not a bypass of topology inference.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from crochet_reconstruction.domain.enums import StitchFamily

ConfidenceBand = Literal["high", "medium", "low", "manual"]


class DiagramStitchType(StrEnum):
    """Bounded first-slice symbol vocabulary. See module docstring for scope."""

    MAGIC_RING = "magic_ring"
    CHAIN = "chain"
    SLIP_STITCH = "slip_stitch"
    SINGLE_CROCHET = "single_crochet"
    HALF_DOUBLE_CROCHET = "half_double_crochet"
    DOUBLE_CROCHET = "double_crochet"
    INCREASE = "increase"
    DECREASE = "decrease"
    JOIN = "join"


class ReservedFutureStitchType(StrEnum):
    """Named in the brief as future vocabulary. Recognising one of these
    labels produces an explicit ``UNSUPPORTED_SYMBOL`` diagnostic rather than
    a silent fallback — see docs/diagram-symbol-ontology.md."""

    TREBLE_CROCHET = "treble_crochet"
    PICOT = "picot"
    PUFF_STITCH = "puff_stitch"
    BOBBLE = "bobble"
    CLUSTER = "cluster"
    FRONT_POST = "front_post"
    BACK_POST = "back_post"


# Symbols that are structural (foundation ring / round closure) rather than
# an individually worked stitch that becomes its own StitchNode.
STRUCTURAL_STITCH_TYPES = frozenset(
    {DiagramStitchType.MAGIC_RING, DiagramStitchType.CHAIN, DiagramStitchType.JOIN}
)

# DiagramStitchType -> StitchFamily for the types that *do* become worked
# StitchNodes. INCREASE/DECREASE default to single crochet (documented
# default; see module docstring) when no more specific base type is given.
WORKED_STITCH_FAMILY: dict[DiagramStitchType, StitchFamily] = {
    DiagramStitchType.SINGLE_CROCHET: StitchFamily.SC,
    DiagramStitchType.HALF_DOUBLE_CROCHET: StitchFamily.HDC,
    DiagramStitchType.DOUBLE_CROCHET: StitchFamily.DC,
    DiagramStitchType.INCREASE: StitchFamily.SC,
    DiagramStitchType.DECREASE: StitchFamily.SC,
}

CANONICAL_LABELS: dict[str, DiagramStitchType] = {t.value: t for t in DiagramStitchType}
"""data-stitch-type / class-name / title text -> canonical type, exact match only."""

ALIAS_TOKENS: dict[str, DiagramStitchType] = {
    "sc": DiagramStitchType.SINGLE_CROCHET,
    "hdc": DiagramStitchType.HALF_DOUBLE_CROCHET,
    "dc": DiagramStitchType.DOUBLE_CROCHET,
    "ch": DiagramStitchType.CHAIN,
    "sl": DiagramStitchType.SLIP_STITCH,
    "ss": DiagramStitchType.SLIP_STITCH,
    "slst": DiagramStitchType.SLIP_STITCH,
    "mr": DiagramStitchType.MAGIC_RING,
    "ring": DiagramStitchType.MAGIC_RING,
    "inc": DiagramStitchType.INCREASE,
    "dec": DiagramStitchType.DECREASE,
}
"""Common short-form aliases accepted anywhere a canonical label is matched
(``data-stitch-type``, element id, CSS class, ``<title>`` text, aria-label)
— documented in docs/diagram-symbol-ontology.md so external chart authors
know both forms are accepted."""


def resolve_label_token(token: str) -> DiagramStitchType | None:
    """Normalise one id/class/title/aria-label/data-attribute token
    (hyphens/underscores/case-insensitive) to a canonical stitch type, or
    ``None`` if it matches neither the canonical vocabulary nor a known
    alias."""
    normalized = token.strip().lower().replace("-", "_")
    if normalized in CANONICAL_LABELS:
        return CANONICAL_LABELS[normalized]
    return ALIAS_TOKENS.get(normalized)


def resolve_reserved_future_token(token: str) -> ReservedFutureStitchType | None:
    normalized = token.strip().lower().replace("-", "_")
    try:
        return ReservedFutureStitchType(normalized)
    except ValueError:
        return None


class ClassificationMethod(StrEnum):
    """Which extraction stage produced a symbol's classification.

    Ordering below (top to bottom) is the deterministic priority order used
    by ``diagram/extraction.py`` — never let a later (lower-confidence)
    method override an earlier one. See ``CONFIDENCE_BY_METHOD``.
    """

    DATA_ATTRIBUTE = "data_attribute"
    USE_REFERENCE = "use_reference"
    ELEMENT_ID = "element_id"
    CSS_CLASS = "css_class"
    TITLE = "title"
    ARIA_LABEL = "aria_label"
    TEXT_LABEL = "text_label"
    PRIMITIVE_GEOMETRY = "primitive_geometry"
    MANUAL_OVERRIDE = "manual_override"
    UNCLASSIFIED = "unclassified"


CONFIDENCE_BY_METHOD: dict[ClassificationMethod, float] = {
    ClassificationMethod.MANUAL_OVERRIDE: 1.0,
    ClassificationMethod.DATA_ATTRIBUTE: 1.0,
    ClassificationMethod.USE_REFERENCE: 0.9,
    ClassificationMethod.ELEMENT_ID: 0.8,
    ClassificationMethod.CSS_CLASS: 0.8,
    ClassificationMethod.TITLE: 0.75,
    ClassificationMethod.ARIA_LABEL: 0.7,
    # Same score as aria_label and primitive_geometry, for opposing reasons
    # that cancel: the label's *content* is explicit (unlike a shape guess),
    # but its *attachment* to a symbol is inferred from position (unlike any
    # declared method). It outranks primitive_geometry in priority — content
    # beats shape when both are available — without claiming to be more
    # certain than the weakest declared method. See diagram/text_labels.py.
    ClassificationMethod.TEXT_LABEL: 0.7,
    ClassificationMethod.PRIMITIVE_GEOMETRY: 0.7,
    ClassificationMethod.UNCLASSIFIED: 0.0,
}
"""Explainable confidence model (see docs/diagram-symbol-ontology.md,
"Confidence model"). Not a probability estimate — a fixed score per
evidence *source*, so the same method always produces the same confidence
for the same symbol. Primitive-geometry matches additionally get a
per-feature confidence penalty (see ``classification.py``) that can only
lower this base score, never raise it above the next tier."""


def confidence_band(confidence: float, *, is_manual: bool) -> ConfidenceBand:
    """High / Medium / Low / Manual — never a raw numeric "probability" in UI text."""
    if is_manual:
        return "manual"
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


REVIEW_REQUIRED_THRESHOLD = 0.5
"""Confidence strictly below this requires user review before compiling
(brief: "<0.5 Requires user review")."""
