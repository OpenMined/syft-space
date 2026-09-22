"""The Alembic environment.

The database address is taken from the application's settings rather than from
alembic.ini: the password must not lie in a file under version control, and the
address comes from the environment anyway — keeping it in two places means one
day letting them drift apart.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from syft_benchmark.config import env_settings
from syft_benchmark.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The environment's settings, not the assembled ones: the stored settings live
# in a table this may be about to create, and reading them here would mean
# asking the database for its own schema before the schema is there.
config.set_main_option("sqlalchemy.url", env_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to the database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply the migrations to a live database."""
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
