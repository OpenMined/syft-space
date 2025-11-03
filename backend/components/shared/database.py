from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Generic, Optional, TypeVar

from sqlmodel import Session, SQLModel, create_engine, select

T = TypeVar("T", bound=SQLModel)


class DatabaseConfig(ABC):
    """Base database configuration class"""

    @abstractmethod
    def get_connection_string(self) -> str:
        """Get the connection string for the database"""
        pass


class SQLiteConfig(DatabaseConfig):
    """SQLite database configuration"""

    def __init__(self, db_path: Path):
        """Initialize the SQLite database configuration"""
        self.db_path = db_path
        # Handle SQLite-specific setup
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection_string(self) -> str:
        """Get the connection string for the database"""
        return f"sqlite:///{self.db_path}"


class Database:
    """Database class for managing database connections and sessions"""

    def __init__(self, config: DatabaseConfig):
        """Initialize the database"""
        self.engine = create_engine(config.get_connection_string())

    def create_db_and_tables(self):
        """Create the database and tables"""
        SQLModel.metadata.create_all(self.engine, checkfirst=True)

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

    def get_by_id(self, id: int) -> Optional[T]:
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

    def get_by_field(self, field_name: str, value: any) -> Optional[T]:
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
