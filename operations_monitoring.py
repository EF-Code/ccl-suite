"""Deterministic, auditable alert evaluation and weekly operations metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from models import (
    AgentHandoff,
    Approval,
    OperationalAlert,
    Project,
    SecurityEvent,
    User,
    Workflow,
    WorkflowAction,
    utc_now,
)

REPEATED_FAILURE_THRESHOLD = 5
REPEATED_FAILURE_WINDOW = timedelta(minutes=15)
HIGH_RISK_HANDOFF_WINDOW = timedelta(days=7)
OVERDUE_APPROVAL_AFTER = timedelta(hours=24)
HIGH_RISK_BLOCK_REASONS = frozenset(
    {
        "input_rule:instruction-override",
        "input_rule:secret-exfiltration",
        "input_rule:access-boundary-bypass",
        "input_rule:approval-bypass",
    }
)
WORKFLOW_STATES = (
    "ready",
    "in_progress",
    "review",
    "changes_required",
    "approved",
    "archived",
)
WORKFLOW_ACTION_STATES = (
    "pending_approval",
    "approved",
    "rejected",
    "cancelled",
    "executed",
)


@dataclass(frozen=True)
class _AlertCandidate:
    fingerprint: str
    rule_code: str
    severity: str
    title: str
    summary: str
    project_id: UUID | None
    actor_id: UUID | None
    resource_type: str
    resource_ref: str
    observed_count: int
    source_last_seen: datetime


def _utc(value: datetime) -> datetime:
    """Normalize SQLite's naive timestamp results to UTC for comparisons."""

    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _fingerprint(*parts: object) -> str:
    return sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _project_ids(actor: User, organization_scope: bool):
    if organization_scope:
        return None
    return select(Project.id).where(Project.owner_id == actor.id)


def _alert_scope(actor: User, organization_scope: bool):
    if organization_scope:
        return None
    project_ids = _project_ids(actor, organization_scope)
    assert project_ids is not None
    return or_(
        OperationalAlert.actor_id == actor.id,
        OperationalAlert.project_id.in_(project_ids),
    )


def _append_audit_event(
    db: Session,
    actor_id: UUID,
    event_code: str,
    alert_id: UUID,
    occurred_at: datetime,
) -> None:
    db.add(
        SecurityEvent(
            actor_id=actor_id,
            event_code=event_code,
            outcome="success",
            resource_type="operational_alert",
            resource_ref=str(alert_id),
            occurred_at=occurred_at,
        )
    )


