"""Alembic environment configuration for the analytics database.

This is separate from the main alembic/env.py to keep the analytics
schema (query_events) isolated in its own SQLite database file.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from syft_space.components.analytics.entities import QueryEvent  # noqa: F401
from syft_space.components.shared.database import SQLiteConfig
from syft_space.config import app_settings

# Alembic Config object
config = context.config

# Set up Python logging from the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Set async database URL if not already set (for CLI usage)
if not config.get_main_option("sqlalchemy.url"):
    db_config = SQLiteConfig(app_settings.analytics_db_path)
    config.set_main_option("sqlalchemy.url", db_config.get_async_database_url())

# Use SQLModel metadata (QueryEvent is registered there via import above)
target_metadata = SQLModel.metadata

# Only manage the query_events table in this alembic environment
ANALYTICS_TABLES = {"query_events"}


def include_name(name: str, type_: str, parent_names: dict) -> bool:
    """Filter to only include analytics tables in autogenerate."""
    if type_ == "table":
        return name in ANALYTICS_TABLES
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Sync migration runner called via run_sync."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Supports two modes:
    1. Programmatic: Connection passed via config.attributes["connection"]
    2. CLI: Creates new async engine and runs migrations
    """
    connectable = config.attributes.get("connection", None)

    if connectable is not None:
        do_run_migrations(connectable)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
