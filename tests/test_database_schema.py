from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, configure_mappers

from database import Base, get_database_url
from models import (
    AgentHandoff,
    Approval,
    Backup,
    DocumentChunk,
    File,
    FileHistory,
    FileVersion,
    IngestionRun,
    KnowledgeErrorReport,
    KnowledgeFeedback,
    KnowledgeSource,
    OperationalAlert,
    PasswordResetToken,
    Project,
    ProjectMembership,
    ResearchReview,
    ResearchReviewClaim,
    ResearchReviewEvent,
    SecurityEvent,
    User,
    Workflow,
    WorkflowAction,
    WorkflowToolRun,
    WorkItem,
    WorkItemContentAsset,
    WorkItemContentReview,
    WorkItemComment,
)

REQUIRED_TABLES = {
    "users",
    "invitations",
    "auth_sessions",
    "auth_throttles",
    "projects",
    "project_memberships",
    "files",
    "file_history",
    "file_versions",
    "backups",
    "workflows",
    "agent_handoffs",
    "approvals",
    "workflow_actions",
    "workflow_tool_runs",
    "security_events",
    "operational_alerts",
    "work_items",
    "work_item_comments",
    "work_item_content_assets",
    "work_item_content_reviews",
    "user_notifications",
    "project_templates",
    "password_reset_tokens",
    "knowledge_sources",
    "ingestion_runs",
    "document_chunks",
    "knowledge_feedback",
    "knowledge_error_reports",
    "research_reviews",
    "research_review_claims",
    "research_review_events",
}


def test_metadata_contains_all_persisted_entities() -> None:
    assert set(Base.metadata.tables) == REQUIRED_TABLES


def test_relationship_mappers_configure() -> None:
    configure_mappers()

    assert User.projects.property.mapper.class_ is Project
    assert User.project_memberships.property.mapper.class_ is ProjectMembership
    assert Project.memberships.property.mapper.class_ is ProjectMembership
    assert ProjectMembership.user.property.mapper.class_ is User
    assert ProjectMembership.project.property.mapper.class_ is Project
    assert Project.files.property.mapper.class_ is File
    assert Project.backups.property.mapper.class_ is Backup
    assert Project.knowledge_sources.property.mapper.class_ is KnowledgeSource
    assert Project.ingestion_runs.property.mapper.class_ is IngestionRun
    assert Project.document_chunks.property.mapper.class_ is DocumentChunk
    assert Project.knowledge_feedback.property.mapper.class_ is KnowledgeFeedback
    assert Project.knowledge_error_reports.property.mapper.class_ is KnowledgeErrorReport
    assert Project.research_reviews.property.mapper.class_ is ResearchReview
    assert KnowledgeSource.ingestion_runs.property.mapper.class_ is IngestionRun
    assert KnowledgeSource.document_chunks.property.mapper.class_ is DocumentChunk
    assert IngestionRun.chunks.property.mapper.class_ is DocumentChunk
    assert File.history.property.mapper.class_ is FileHistory
    assert File.versions.property.mapper.class_ is FileVersion
    assert File.knowledge_sources.property.mapper.class_ is KnowledgeSource
    assert Project.workflows.property.mapper.class_ is Workflow
    assert Project.work_items.property.mapper.class_ is WorkItem
    assert WorkItem.assignee_user.property.mapper.class_ is User
    assert WorkItem.comments.property.mapper.class_ is WorkItemComment
    assert WorkItem.content_assets.property.mapper.class_ is WorkItemContentAsset
    assert WorkItem.content_reviews.property.mapper.class_ is WorkItemContentReview
    assert WorkItemComment.work_item.property.mapper.class_ is WorkItem
    assert WorkItemComment.author.property.mapper.class_ is User
    assert User.work_item_comments.property.mapper.class_ is WorkItemComment
    assert User.created_work_items.property.mapper.class_ is WorkItem
    assert Workflow.approvals.property.mapper.class_ is Approval
    assert Workflow.actions.property.mapper.class_ is WorkflowAction
    assert Workflow.tool_runs.property.mapper.class_ is WorkflowToolRun
    assert Workflow.agent_handoffs.property.mapper.class_ is AgentHandoff
    assert ResearchReview.claims.property.mapper.class_ is ResearchReviewClaim
    assert ResearchReview.events.property.mapper.class_ is ResearchReviewEvent
    assert User.security_events.property.mapper.class_ is SecurityEvent
    assert User.knowledge_feedback.property.mapper.class_ is KnowledgeFeedback
    assert User.knowledge_error_reports.property.mapper.class_ is KnowledgeErrorReport
    assert User.created_research_reviews.property.mapper.class_ is ResearchReview
    assert User.approved_research_reviews.property.mapper.class_ is ResearchReview
    assert User.verified_research_claims.property.mapper.class_ is ResearchReviewClaim
    assert User.research_review_events.property.mapper.class_ is ResearchReviewEvent


