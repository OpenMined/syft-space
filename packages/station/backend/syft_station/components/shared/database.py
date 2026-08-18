from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config as AlembicConfig
from loguru import logger
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession


class SQLiteConfig:
    """SQLite database configuration"""

    def __init__(self, db_path: Path, enable_foreign_keys: bool = True):
        self.db_path = db_path
        self.enable_foreign_keys = enable_foreign_keys

    def get_async_database_url(self) -> str:
        """Get the async database connection URL (uses aiosqlite driver)"""
        return f"sqlite+aiosqlite:///{self.db_path}"

    def setup(self) -> None:
        """Create parent directory if it doesn't exist"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


class AsyncDatabase:
    """Async database class for managing async connections and sessions"""

    def __init__(self, config: SQLiteConfig):
        self.config = config
        self.config.setup()

        self.database_url = self.config.get_async_database_url()
        logger.info(f"Initializing async database with URL: {self.database_url}")

        self.engine: AsyncEngine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=10,
            max_overflow=5,
            pool_recycle=3600,
        )

        enable_foreign_keys = self.config.enable_foreign_keys

        @event.listens_for(self.engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            # WAL lets readers proceed while a writer holds the lock.
            cursor.execute("PRAGMA journal_mode=WAL")
            # With WAL, NORMAL only risks losing the very last commits on
            # power loss (never corruption) and skips an fsync per txn.
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Wait for a locked database instead of failing immediately.
            cursor.execute("PRAGMA busy_timeout=5000")
            if enable_foreign_keys:
                cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async def dispose(self) -> None:
        """Dispose of the engine and close all pooled connections."""
        await self.engine.dispose()
        logger.info("Database engine disposed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[SQLModelAsyncSession, None]:
        """Get an async session for the database"""
        async with SQLModelAsyncSession(self.engine) as session:
            yield session

    async def run_migrations(self, reset: bool = False) -> None:
        """Run database migrations using the async engine.

        Uses run_sync to bridge Alembic's sync API with the async engine.
        """
        from syft_station.config import app_settings

        package_dir = Path(__file__).parent.parent.parent
        alembic_ini_path = package_dir / "alembic.ini"

        if not alembic_ini_path.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

        alembic_cfg = AlembicConfig(str(alembic_ini_path))

        def do_run_migrations(connection) -> None:
            if reset:
                SQLModel.metadata.drop_all(connection)

            # Let env.py reuse our connection instead of creating a new one.
            alembic_cfg.attributes["connection"] = connection

            try:
                command.upgrade(alembic_cfg, "head")
                logger.info("Database migrations completed successfully")
            except Exception as e:
                if app_settings.debug:
                    logger.warning(f"Migration failed: {e}")
                    logger.warning("Dev mode: Using create_all() and stamping to head")
                    SQLModel.metadata.create_all(connection, checkfirst=True)
                    try:
                        command.stamp(alembic_cfg, "head")
                        logger.info("Database created and stamped to head")
                    except Exception as stamp_error:
                        logger.warning(f"Could not stamp database: {stamp_error}")
                else:
                    logger.exception(f"Migration failed in production mode: {e}")
                    raise RuntimeError(
                        f"Database migration failed. This is fatal in production. "
                        f"Error: {e}"
                    ) from e

        async with self.engine.connect() as connection:
            await connection.run_sync(do_run_migrations)


class AsyncBaseRepository[T: SQLModel]:
    """Async base repository class for CRUD operations"""

    def __init__(self, db: AsyncDatabase, model: type[T]):
        self.db = db
        self.model = model

    async def create(self, obj: T) -> T:
        async with self.db.get_session() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def get_by_id(self, id: Any) -> T | None:
        async with self.db.get_session() as session:
            return await session.get(self.model, id)

    async def get_all(self) -> list[T]:
        async with self.db.get_session() as session:
            statement = select(self.model)
            result = await session.exec(statement)
            return list(result.all())

    async def update(self, obj: T) -> T:
        async with self.db.get_session() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def delete(self, id: Any) -> bool:
        async with self.db.get_session() as session:
            obj = await session.get(self.model, id)
            if obj:
                await session.delete(obj)
                await session.commit()
                return True
            return False