def _candidate_alerts(
    db: Session, actor: User, organization_scope: bool, now: datetime
):
    candidates: list[_AlertCandidate] = []
    lower_bound = now - REPEATED_FAILURE_WINDOW
    event_conditions = [
        SecurityEvent.actor_id.is_not(None),
        SecurityEvent.outcome.in_(("failure", "denied")),
        SecurityEvent.occurred_at >= lower_bound,
        SecurityEvent.occurred_at <= now,
    ]
    if not organization_scope:
        event_conditions.append(SecurityEvent.actor_id == actor.id)
    repeated_rows = db.execute(
        select(
            SecurityEvent.actor_id,
            SecurityEvent.event_code,
            func.count(SecurityEvent.id),
            func.min(SecurityEvent.occurred_at),
            func.max(SecurityEvent.occurred_at),
        )
        .where(*event_conditions)
        .group_by(SecurityEvent.actor_id, SecurityEvent.event_code)
        .having(func.count(SecurityEvent.id) >= REPEATED_FAILURE_THRESHOLD)
    ).all()
    for actor_id, event_code, count, _first_event, last_event in repeated_rows:
        assert actor_id is not None
        candidates.append(
            _AlertCandidate(
                fingerprint=_fingerprint(
                    "security.repeated_failures", actor_id, event_code
                ),
                rule_code="security.repeated_failures",
                severity="high"
                if count >= REPEATED_FAILURE_THRESHOLD * 2
                else "warning",
                title="Repeated failed or denied activity",
                summary=(
                    f"{count} failed or denied attempts for event '{event_code}' by one account "
                    "were recorded within 15 minutes."
                ),
                project_id=None,
                actor_id=actor_id,
                resource_type="security_event_code",
                resource_ref=event_code,
                observed_count=int(count),
                source_last_seen=last_event,
            )
        )

    handoff_conditions = [
        AgentHandoff.status == "blocked",
        AgentHandoff.blocked_reason.in_(HIGH_RISK_BLOCK_REASONS),
        AgentHandoff.created_at >= now - HIGH_RISK_HANDOFF_WINDOW,
        AgentHandoff.created_at <= now,
    ]
    if not organization_scope:
        handoff_conditions.append(Project.owner_id == actor.id)
    high_risk_handoffs = db.scalars(
        select(AgentHandoff)
        .join(Project, AgentHandoff.project_id == Project.id)
        .where(*handoff_conditions)
        .order_by(AgentHandoff.created_at, AgentHandoff.id)
    ).all()
    for handoff in high_risk_handoffs:
        reason = handoff.blocked_reason or ""
        critical = reason in {
            "input_rule:secret-exfiltration",
            "input_rule:approval-bypass",
        }
        category = reason.removeprefix("input_rule:").replace("-", " ")
        candidates.append(
            _AlertCandidate(
                fingerprint=_fingerprint("security.high_risk_handoff", handoff.id),
                rule_code="security.high_risk_handoff",
                severity="critical" if critical else "high",
                title="High-risk agent input was blocked",
                summary=f"A project agent handoff was blocked by the '{category}' safety rule.",
                project_id=handoff.project_id,
                actor_id=handoff.requested_by_id,
                resource_type="agent_handoff",
                resource_ref=str(handoff.id),
                observed_count=1,
                source_last_seen=handoff.created_at,
            )
        )

    approval_conditions = [
        Approval.status == "pending",
        Approval.requested_at <= now - OVERDUE_APPROVAL_AFTER,
    ]
    if not organization_scope:
        approval_conditions.append(Project.owner_id == actor.id)
    overdue_approvals = db.scalars(
        select(Approval)
        .join(Workflow, Approval.workflow_id == Workflow.id)
        .join(Project, Workflow.project_id == Project.id)
        .where(*approval_conditions)
        .order_by(Approval.requested_at, Approval.id)
    ).all()
    for approval in overdue_approvals:
        project_id = approval.workflow.project_id
        candidates.append(
            _AlertCandidate(
                fingerprint=_fingerprint("workflow.overdue_approval", approval.id),
                rule_code="workflow.overdue_approval",
                severity="warning",
                title="Approval is overdue",
                summary="A workflow approval has remained pending for at least 24 hours.",
                project_id=project_id,
                actor_id=approval.requested_by_id,
                resource_type="approval",
                resource_ref=str(approval.id),
                observed_count=1,
                source_last_seen=approval.requested_at,
            )
        )
    return candidates


def _severity_rank(severity: str) -> int:
    return {"warning": 0, "high": 1, "critical": 2}[severity]


