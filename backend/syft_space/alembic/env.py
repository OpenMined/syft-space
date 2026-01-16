"""Alembic environment configuration for SQLModel."""

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

from syft_space.components.datasets.entities import (  # noqa: F401
    Dataset,
    ProvisionerState,
)
from syft_space.components.endpoints.entities import Endpoint  # noqa: F401
from syft_space.components.ingestion.entities import IngestionJob  # noqa: F401
from syft_space.components.marketplaces.entities import Marketplace  # noqa: F401
from syft_space.components.models.entities import Model  # noqa: F401
from syft_space.components.policies.entities import Policy  # noqa: F401
from syft_space.components.settings.entities import Settings  # noqa: F401
from syft_space.components.shared.database import SQLiteConfig
from syft_space.components.tenants.entities import Tenant  # noqa: F401
from syft_space.config import app_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL - use existing config value if set (from Database.run_migrations()),
# otherwise fall back to app_settings (for CLI usage)
if not config.get_main_option("sqlalchemy.url"):
    db_config = SQLiteConfig(app_settings.sqlite_db_path)
    config.set_main_option("sqlalchemy.url", db_config.get_database_url())

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


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    from sqlalchemy import engine_from_config, pool

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Important for SQLModel: compare types properly
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
