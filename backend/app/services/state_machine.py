"""
Status state machine for CivicPulse complaints.

Domain rules:
- open -> in_progress
- in_progress -> resolved
- open -> rejected
- in_progress -> rejected
- resolved and rejected are terminal.
- Everything else is an invalid transition and rejected with HTTP 409 naming the transition.

Implemented as an explicit transition table rather than if-else chains.
"""

from app.models.complaint import StatusEnum


class InvalidStateTransitionError(Exception):
    """Raised when an illegal status transition is attempted."""

    def __init__(self, current_status: StatusEnum, target_status: StatusEnum):
        self.current_status = current_status
        self.target_status = target_status
        message = (
            f"Invalid status transition from '{current_status.value}' to '{target_status.value}'"
        )
        super().__init__(message)


# Explicit transition table mapping each status to the set of allowed next statuses
TRANSITION_TABLE: dict[StatusEnum, set[StatusEnum]] = {
    StatusEnum.OPEN: {
        StatusEnum.IN_PROGRESS,
        StatusEnum.REJECTED,
    },
    StatusEnum.IN_PROGRESS: {
        StatusEnum.RESOLVED,
        StatusEnum.REJECTED,
    },
    StatusEnum.RESOLVED: set(),  # Terminal state
    StatusEnum.REJECTED: set(),  # Terminal state
}


def can_transition(current: StatusEnum, target: StatusEnum) -> bool:
    """Return True if transitioning from current to target status is valid."""
    return target in TRANSITION_TABLE.get(current, set())


def validate_transition(current: StatusEnum, target: StatusEnum) -> None:
    """
    Validate that transitioning from current to target status is allowed.
    Raises InvalidStateTransitionError if the transition is illegal.
    """
    if not can_transition(current, target):
        raise InvalidStateTransitionError(current_status=current, target_status=target)
