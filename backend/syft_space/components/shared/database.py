from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Generic, TypeVar

from alembic import command
from alembic.config import Config as AlembicConfig
from loguru import logger
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

T = TypeVar("T", bound=SQLModel)


class DatabaseConfig(ABC):
    """Base database configuration class"""

    @abstractmethod
    def get_database_url(self) -> str:
        """Get the sync database connection URL"""
        pass

    @abstractmethod
    def get_async_database_url(self) -> str:
        """Get the async database connection URL"""
        pass

    @abstractmethod
    def setup(self) -> None:
        """Perform any database-specific setup (create dirs, etc.)"""
        pass


class SQLiteConfig(DatabaseConfig):
    """SQLite database configuration"""

    def __init__(self, db_path: Path, enable_foreign_keys: bool = True):
        """Initialize the SQLite database configuration

        Args:
            db_path: Path to the SQLite database file
            enable_foreign_keys: Whether to enable foreign key constraints (default: True)
        """
        self.db_path = db_path
        self.enable_foreign_keys = enable_foreign_keys

    def get_database_url(self) -> str:
        """Get the database connection URL"""
        return f"sqlite:///{self.db_path}"

    def get_async_database_url(self) -> str:
        """Get the async database connection URL (uses aiosqlite driver)"""
        return f"sqlite+aiosqlite:///{self.db_path}"

    def setup(self) -> None:
        """Create parent directory if it doesn't exist"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


class AsyncDatabase:
    """Async database class for managing async database connections and sessions"""

    config: DatabaseConfig

    def __init__(self, config: DatabaseConfig):
        """Initialize the async database with a configuration

        Args:
            config: Database configuration instance
        """
        self.config = config

        # Run database-specific setup
        self.config.setup()

        # Get async database URL and create async engine

        self.database_url = self.config.get_async_database_url()
        logger.info(f"Initializing async database with URL: {self.database_url}")

        # Create async engine
        self.engine: AsyncEngine = create_async_engine(
            self.database_url,
            echo=False,
        )

        # Configure PRAGMA for foreign key constraints
        if isinstance(self.config, SQLiteConfig) and self.config.enable_foreign_keys:

            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
                logger.debug("SQLite PRAGMA foreign_keys=ON set for new connection")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[SQLModelAsyncSession, None]:
        """Get an async session for the database"""
        async with SQLModelAsyncSession(self.engine) as session:
            yield session

    async def run_migrations(self, reset: bool = False) -> None:
        """Run database migrations using async engine.

        Uses run_sync to bridge Alembic's sync API with async engine.

        Args:
            reset: If True, drop all tables before running migrations
        """
        from syft_space.config import app_settings

        package_dir = Path(__file__).parent.parent.parent
        alembic_ini_path = package_dir / "alembic.ini"

        if not alembic_ini_path.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

        alembic_cfg = AlembicConfig(str(alembic_ini_path))

        def do_run_migrations(connection) -> None:
            """Sync function that runs actual migrations."""
            if reset:
                SQLModel.metadata.drop_all(connection)

            # Pass connection to Alembic via config attributes
            # This allows env.py to reuse our connection instead of creating a new one
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
                    logger.error(f"Migration failed in production mode: {e}")
                    raise RuntimeError(
                        f"Database migration failed. This is fatal in production. "
                        f"Error: {e}"
                    ) from e

        async with self.engine.connect() as connection:
            await connection.run_sync(do_run_migrations)


class AsyncBaseRepository(Generic[T]):
    """Async base repository class for CRUD operations"""

    def __init__(self, db: AsyncDatabase, model: type[T]):
        """Initialize the async base repository"""
        self.db = db
        self.model = model

    async def create(self, obj: T) -> T:
        """Create an object in the database"""
        async with self.db.get_session() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def get_by_id(self, id: int) -> T | None:
        """Get an object by its ID"""
        async with self.db.get_session() as session:
            return await session.get(self.model, id)

    async def get_all(self) -> list[T]:
        """Get all objects from the database"""
        async with self.db.get_session() as session:
            statement = select(self.model)
            result = await session.exec(statement)
            return list(result.all())

    async def update(self, obj: T) -> T:
        """Update an object in the database"""
        async with self.db.get_session() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def delete(self, id: int) -> bool:
        """Delete an object from the database"""
        async with self.db.get_session() as session:
            obj = await session.get(self.model, id)
            if obj:
                await session.delete(obj)
                await session.commit()
                return True
            return False

    async def get_by_field(self, field_name: str, value: Any) -> T | None:
        """Get an object by a specific field value"""
        async with self.db.get_session() as session:
            statement = select(self.model).where(
                getattr(self.model, field_name) == value
            )
            result = await session.exec(statement)
            return result.first()

    async def delete_by_field(self, field_name: str, value: Any) -> bool:
        """Delete an object by a specific field value"""
        async with self.db.get_session() as session:
            statement = select(self.model).where(
                getattr(self.model, field_name) == value
            )
            result = await session.exec(statement)
            obj = result.first()
            if obj:
                await session.delete(obj)
                await session.commit()
                return True
            return False