def evaluate_operational_alerts(
    db: Session,
    actor: User,
    organization_scope: bool,
    *,
    now: datetime | None = None,
) -> dict[str, int | datetime | str]:
    """Evaluate the documented rules once and persist deduplicated alert state."""

    evaluated_at = now or utc_now()
    candidates = _candidate_alerts(db, actor, organization_scope, evaluated_at)
    candidate_fingerprints = {candidate.fingerprint for candidate in candidates}
    created = reopened = escalated = auto_resolved = 0

    for candidate in candidates:
        alert = db.scalar(
            select(OperationalAlert).where(
                OperationalAlert.fingerprint == candidate.fingerprint
            )
        )
        if alert is None:
            alert = OperationalAlert(
                fingerprint=candidate.fingerprint,
                rule_code=candidate.rule_code,
                severity=candidate.severity,
                status="open",
                title=candidate.title,
                summary=candidate.summary,
                project_id=candidate.project_id,
                actor_id=candidate.actor_id,
                resource_type=candidate.resource_type,
                resource_ref=candidate.resource_ref,
                observed_count=candidate.observed_count,
                escalation_level=0,
                first_seen_at=evaluated_at,
                last_seen_at=evaluated_at,
                created_at=evaluated_at,
                updated_at=evaluated_at,
            )
            db.add(alert)
            db.flush()
            _append_audit_event(
                db, actor.id, "security.alert.opened", alert.id, evaluated_at
            )
            created += 1
        elif alert.status == "resolved":
            if alert.resolved_at is None or _utc(candidate.source_last_seen) <= _utc(
                alert.resolved_at
            ):
                continue
            alert.status = "open"
            alert.severity = candidate.severity
            alert.title = candidate.title
            alert.summary = candidate.summary
            alert.project_id = candidate.project_id
            alert.actor_id = candidate.actor_id
            alert.observed_count = candidate.observed_count
            alert.escalation_level = 0
            alert.first_seen_at = evaluated_at
            alert.last_seen_at = evaluated_at
            alert.escalated_at = None
            alert.acknowledged_at = None
            alert.acknowledged_by_id = None
            alert.resolved_at = None
            alert.resolved_by_id = None
            alert.updated_at = evaluated_at
            _append_audit_event(
                db, actor.id, "security.alert.reopened", alert.id, evaluated_at
            )
            reopened += 1
        else:
            alert.observed_count = candidate.observed_count
            alert.title = candidate.title
            alert.summary = candidate.summary
            alert.last_seen_at = evaluated_at
            alert.updated_at = evaluated_at
            if _severity_rank(candidate.severity) > _severity_rank(alert.severity):
                alert.severity = candidate.severity

    # An overdue-approval alert is automatically cleared once the approval is
    # decided or no longer overdue. Other alert classes require human triage.
    overdue_active_conditions = [
        OperationalAlert.rule_code == "workflow.overdue_approval",
        OperationalAlert.status.in_(("open", "acknowledged")),
    ]
    scope_condition = _alert_scope(actor, organization_scope)
    if scope_condition is not None:
        overdue_active_conditions.append(scope_condition)
    active_overdue = db.scalars(
        select(OperationalAlert).where(*overdue_active_conditions)
    ).all()
    for alert in active_overdue:
        if alert.fingerprint in candidate_fingerprints:
            continue
        alert.status = "resolved"
        alert.resolved_at = evaluated_at
        alert.resolved_by_id = actor.id
        alert.updated_at = evaluated_at
        _append_audit_event(
            db, actor.id, "security.alert.auto_resolved", alert.id, evaluated_at
        )
        auto_resolved += 1

    active_conditions = [OperationalAlert.status == "open"]
    if scope_condition is not None:
        active_conditions.append(scope_condition)
    active_alerts = db.scalars(select(OperationalAlert).where(*active_conditions)).all()
    for alert in active_alerts:
        old_level = alert.escalation_level
        # Escalation event is added here so it participates in the same unit of work.
        if alert.acknowledged_at is None:
            age = evaluated_at - _utc(alert.first_seen_at)
            target_level = (
                2
                if age >= timedelta(hours=72)
                else 1
                if age >= timedelta(hours=24)
                else 0
            )
            if target_level > old_level:
                alert.escalation_level = target_level
                alert.escalated_at = evaluated_at
                escalated_severity = "critical" if target_level >= 2 else "high"
                if _severity_rank(alert.severity) < _severity_rank(escalated_severity):
                    alert.severity = escalated_severity
                alert.updated_at = evaluated_at
                _append_audit_event(
                    db, actor.id, "security.alert.escalated", alert.id, evaluated_at
                )
                escalated += 1

    db.flush()
    active_count = (
        db.scalar(
            select(func.count(OperationalAlert.id)).where(
                OperationalAlert.status.in_(("open", "acknowledged")),
                *([scope_condition] if scope_condition is not None else []),
            )
        )
        or 0
    )
    db.commit()
    return {
        "evaluated_at": evaluated_at,
        "scope": "organization" if organization_scope else "account",
        "created": created,
        "reopened": reopened,
        "escalated": escalated,
        "auto_resolved": auto_resolved,
        "active_alerts": int(active_count),
        "note": "Rules were evaluated on request; no background worker or external notification was run.",
    }


