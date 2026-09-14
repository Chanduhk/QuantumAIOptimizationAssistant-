import os
from pathlib import Path
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.base import Base

load_dotenv()

# Keep the development database local to the backend module by default.
DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "behavior_engine.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


def get_database_url() -> str:
    """Resolve the active database URL for development or production."""
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip()
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def _build_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with sensible defaults for the target driver."""
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            future=True,
            pool_pre_ping=True,
        )

    return create_engine(database_url, future=True, pool_pre_ping=True)


engine = _build_engine(get_database_url())
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
    expire_on_commit=False,
)


def init_db(database_url: Optional[str] = None) -> Engine:
    """Reconfigure the global engine and session factory."""
    global engine, SessionLocal

    resolved_database_url = database_url or get_database_url()
    engine = _build_engine(resolved_database_url)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,
        expire_on_commit=False,
    )
    return engine


def create_tables(database_url: Optional[str] = None) -> None:
    """Create all registered SQLAlchemy tables."""
    if database_url is not None:
        init_db(database_url)
    Base.metadata.create_all(bind=engine)
    from backend.app.services.task_lifecycle_service import ensure_task_lifecycle_schema_for_bind

    ensure_task_lifecycle_schema_for_bind(engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI request handling."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
