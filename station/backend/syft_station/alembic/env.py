"""Alembic environment configuration for SQLModel with async support."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from syft_station.components.credits.entities import (  # noqa: F401
    Invoice,
    LedgerEntry,
    SpaceCreditToken,
    UserBalance,
    Wallet,
)
from syft_station.components.requests.entities import SpaceRequest  # noqa: F401
from syft_station.components.setup.entities import StationConfig  # noqa: F401
from syft_station.components.shared.database import SQLiteConfig
from syft_station.components.spaces.entities import Space, SpaceToken  # noqa: F401
from syft_station.config import app_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Set async database URL if not already set (for CLI usage)
if not config.get_main_option("sqlalchemy.url"):
    db_config = SQLiteConfig(app_settings.sqlite_db_path)
    config.set_main_option("sqlalchemy.url", db_config.get_async_database_url())

# Set target metadata for 'autogenerate' support
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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


def do_run_migrations(connection: Connection) -> None:
    """Sync migration runner called via run_sync."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
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
    1. Programmatic: connection passed via config.attributes["connection"]
       (from AsyncDatabase.run_migrations())
    2. CLI: creates a new async engine and runs migrations
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