def test_schema_can_be_created_without_a_live_database() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    tables = set(inspect(engine).get_table_names())
    assert tables == REQUIRED_TABLES
    notification_columns = {
        column["name"] for column in inspect(engine).get_columns("user_notifications")
    }
    notification_indexes = inspect(engine).get_indexes("user_notifications")

    assert "dedupe_key" in notification_columns
    assert any(index["name"] == "uq_user_notifications_dedupe_key" for index in notification_indexes)


def test_database_password_file_is_url_encoded(monkeypatch, tmp_path: Path) -> None:
    password_path = tmp_path / "database-password"
    password_path.write_text("local:p@ss/word\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CCL_DATABASE_PASSWORD", raising=False)
    monkeypatch.setenv("CCL_DATABASE_HOST", "db")
    monkeypatch.setenv("CCL_DATABASE_PORT", "5432")
    monkeypatch.setenv("CCL_DATABASE_NAME", "ccl_suite")
    monkeypatch.setenv("CCL_DATABASE_USER", "ccl_app")
    monkeypatch.setenv("CCL_DATABASE_PASSWORD_FILE", str(password_path))

    database_url = make_url(get_database_url())

    assert database_url.password == "local:p@ss/word"
    assert database_url.username == "ccl_app"


def test_database_password_file_must_not_be_empty(monkeypatch, tmp_path: Path) -> None:
    password_path = tmp_path / "database-password"
    password_path.write_text("\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CCL_DATABASE_HOST", "db")
    monkeypatch.setenv("CCL_DATABASE_PASSWORD_FILE", str(password_path))

    import pytest

    with pytest.raises(ValueError, match="must contain a password"):
        get_database_url()


