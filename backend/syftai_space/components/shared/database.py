from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Generic, TypeVar

from alembic import command
from alembic.config import Config as AlembicConfig
from loguru import logger
from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine, select

T = TypeVar("T", bound=SQLModel)


class DatabaseConfig(ABC):
    """Base database configuration class"""

    @abstractmethod
    def get_database_url(self) -> str:
        """Get the database connection URL"""
        pass

    @abstractmethod
    def setup(self) -> None:
        """Perform any database-specific setup (create dirs, etc.)"""
        pass

    @abstractmethod
    def configure_engine(self, engine: Engine) -> None:
        """
        Configure database-specific settings on the engine.
        Override this method in subclasses to add database-specific configurations.
        """
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

    def setup(self) -> None:
        """Create parent directory if it doesn't exist"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def configure_engine(self, engine: Engine) -> None:
        """Configure SQLite-specific PRAGMA settings"""
        if self.enable_foreign_keys:

            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                """Set SQLite PRAGMA on each new connection"""
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
                logger.debug("SQLite PRAGMA foreign_keys=ON set for new connection")


class Database:
    """Database class for managing database connections and sessions"""

    def __init__(self, config: DatabaseConfig):
        """Initialize the database with a configuration

        Args:
            config: Database configuration instance
        """
        # Run database-specific setup
        config.setup()

        # Get database URL and create engine
        self.database_url = config.get_database_url()
        logger.info(f"Initializing database with connection URL: {self.database_url}")
        self.engine = create_engine(self.database_url)

        # Apply database-specific configurations
        config.configure_engine(self.engine)

    def run_migrations(self, reset: bool = False):
        """Run database migrations.

        In production (debug=False): Strict Alembic migrations only.
        In development (debug=True): Falls back to create_all + stamp if migrations fail.
        """
        from syftai_space.config import app_settings

        # If reset is True, drop all tables first
        if reset:
            SQLModel.metadata.drop_all(self.engine)

        # Get the syftai_space package directory where alembic.ini is located
        package_dir = Path(__file__).parent.parent.parent
        alembic_ini_path = package_dir / "alembic.ini"

        if not alembic_ini_path.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

        # Create Alembic config and override the database URL
        alembic_cfg = AlembicConfig(str(alembic_ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)

        try:
            # Run upgrade to head
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully")

        except Exception as e:
            if app_settings.debug:
                # DEV MODE: Fallback to create_all + stamp
                logger.warning(f"Migration failed: {e}")
                logger.warning("Dev mode: Using create_all() and stamping to head")

                SQLModel.metadata.create_all(self.engine, checkfirst=True)

                # Stamp the database so Alembic knows we're at "head"
                try:
                    command.stamp(alembic_cfg, "head")
                    logger.info("Database created and stamped to head")
                except Exception as stamp_error:
                    logger.warning(f"Could not stamp database: {stamp_error}")
            else:
                # PRODUCTION MODE: Fail loudly
                logger.error(f"Migration failed in production mode: {e}")
                raise RuntimeError(
                    f"Database migration failed. This is fatal in production. "
                    f"Error: {e}"
                ) from e

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a session for the database"""
        with Session(self.engine) as session:
            yield session


class BaseRepository(Generic[T]):
    """Base repository class for CRUD operations"""

    def __init__(self, db: Database, model: type[T]):
        """Initialize the base repository"""
        self.db = db
        self.model = model

    def create(self, obj: T) -> T:
        """Create an object in the database"""
        with self.db.get_session() as session:
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj

    def get_by_id(self, id: int) -> T | None:
        """Get an object by its ID"""
        with self.db.get_session() as session:
            return session.get(self.model, id)

    def get_all(self) -> list[T]:
        """Get all objects from the database"""
        with self.db.get_session() as session:
            statement = select(self.model)
            return session.exec(statement).all()

    def update(self, obj: T) -> T:
        """Update an object in the database"""
        with self.db.get_session() as session:
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj

    def delete(self, id: int) -> bool:
        """Delete an object from the database"""
        with self.db.get_session() as session:
            obj = session.get(self.model, id)
            if obj:
                session.delete(obj)
                session.commit()
                return True
            return False

    def get_by_field(self, field_name: str, value: any) -> T | None:
        """Get an object by a specific field value"""
        with self.db.get_session() as session:
            statement = select(self.model).where(
                getattr(self.model, field_name) == value
            )
            return session.exec(statement).first()

    def delete_by_field(self, field_name: str, value: any) -> bool:
        """Delete an object by a specific field value"""
        with self.db.get_session() as session:
            statement = select(self.model).where(
                getattr(self.model, field_name) == value
            )
            obj = session.exec(statement).first()
            if obj:
                session.delete(obj)
                session.commit()
                return True
            return False
