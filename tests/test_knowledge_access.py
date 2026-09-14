from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from knowledge_access import evaluate_project_knowledge_access


PROJECT_OWNER_ID = uuid4()
OTHER_USER_ID = uuid4()


@pytest.mark.parametrize("role", ["staff", "member"])
def test_project_owner_with_knowledge_read_has_project_scope(role: str) -> None:
    decision = evaluate_project_knowledge_access(
        actor_id=PROJECT_OWNER_ID,
        actor_role=role,
        project_owner_id=PROJECT_OWNER_ID,
    )

    assert decision.allowed is True
    assert decision.scope == "project"
    assert decision.reason == "project_owner"


@pytest.mark.parametrize("role", ["supervisor", "reviewer", "administrator"])
def test_global_knowledge_operators_can_read_any_project(role: str) -> None:
    decision = evaluate_project_knowledge_access(
        actor_id=OTHER_USER_ID,
        actor_role=role,
        project_owner_id=PROJECT_OWNER_ID,
    )

    assert decision.allowed is True
    assert decision.scope == "global"
    assert decision.reason == "global_operator"


@pytest.mark.parametrize("role", ["intern", "unknown"])
def test_roles_without_knowledge_read_are_denied_even_as_owner(role: str) -> None:
    decision = evaluate_project_knowledge_access(
        actor_id=PROJECT_OWNER_ID,
        actor_role=role,
        project_owner_id=PROJECT_OWNER_ID,
    )

    assert decision.allowed is False
    assert decision.scope == "denied"
    assert decision.reason == "missing_permission"


def test_staff_cannot_read_a_project_they_do_not_own() -> None:
    decision = evaluate_project_knowledge_access(
        actor_id=OTHER_USER_ID,
        actor_role="staff",
        project_owner_id=PROJECT_OWNER_ID,
    )

    assert decision.allowed is False
    assert decision.scope == "denied"
    assert decision.reason == "outside_project"


def test_operator_aliases_are_normalized_before_scope_evaluation() -> None:
    decision = evaluate_project_knowledge_access(
        actor_id=OTHER_USER_ID,
        actor_role="  REVIEWER ",
        project_owner_id=PROJECT_OWNER_ID,
    )

    assert decision.allowed is True
    assert decision.scope == "global"
    assert decision.reason == "global_operator"


def test_access_decisions_are_immutable_audit_inputs() -> None:
    decision = evaluate_project_knowledge_access(
        actor_id=PROJECT_OWNER_ID,
        actor_role="staff",
        project_owner_id=PROJECT_OWNER_ID,
    )

    with pytest.raises(FrozenInstanceError):
        decision.scope = "denied"  # type: ignore[misc]