def test_required_indexes_and_foreign_keys_are_declared() -> None:
    assert Project.__table__.c.storage_slug.unique is True
    assert "ix_password_reset_tokens_user_created" in {
        index.name for index in PasswordResetToken.__table__.indexes
    }
    assert "ix_knowledge_sources_project_status" in {
        index.name for index in KnowledgeSource.__table__.indexes
    }
    assert "ix_knowledge_sources_owner_status" in {
        index.name for index in KnowledgeSource.__table__.indexes
    }
    assert "ix_projects_owner_status" in {
        index.name for index in Project.__table__.indexes
    }
    assert "ix_files_project_created_at" in {
        index.name for index in File.__table__.indexes
    }
    assert "ix_files_project_status" in {
        index.name for index in File.__table__.indexes
    }
    assert "ix_file_history_file_observed_at" in {
        index.name for index in FileHistory.__table__.indexes
    }
    assert "ix_file_versions_file_created_at" in {
        index.name for index in FileVersion.__table__.indexes
    }
    assert "ix_backups_project_created_at" in {
        index.name for index in Backup.__table__.indexes
    }
    assert "ix_backups_project_status" in {
        index.name for index in Backup.__table__.indexes
    }
    assert "ix_ingestion_runs_project_created_at" in {
        index.name for index in IngestionRun.__table__.indexes
    }
    assert "ix_ingestion_runs_source_created_at" in {
        index.name for index in IngestionRun.__table__.indexes
    }
    assert "ix_document_chunks_project_source_index" in {
        index.name for index in DocumentChunk.__table__.indexes
    }
    assert "ix_document_chunks_ingestion_index" in {
        index.name for index in DocumentChunk.__table__.indexes
    }
    assert "ix_workflows_project_status" in {
        index.name for index in Workflow.__table__.indexes
    }
    assert "ix_approvals_workflow_status" in {
        index.name for index in Approval.__table__.indexes
    }
    assert "ix_workflow_actions_project_status" in {
        index.name for index in WorkflowAction.__table__.indexes
    }
    assert "ix_workflow_tool_runs_project_created_at" in {
        index.name for index in WorkflowToolRun.__table__.indexes
    }
    assert "ix_agent_handoffs_project_created_at" in {
        index.name for index in AgentHandoff.__table__.indexes
    }
    assert "ix_agent_handoffs_workflow_created_at" in {
        index.name for index in AgentHandoff.__table__.indexes
    }
    assert {
        constraint.name for constraint in AgentHandoff.__table__.constraints
    } >= {
        "ck_agent_handoffs_source_agent_allowlist",
        "ck_agent_handoffs_target_agent_allowlist",
    }
    assert AgentHandoff.__table__.c.trace_id.unique is True
    assert AgentHandoff.__table__.c.input_fingerprint.type.length == 64
    assert AgentHandoff.__table__.c.input_summary.type.length == 255
    assert AgentHandoff.__table__.c.output_summary.type.length == 500
    assert {
        index.name for index in SecurityEvent.__table__.indexes
    } == {
        "ix_security_events_actor_occurred_at",
        "ix_security_events_code_occurred_at",
        "ix_security_events_occurred_at",
    }
    assert {
        index.name for index in OperationalAlert.__table__.indexes
    } == {
        "ix_operational_alerts_status_severity",
        "ix_operational_alerts_project_status",
    }
    assert {
        index.name for index in WorkItem.__table__.indexes
    } == {"ix_work_items_project_status_due", "ix_work_items_assignee_status_due"}
    assert {index.name for index in WorkItemComment.__table__.indexes} == {
        "ix_work_item_comments_item_created_at"
    }
    assert {
        constraint.name for constraint in WorkItemComment.__table__.constraints
    } >= {"ck_work_item_comments_body_not_blank", "ck_work_item_comments_body_max_length"}
    assert "ix_project_memberships_user_project" in {
        index.name for index in ProjectMembership.__table__.indexes
    }
    assert {
        constraint.name for constraint in WorkItem.__table__.constraints
    } >= {"ck_work_items_title_not_blank", "ck_work_items_status", "ck_work_items_priority"}
    assert OperationalAlert.__table__.c.fingerprint.unique is True
    assert {
        constraint.name for constraint in OperationalAlert.__table__.constraints
    } >= {
        "ck_operational_alerts_rule_code",
        "ck_operational_alerts_status",
        "ck_operational_alerts_severity",
        "ck_operational_alerts_escalation",
    }
    assert "ix_knowledge_feedback_project_created_at" in {
        index.name for index in KnowledgeFeedback.__table__.indexes
    }
    assert "ix_knowledge_error_reports_project_created_at" in {
        index.name for index in KnowledgeErrorReport.__table__.indexes
    }
    assert "ix_research_reviews_project_status" in {
        index.name for index in ResearchReview.__table__.indexes
    }
    assert "ix_research_review_claims_review_status" in {
        index.name for index in ResearchReviewClaim.__table__.indexes
    }
    assert "ix_research_review_events_review_created_at" in {
        index.name for index in ResearchReviewEvent.__table__.indexes
    }

    project_owner_fk = next(iter(Project.__table__.c.owner_id.foreign_keys))
    file_project_fk = next(iter(File.__table__.c.project_id.foreign_keys))
    history_file_fk = next(iter(FileHistory.__table__.c.file_id.foreign_keys))
    version_file_fk = next(iter(FileVersion.__table__.c.file_id.foreign_keys))
    backup_project_fk = next(iter(Backup.__table__.c.project_id.foreign_keys))
    backup_creator_fk = next(iter(Backup.__table__.c.created_by_id.foreign_keys))
    assert project_owner_fk.ondelete == "RESTRICT"
    assert file_project_fk.ondelete == "CASCADE"
    assert history_file_fk.ondelete == "CASCADE"
    assert version_file_fk.ondelete == "CASCADE"
    assert backup_project_fk.ondelete == "CASCADE"
    assert backup_creator_fk.ondelete == "SET NULL"
    review_project_fk = next(iter(ResearchReview.__table__.c.project_id.foreign_keys))
    review_claim_fk = next(iter(ResearchReviewClaim.__table__.c.review_id.foreign_keys))
    assert review_project_fk.ondelete == "CASCADE"
    assert review_claim_fk.ondelete == "CASCADE"
    comment_item_fk = next(iter(WorkItemComment.__table__.c.work_item_id.foreign_keys))
    comment_author_fk = next(iter(WorkItemComment.__table__.c.author_id.foreign_keys))
    assert comment_item_fk.ondelete == "CASCADE"
    assert comment_author_fk.ondelete == "SET NULL"


