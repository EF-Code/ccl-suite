from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import configure_mappers

from database import Base
from models import (
    Approval,
    Backup,
    File,
    FileHistory,
    FileVersion,
    KnowledgeSource,
    Project,
    SecurityEvent,
    User,
    Workflow,
)


REQUIRED_TABLES = {
    "users",
    "projects",
    "files",
    "file_history",
    "file_versions",
    "backups",
    "workflows",
    "approvals",
    "security_events",
    "knowledge_sources",
}


def test_metadata_contains_all_persisted_entities() -> None:
    assert set(Base.metadata.tables) == REQUIRED_TABLES


def test_relationship_mappers_configure() -> None:
    configure_mappers()

    assert User.projects.property.mapper.class_ is Project
    assert Project.files.property.mapper.class_ is File
    assert Project.backups.property.mapper.class_ is Backup
    assert Project.knowledge_sources.property.mapper.class_ is KnowledgeSource
    assert File.history.property.mapper.class_ is FileHistory
    assert File.versions.property.mapper.class_ is FileVersion
    assert File.knowledge_sources.property.mapper.class_ is KnowledgeSource
    assert Project.workflows.property.mapper.class_ is Workflow
    assert Workflow.approvals.property.mapper.class_ is Approval
    assert User.security_events.property.mapper.class_ is SecurityEvent


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
    assert "ix_workflows_project_status" in {
        index.name for index in Workflow.__table__.indexes
    }
    assert "ix_approvals_workflow_status" in {
        index.name for index in Approval.__table__.indexes
    }
    assert {
        index.name for index in SecurityEvent.__table__.indexes
    } == {
        "ix_security_events_actor_occurred_at",
        "ix_security_events_code_occurred_at",
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


def test_sensitive_payload_columns_are_not_stored() -> None:
    stored_columns = {
        column.name
        for table in Base.metadata.tables.values()
        for column in table.columns
    }
    forbidden_columns = {
        "password",
        "password_hash",
        "access_token",
        "refresh_token",
        "request_body",
        "file_contents",
        "ip_address",
        "user_agent",
    }

    assert stored_columns.isdisjoint(forbidden_columns)
