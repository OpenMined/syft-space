"""Alembic environment configuration for SQLModel with async support."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from syft_space.components.datasets.entities import (  # noqa: F401
    Dataset,
    ProvisionerState,
)
from syft_space.components.endpoints.entities import Endpoint  # noqa: F401
from syft_space.components.ingestion.entities import IngestionJob  # noqa: F401
from syft_space.components.marketplaces.entities import Marketplace  # noqa: F401
from syft_space.components.models.entities import Model  # noqa: F401
from syft_space.components.payments.entities import BundleUsage, Invoice  # noqa: F401
from syft_space.components.policies.entities import Policy  # noqa: F401
from syft_space.components.settings.entities import Settings  # noqa: F401
from syft_space.components.shared.database import SQLiteConfig
from syft_space.components.tenants.entities import Tenant  # noqa: F401
from syft_space.components.wallets.entities import Wallet  # noqa: F401
from syft_space.config import app_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Set async database URL if not already set (for CLI usage)
if not config.get_main_option("sqlalchemy.url"):
    db_config = SQLiteConfig(app_settings.sqlite_db_path)
    config.set_main_option("sqlalchemy.url", db_config.get_async_database_url())

# Set target metadata for 'autogenerate' support
# SQLModel uses SQLModel.metadata just like SQLAlchemy's Base.metadata
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Important for SQLModel: compare types properly
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Sync migration runner called via run_sync."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Important for SQLModel: compare types properly
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations with async engine.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
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
       (from AsyncDatabase.run_migrations())
    2. CLI: Creates new async engine and runs migrations
    """
    # Check if connection was passed programmatically
    connectable = config.attributes.get("connection", None)

    if connectable is not None:
        # Programmatic: use existing connection from AsyncDatabase.run_migrations()
        do_run_migrations(connectable)
    else:
        # CLI: create new async engine
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
