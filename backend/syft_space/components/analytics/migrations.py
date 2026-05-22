"""Standalone migration runner for the analytics database."""

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine

from syft_space.components.analytics.entities import QueryCostLine, QueryEvent


async def run_analytics_migrations(engine: AsyncEngine, reset: bool = False) -> None:
    """Run Alembic migrations for the analytics database.

    Uses a separate alembic_analytics.ini config so the analytics schema
    (query_events table) is managed independently of the main app.db.

    Args:
        engine: The async engine for the analytics database
        reset: If True, drop analytics tables before running migrations
    """
    from syft_space.config import app_settings

    package_dir = Path(__file__).parent.parent.parent
    alembic_ini_path = package_dir / "alembic_analytics.ini"

    if not alembic_ini_path.exists():
        logger.warning(
            f"Analytics alembic config not found at {alembic_ini_path}, "
            "falling back to direct table creation"
        )
        async with engine.connect() as connection:
            await connection.run_sync(_create_tables_directly)
            await connection.commit()
        return

    alembic_cfg = AlembicConfig(str(alembic_ini_path))

    def do_run_migrations(connection) -> None:
        if reset:
            QueryCostLine.__table__.drop(connection, checkfirst=True)
            QueryEvent.__table__.drop(connection, checkfirst=True)

        alembic_cfg.attributes["connection"] = connection

        try:
            command.upgrade(alembic_cfg, "head")
            logger.info("Analytics database migrations completed successfully")
        except Exception as e:
            if app_settings.debug:
                logger.warning(f"Analytics migration failed: {e}")
                logger.warning(
                    "Dev mode: Creating analytics tables directly and stamping to head"
                )
                _create_tables_directly(connection)
                try:
                    command.stamp(alembic_cfg, "head")
                except Exception as stamp_error:
                    logger.warning(f"Could not stamp analytics database: {stamp_error}")
            else:
                logger.exception(f"Analytics migration failed in production: {e}")
                raise RuntimeError(
                    f"Analytics database migration failed. Error: {e}"
                ) from e

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)


def _create_tables_directly(connection) -> None:
    """Create both analytics tables in dependency order, idempotent."""
    QueryEvent.__table__.create(connection, checkfirst=True)
    QueryCostLine.__table__.create(connection, checkfirst=True)
