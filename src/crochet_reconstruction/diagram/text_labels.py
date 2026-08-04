"""Text-label association: classification priority #7.

A chart can name a symbol with a free-standing ``<text>`` element sitting
next to it ("dc", "sc") instead of carrying ``data-stitch-type``/``id``/
``class``/``<title>``/``aria-label`` metadata. Nothing in the SVG says which
symbol such a label belongs to — the association has to be inferred from
position, which is why this method sits *below* every declared-metadata
method in ``ontology.ClassificationMethod``'s priority order and can never
override one.

It sits *above* ``primitive_geometry`` because the label's *content* is
explicit: "dc" written by the chart's author is a stronger statement about
the intended stitch than counting strokes in the artwork is. Only the
attachment is inferred, not the meaning.

Two guards keep an inferred attachment from becoming a confident wrong
answer, both of which fail *closed* — a rejected association falls through to
the geometry heuristic or to unclassified, exactly as before this method
existed, and never produces a guessed classification:

* **Range.** The label must be within ``MAX_DISTANCE_BBOX_DIAGONALS`` of the
  symbol's own bounding-box diagonal. Expressing the limit relative to the
  symbol's own size rather than in absolute user units makes it independent
  of the chart's scale, matching this package's general rule that a symbol's
  own proportions — not the document's — drive interpretation (see
  ``classification.py``'s module docstring).
* **Mutual nearest, with separation.** The symbol must be the label's nearest
  eligible candidate *and* the label must be the symbol's nearest eligible
  label, each by a factor of ``AMBIGUITY_SEPARATION_RATIO`` over the runner-up.
  A label sitting midway between two symbols therefore classifies neither.

Neither constant is a crochet fact; both describe chart *layout*, and both
are documented in ``docs/diagram-symbol-ontology.md``. Loosening them cannot
turn an unclassified symbol into a wrong one silently — it would only widen
which labels are considered, and the mutual-nearest rule still has to hold.

Only labels whose text resolves to a known stitch type are considered at all
(``ontology.resolve_label_token``, exact match after normalisation). A chart's
round numbers, stitch counts, and titles — "3", "18 sts", "Round 4" — resolve
to nothing and are ignored here rather than being parsed; using them to seed
round numbering is a separate, still-unimplemented gap (see
``docs/known-limitations.md``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from crochet_reconstruction.diagram.ontology import DiagramStitchType, resolve_label_token
from crochet_reconstruction.diagram.svg_parser import NormalizedElement

Vec2 = tuple[float, float]
BBox = tuple[float, float, float, float]

MAX_DISTANCE_BBOX_DIAGONALS = 1.5
"""How far a label may sit from a symbol's anchor, in multiples of that
symbol's own bounding-box diagonal."""

AMBIGUITY_SEPARATION_RATIO = 1.5
"""How much nearer the winner must be than the runner-up, in both directions,
for an association to count as unambiguous."""

MIN_BBOX_DIAGONAL = 1e-6
"""Below this a symbol has no meaningful size to scale the search radius
against (a degenerate zero-area bbox), so no label can be associated with it."""


@dataclass(frozen=True)
class TextLabel:
    """One ``<text>`` element whose content names a known stitch type."""

    stitch_type: DiagramStitchType
    raw_text: str
    position: Vec2
    element_path: str


def _text_position(element: NormalizedElement) -> Vec2 | None:
    try:
        x = float(element.attrib.get("x", 0))
        y = float(element.attrib.get("y", 0))
    except ValueError:
        return None
    return element.transform.apply(x, y)


def collect_text_labels(root: NormalizedElement) -> list[TextLabel]:
    """Every ``<text>`` in document order whose content names a stitch type.

    Text that resolves to nothing is dropped here rather than carried
    forward — it is a round number, a stitch count, or a chart title, none of
    which this method has any business guessing about.
    """
    labels: list[TextLabel] = []

    def walk(element: NormalizedElement) -> None:
        if element.tag == "text" and element.text:
            resolved = resolve_label_token(element.text)
            position = _text_position(element)
            if resolved is not None and position is not None:
                labels.append(
                    TextLabel(
                        stitch_type=resolved,
                        raw_text=element.text,
                        position=position,
                        element_path=element.element_path,
                    )
                )
        for child in element.children:
            walk(child)

    walk(root)
    return labels


def _distance(a: Vec2, b: Vec2) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def bbox_diagonal(bbox: BBox) -> float:
    return math.hypot(bbox[2] - bbox[0], bbox[3] - bbox[1])


def _is_unambiguous_winner(distances: list[float], winner_index: int) -> bool:
    """True when ``distances[winner_index]`` beats every other entry by the
    separation ratio. Indexed rather than compared by value so two genuinely
    equidistant entries are correctly read as a tie (and therefore ambiguous),
    instead of one of them being mistaken for the winner itself."""
    winner = distances[winner_index]
    others = [d for i, d in enumerate(distances) if i != winner_index]
    if not others:
        return True
    return min(others) >= winner * AMBIGUITY_SEPARATION_RATIO


@dataclass(frozen=True)
class LabelCandidate:
    """The minimum a candidate must expose to take part in association."""

    anchor: Vec2
    bbox: BBox


def associate_text_labels(
    candidates: list[LabelCandidate], labels: list[TextLabel]
) -> dict[int, TextLabel]:
    """Map candidate index -> the label that unambiguously names it.

    Candidates absent from the result got no association, for any of the
    reasons in this module's docstring; every one of those is a fall-through to
    the next classification method, never a guess.
    """
    if not candidates or not labels:
        return {}

    # distances[candidate_index][label_index] — computed once, read from both
    # directions, so "nearest" means the same thing to a symbol looking at
    # labels and to a label looking at symbols.
    distances = [[_distance(c.anchor, label.position) for label in labels] for c in candidates]

    associations: dict[int, TextLabel] = {}
    for candidate_index, candidate in enumerate(candidates):
        diagonal = bbox_diagonal(candidate.bbox)
        if diagonal < MIN_BBOX_DIAGONAL:
            continue

        row = distances[candidate_index]
        best_label_index = min(range(len(labels)), key=row.__getitem__)
        best_distance = row[best_label_index]

        if best_distance > diagonal * MAX_DISTANCE_BBOX_DIAGONALS:
            continue
        if not _is_unambiguous_winner(row, best_label_index):
            continue

        column = [distances[i][best_label_index] for i in range(len(candidates))]
        if not _is_unambiguous_winner(column, candidate_index):
            continue

        associations[candidate_index] = labels[best_label_index]

    return associations
