from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import configure_mappers

from database import Base
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
    Project,
    ResearchReview,
    ResearchReviewClaim,
    ResearchReviewEvent,
    SecurityEvent,
    User,
    Workflow,
    WorkflowAction,
    WorkflowToolRun,
)


REQUIRED_TABLES = {
    "users",
    "invitations",
    "auth_sessions",
    "auth_throttles",
    "projects",
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


def test_required_indexes_and_foreign_keys_are_declared() -> None:
    assert Project.__table__.c.storage_slug.unique is True
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


def test_alembic_revision_ids_fit_version_column_limit() -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    revisions = ScriptDirectory.from_config(config).walk_revisions()

    too_long = [revision.revision for revision in revisions if len(revision.revision) > 32]

    assert too_long == []


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