def build_weekly_operations_metrics(
    db: Session,
    actor: User,
    organization_scope: bool,
    period_start: date,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Calculate deterministic week-window metrics and explicitly current snapshots."""

    generated_at = now or utc_now()
    start_at = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=7)
    project_scope = [] if organization_scope else [Project.owner_id == actor.id]

    def count(statement) -> int:
        return int(db.scalar(statement) or 0)

    projects_created = count(
        select(func.count(Project.id)).where(
            *project_scope,
            Project.created_at >= start_at,
            Project.created_at < end_at,
        )
    )
    active_projects = count(
        select(func.count(Project.id)).where(
            *project_scope,
            Project.status == "active",
            Project.created_at <= generated_at,
        )
    )
    workflow_project_scope = (
        [] if organization_scope else [Project.owner_id == actor.id]
    )
    workflows_created = count(
        select(func.count(Workflow.id))
        .join(Project, Workflow.project_id == Project.id)
        .where(
            *workflow_project_scope,
            Workflow.created_at >= start_at,
            Workflow.created_at < end_at,
        )
    )
    workflow_rows = db.execute(
        select(Workflow.state, func.count(Workflow.id))
        .join(Project, Workflow.project_id == Project.id)
        .where(*workflow_project_scope, Workflow.created_at <= generated_at)
        .group_by(Workflow.state)
    ).all()
    workflows_by_state = {state: 0 for state in WORKFLOW_STATES}
    workflows_by_state.update({state: int(total) for state, total in workflow_rows})

    workflow_action_scope = [] if organization_scope else [Project.owner_id == actor.id]
    workflow_actions_created = count(
        select(func.count(WorkflowAction.id))
        .join(Project, WorkflowAction.project_id == Project.id)
        .where(
            *workflow_action_scope,
            WorkflowAction.created_at >= start_at,
            WorkflowAction.created_at < end_at,
        )
    )
    workflow_action_rows = db.execute(
        select(WorkflowAction.status, func.count(WorkflowAction.id))
        .join(Project, WorkflowAction.project_id == Project.id)
        .where(*workflow_action_scope, WorkflowAction.created_at <= generated_at)
        .group_by(WorkflowAction.status)
    ).all()
    workflow_actions_by_status = {state: 0 for state in WORKFLOW_ACTION_STATES}
    workflow_actions_by_status.update(
        {state: int(total) for state, total in workflow_action_rows}
    )
    workflow_actions_executed = count(
        select(func.count(WorkflowAction.id))
        .join(Project, WorkflowAction.project_id == Project.id)
        .where(
            *workflow_action_scope,
            WorkflowAction.status == "executed",
            WorkflowAction.executed_at >= start_at,
            WorkflowAction.executed_at < end_at,
        )
    )

    approval_scope = [] if organization_scope else [Project.owner_id == actor.id]
    approval_from = Approval.__table__.join(
        Workflow, Approval.workflow_id == Workflow.id
    ).join(Project, Workflow.project_id == Project.id)
    approvals_requested = count(
        select(func.count(Approval.id))
        .select_from(approval_from)
        .where(
            *approval_scope,
            Approval.requested_at >= start_at,
            Approval.requested_at < end_at,
        )
    )
    approvals_decided = count(
        select(func.count(Approval.id))
        .select_from(approval_from)
        .where(
            *approval_scope,
            Approval.decided_at >= start_at,
            Approval.decided_at < end_at,
        )
    )
    pending_conditions = [*approval_scope, Approval.status == "pending"]
    approvals_pending = count(
        select(func.count(Approval.id))
        .select_from(approval_from)
        .where(*pending_conditions)
    )
    approvals_overdue = count(
        select(func.count(Approval.id))
        .select_from(approval_from)
        .where(
            *pending_conditions,
            Approval.requested_at <= generated_at - OVERDUE_APPROVAL_AFTER,
        )
    )

    security_scope = [] if organization_scope else [SecurityEvent.actor_id == actor.id]
    security_period = [
        *security_scope,
        SecurityEvent.occurred_at >= start_at,
        SecurityEvent.occurred_at < end_at,
    ]
    security_rows = db.execute(
        select(
            func.count(SecurityEvent.id),
            func.sum(case((SecurityEvent.outcome == "success", 1), else_=0)),
            func.sum(case((SecurityEvent.outcome == "failure", 1), else_=0)),
            func.sum(case((SecurityEvent.outcome == "denied", 1), else_=0)),
        ).where(*security_period)
    ).one()

    handoff_scope = [] if organization_scope else [Project.owner_id == actor.id]
    handoff_by_created = [
        *handoff_scope,
        AgentHandoff.created_at >= start_at,
        AgentHandoff.created_at < end_at,
    ]
    handoff_status_rows = db.execute(
        select(AgentHandoff.status, func.count(AgentHandoff.id))
        .join(Project, AgentHandoff.project_id == Project.id)
        .where(*handoff_by_created)
        .group_by(AgentHandoff.status)
    ).all()
    handoff_status = {state: int(total) for state, total in handoff_status_rows}
    completed_handoff_rows = db.execute(
        select(AgentHandoff.created_at, AgentHandoff.completed_at)
        .join(Project, AgentHandoff.project_id == Project.id)
        .where(
            *handoff_scope,
            AgentHandoff.status == "completed",
            AgentHandoff.completed_at >= start_at,
            AgentHandoff.completed_at < end_at,
            AgentHandoff.created_at <= AgentHandoff.completed_at,
        )
    ).all()
    durations = [
        (_utc(completed) - _utc(created)).total_seconds()
        for created, completed in completed_handoff_rows
    ]
    high_risk_blocks = count(
        select(func.count(AgentHandoff.id))
        .join(Project, AgentHandoff.project_id == Project.id)
        .where(
            *handoff_by_created,
            AgentHandoff.status == "blocked",
            AgentHandoff.blocked_reason.in_(HIGH_RISK_BLOCK_REASONS),
        )
    )

    alert_scope = _alert_scope(actor, organization_scope)
    alert_conditions = [] if alert_scope is None else [alert_scope]
    alerts_opened = count(
        select(func.count(OperationalAlert.id)).where(
            *alert_conditions,
            OperationalAlert.created_at >= start_at,
            OperationalAlert.created_at < end_at,
        )
    )
    alerts_open_now = count(
        select(func.count(OperationalAlert.id)).where(
            *alert_conditions,
            OperationalAlert.status == "open",
        )
    )
    alerts_acknowledged_now = count(
        select(func.count(OperationalAlert.id)).where(
            *alert_conditions,
            OperationalAlert.status == "acknowledged",
        )
    )
    alerts_escalated = count(
        select(func.count(OperationalAlert.id)).where(
            *alert_conditions,
            OperationalAlert.status == "open",
            OperationalAlert.escalation_level > 0,
        )
    )

    return {
        "projects_created_in_period": projects_created,
        "active_projects_at_generation": active_projects,
        "workflows_created_in_period": workflows_created,
        "workflows_by_state_now": workflows_by_state,
        "workflow_actions_created_in_period": workflow_actions_created,
        "workflow_actions_executed_in_period": workflow_actions_executed,
        "workflow_actions_pending_now": workflow_actions_by_status["pending_approval"],
        "workflow_actions_by_status_now": workflow_actions_by_status,
        "approvals_requested_in_period": approvals_requested,
        "approvals_decided_in_period": approvals_decided,
        "approvals_pending_now": approvals_pending,
        "approvals_overdue_now": approvals_overdue,
        "security_events_in_period": int(security_rows[0] or 0),
        "security_successes_in_period": int(security_rows[1] or 0),
        "security_failures_in_period": int(security_rows[2] or 0),
        "security_denials_in_period": int(security_rows[3] or 0),
        "high_risk_agent_blocks_in_period": high_risk_blocks,
        "handoffs_started_in_period": sum(handoff_status.values()),
        "handoffs_completed_in_period": sum(
            1 for _created, _completed in completed_handoff_rows
        ),
        "handoffs_failed_in_period": handoff_status.get("failed", 0),
        "handoffs_blocked_in_period": handoff_status.get("blocked", 0),
        "mean_handoff_completion_seconds": sum(durations) / len(durations)
        if durations
        else None,
        "alerts_opened_in_period": alerts_opened,
        "alerts_open_now": alerts_open_now,
        "alerts_acknowledged_now": alerts_acknowledged_now,
        "alerts_escalated_open_now": alerts_escalated,
    }


__all__ = [
    "HIGH_RISK_BLOCK_REASONS",
    "build_weekly_operations_metrics",
    "evaluate_operational_alerts",
]
