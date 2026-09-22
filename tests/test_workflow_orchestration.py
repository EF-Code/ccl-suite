from workflow_orchestration import (
    APPROVAL_GATED_STATES,
    TERMINAL_WORKFLOW_STATES,
    can_transition,
    is_terminal_state,
    requires_human_approval,
)


def test_approval_gated_states_are_explicit() -> None:
    assert APPROVAL_GATED_STATES == {"approved", "archived"}
    assert requires_human_approval("approved") is True
    assert requires_human_approval("review") is False


def test_archived_is_the_only_terminal_workflow_state() -> None:
    assert TERMINAL_WORKFLOW_STATES == {"archived"}
    assert is_terminal_state("archived") is True
    assert is_terminal_state("approved") is False
    assert can_transition("archived", "review") is False
