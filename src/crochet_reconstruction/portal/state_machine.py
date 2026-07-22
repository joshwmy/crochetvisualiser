"""Submission state machine.

```
draft -> submitted -> under_review -> changes_requested -> submitted (resubmit)
                                    -> rejected   (terminal)
                                    -> approved -> withdrawn (terminal)
```

Withdrawal is deliberately **not** modelled as a normal state-machine edge
from every state: it is a cross-cutting privacy right (a contributor can
ask to withdraw at any time, per the consent model), handled by
`services.withdraw_project`, which is allowed from any non-withdrawn status
and always records an audit event — see docs/portal-privacy-and-consent.md.
This module governs only the *review workflow's* transitions.
"""

from __future__ import annotations

from crochet_reconstruction.portal.models import ProjectStatus


class InvalidTransitionError(ValueError):
    """Raised when a requested status transition is not allowed."""


_ALLOWED_TRANSITIONS: dict[ProjectStatus, frozenset[ProjectStatus]] = {
    ProjectStatus.DRAFT: frozenset({ProjectStatus.SUBMITTED}),
    ProjectStatus.SUBMITTED: frozenset({ProjectStatus.UNDER_REVIEW}),
    ProjectStatus.UNDER_REVIEW: frozenset(
        {ProjectStatus.CHANGES_REQUESTED, ProjectStatus.REJECTED, ProjectStatus.APPROVED}
    ),
    ProjectStatus.CHANGES_REQUESTED: frozenset({ProjectStatus.SUBMITTED}),
    ProjectStatus.REJECTED: frozenset(),
    ProjectStatus.APPROVED: frozenset({ProjectStatus.WITHDRAWN}),
    ProjectStatus.WITHDRAWN: frozenset(),
}


def assert_valid_transition(current: ProjectStatus, target: ProjectStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"cannot transition from {current.value!r} to {target.value!r}; "
            f"allowed targets from {current.value!r}: "
            f"{sorted(s.value for s in allowed) or '(none - terminal state)'}"
        )


def is_withdrawable(current: ProjectStatus) -> bool:
    """Withdrawal is allowed from any status except an already-withdrawn one."""
    return current is not ProjectStatus.WITHDRAWN
