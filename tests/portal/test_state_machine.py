import pytest

from crochet_reconstruction.portal.models import ProjectStatus
from crochet_reconstruction.portal.state_machine import (
    InvalidTransitionError,
    assert_valid_transition,
    is_withdrawable,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ProjectStatus.DRAFT, ProjectStatus.SUBMITTED),
        (ProjectStatus.SUBMITTED, ProjectStatus.UNDER_REVIEW),
        (ProjectStatus.UNDER_REVIEW, ProjectStatus.APPROVED),
        (ProjectStatus.UNDER_REVIEW, ProjectStatus.REJECTED),
        (ProjectStatus.UNDER_REVIEW, ProjectStatus.CHANGES_REQUESTED),
        (ProjectStatus.CHANGES_REQUESTED, ProjectStatus.SUBMITTED),
        (ProjectStatus.APPROVED, ProjectStatus.WITHDRAWN),
    ],
)
def test_valid_transitions_do_not_raise(current: ProjectStatus, target: ProjectStatus) -> None:
    assert_valid_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ProjectStatus.DRAFT, ProjectStatus.APPROVED),
        (ProjectStatus.DRAFT, ProjectStatus.UNDER_REVIEW),
        (ProjectStatus.SUBMITTED, ProjectStatus.APPROVED),
        (ProjectStatus.REJECTED, ProjectStatus.SUBMITTED),
        (ProjectStatus.REJECTED, ProjectStatus.APPROVED),
        (ProjectStatus.APPROVED, ProjectStatus.SUBMITTED),
        (ProjectStatus.WITHDRAWN, ProjectStatus.DRAFT),
        (ProjectStatus.WITHDRAWN, ProjectStatus.SUBMITTED),
    ],
)
def test_invalid_transitions_raise(current: ProjectStatus, target: ProjectStatus) -> None:
    with pytest.raises(InvalidTransitionError):
        assert_valid_transition(current, target)


def test_is_withdrawable_true_for_all_but_withdrawn() -> None:
    for status in ProjectStatus:
        if status is ProjectStatus.WITHDRAWN:
            assert not is_withdrawable(status)
        else:
            assert is_withdrawable(status)
