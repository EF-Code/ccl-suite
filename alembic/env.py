"""Alembic runtime configuration for the CCL Suite schema."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from database import Base, get_database_url
from models import (  # noqa: F401
    Approval,
    Backup,
    DocumentChunk,
    File,
    FileHistory,
    FileVersion,
    IngestionRun,
    KnowledgeSource,
    Project,
    SecurityEvent,
    User,
    Workflow,
)

config = context.config

if config.config_file_name is not None and config.get_section("loggers") is not None:
    fileConfig(config.config_file_name)

# Importing the model classes above registers every table on Base.metadata.
target_metadata = Base.metadata

# Alembic uses ConfigParser interpolation, so percent signs in encoded URLs
# must be escaped before they are stored in the config object.
config.set_main_option("sqlalchemy.url", get_database_url().replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
