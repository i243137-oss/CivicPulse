"""
Unit tests for the status state machine.

Validates the explicit transition table:
- open -> in_progress (allowed)
- in_progress -> resolved (allowed)
- open -> rejected (allowed)
- in_progress -> rejected (allowed)
- resolved and rejected are terminal (no outgoing transitions allowed)
- all invalid transitions raise InvalidStateTransitionError with descriptive message
"""

import pytest

from app.models.complaint import StatusEnum
from app.services.state_machine import (
    InvalidStateTransitionError,
    can_transition,
    validate_transition,
)


def test_valid_transitions() -> None:
    """Test all valid status transitions defined in the domain rules."""
    # open -> in_progress
    assert can_transition(StatusEnum.OPEN, StatusEnum.IN_PROGRESS) is True
    validate_transition(StatusEnum.OPEN, StatusEnum.IN_PROGRESS)

    # in_progress -> resolved
    assert can_transition(StatusEnum.IN_PROGRESS, StatusEnum.RESOLVED) is True
    validate_transition(StatusEnum.IN_PROGRESS, StatusEnum.RESOLVED)

    # open -> rejected
    assert can_transition(StatusEnum.OPEN, StatusEnum.REJECTED) is True
    validate_transition(StatusEnum.OPEN, StatusEnum.REJECTED)

    # in_progress -> rejected
    assert can_transition(StatusEnum.IN_PROGRESS, StatusEnum.REJECTED) is True
    validate_transition(StatusEnum.IN_PROGRESS, StatusEnum.REJECTED)


def test_invalid_transition_from_open_to_resolved() -> None:
    """Cannot jump directly from open to resolved without being in_progress."""
    assert can_transition(StatusEnum.OPEN, StatusEnum.RESOLVED) is False
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        validate_transition(StatusEnum.OPEN, StatusEnum.RESOLVED)
    assert "Invalid status transition from 'open' to 'resolved'" in str(exc_info.value)
    assert exc_info.value.current_status == StatusEnum.OPEN
    assert exc_info.value.target_status == StatusEnum.RESOLVED


def test_resolved_is_terminal() -> None:
    """Resolved complaints cannot transition to any other status."""
    for target in StatusEnum:
        assert can_transition(StatusEnum.RESOLVED, target) is False
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(StatusEnum.RESOLVED, target)


def test_rejected_is_terminal() -> None:
    """Rejected complaints cannot transition to any other status."""
    for target in StatusEnum:
        assert can_transition(StatusEnum.REJECTED, target) is False
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(StatusEnum.REJECTED, target)


def test_same_status_transition_is_rejected() -> None:
    """Transitioning to the same status is not permitted in the state machine."""
    for st in StatusEnum:
        assert can_transition(st, st) is False
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(st, st)
