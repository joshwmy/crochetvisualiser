"""Per-round arithmetic validation: stated totals and stitch consumption.

Rule IDs match decision package §15's rule catalogue (``V-COUNT-001``,
``V-CONSUME-001``, ``V-CONSUME-002``, ``V-REPEAT-001``).
"""

from __future__ import annotations

from crochet_reconstruction.domain.operations import consumed_count, produced_count
from crochet_reconstruction.domain.rounds import Round
from crochet_reconstruction.validation.models import ReportBuilder


def check_round_arithmetic(
    round: Round, previous_total: int | None, path: str, builder: ReportBuilder
) -> int:
    """Validate one round's consumed/produced counts against its stated total.

    Returns the round's produced total, used by the caller as
    ``previous_total`` for the next round — even when validation fails, so
    that a single bad round does not cascade into spurious downstream
    errors.
    """
    try:
        consumed = sum(consumed_count(op) for op in round.operations)
        produced = sum(produced_count(op) for op in round.operations)
    except ValueError as exc:
        builder.fatal("V-REPEAT-001", path, str(exc))
        return round.stated_total

    if produced != round.stated_total:
        builder.fatal(
            "V-COUNT-001",
            path,
            f"round states {round.stated_total} stitches but operations produce {produced}",
            details={
                "stated_total": round.stated_total,
                "produced": produced,
                "consumed": consumed,
            },
        )

    if previous_total is None:
        if consumed != 0:
            builder.fatal(
                "V-CONSUME-001",
                path,
                f"round consumes {consumed} stitches but no previous round exists",
                details={"consumed": consumed},
            )
    elif consumed > previous_total:
        builder.fatal(
            "V-CONSUME-001",
            path,
            f"round consumes {consumed} stitches but only {previous_total} are available",
            details={"consumed": consumed, "available": previous_total},
        )
    elif consumed < previous_total:
        builder.fatal(
            "V-CONSUME-002",
            path,
            f"round consumes {consumed} of {previous_total} previous-round stitches; "
            f"a full round must be consumed",
            details={"consumed": consumed, "available": previous_total},
        )

    return produced