def test_alembic_revision_ids_fit_version_column_limit() -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    revisions = ScriptDirectory.from_config(config).walk_revisions()

    too_long = [revision.revision for revision in revisions if len(revision.revision) > 32]

    assert too_long == []


def test_membership_migration_preserves_legacy_labels_and_enrolls_owners(
    monkeypatch, tmp_path: Path
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'membership-migration.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0017_project_work_items")

    owner_id = uuid4()
    project_id = uuid4()
    work_item_id = uuid4()
    engine = create_engine(database_url)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            User.__table__.insert().values(
                id=owner_id,
                external_ref="migration-owner",
                email="migration-owner@example.test",
                is_active=True,
                role="staff",
            )
        )
        connection.execute(
            Project.__table__.insert().values(
                id=project_id,
                owner_id=owner_id,
                name="Legacy project",
                storage_slug="legacy-project",
                description="",
                category="general",
                scope="",
                deadline=None,
                outputs=[],
                responsible_person="",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            Table("work_items", MetaData(), autoload_with=connection).insert().values(
                id=work_item_id.hex,
                project_id=project_id.hex,
                title="Legacy assignment",
                description="Keep its original label until reviewed.",
                assignee="Video editor",
                status="todo",
                priority="normal",
                due_date=None,
                created_by_id=owner_id.hex,
                completed_at=None,
                created_at=now,
                updated_at=now,
            )
        )
    engine.dispose()

    command.upgrade(config, "head")
    migrated_engine = create_engine(database_url)
    with Session(migrated_engine) as session:
        membership = session.get(ProjectMembership, (project_id, owner_id))
        work_item = session.get(WorkItem, work_item_id)

    assert membership is not None
    assert membership.role == "manager"
    assert work_item is not None
    assert work_item.assignee_id is None
    assert work_item.assignee == "Video editor"
    notification_inspector = inspect(migrated_engine)
    notification_columns = {
        column["name"]
        for column in notification_inspector.get_columns("user_notifications")
    }
    notification_indexes = {
        index["name"]
        for index in notification_inspector.get_indexes("user_notifications")
    }
    notification_checks = {
        constraint["name"]: constraint["sqltext"]
        for constraint in notification_inspector.get_check_constraints("user_notifications")
    }
    assert "dedupe_key" in notification_columns
    assert "uq_user_notifications_dedupe_key" in notification_indexes
    assert "task.due_soon" in notification_checks["ck_user_notifications_event_type"]
    assert "task.overdue" in notification_checks["ck_user_notifications_event_type"]
    assert "content.review_requested" in notification_checks["ck_user_notifications_event_type"]
    migrated_engine.dispose()


def test_sensitive_payload_columns_are_not_stored() -> None:
    stored_columns = {
        column.name
        for table in Base.metadata.tables.values()
        for column in table.columns
    }
    forbidden_columns = {
        "password",
        "access_token",
        "refresh_token",
        "request_body",
        "file_contents",
        "ip_address",
        "user_agent",
    }

    assert stored_columns.isdisjoint(forbidden_columns)
    assert "password_hash" in Base.metadata.tables["users"].columns
    assert "token_hash" in Base.metadata.tables["auth_sessions"].columns
