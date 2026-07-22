"""Structured exceptions for portal services. Messages are safe to show to
end users (no internal paths, IDs, or stack details) unless noted."""

from __future__ import annotations


class PortalError(Exception):
    """Base class for all portal service errors."""


class InvitationError(PortalError):
    pass


class InvitationInvalidError(InvitationError):
    pass


class InvitationExpiredError(InvitationError):
    pass


class InvitationRevokedError(InvitationError):
    pass


class InvitationExhaustedError(InvitationError):
    pass


class ProjectNotEditableError(PortalError):
    """Raised when attempting to edit a project outside draft/changes_requested."""


class SubmissionValidationError(PortalError):
    """Raised when a project is missing required data for submission.

    ``missing_items`` is a plain-language list safe to render directly to
    the contributor (e.g. "a front photo", "consent to the privacy notice").
    """

    def __init__(self, missing_items: list[str]) -> None:
        self.missing_items = missing_items
        super().__init__("submission is missing required information: " + "; ".join(missing_items))


class TrialLinkValidationError(PortalError):
    pass


class ImageLimitExceededError(PortalError):
    pass
