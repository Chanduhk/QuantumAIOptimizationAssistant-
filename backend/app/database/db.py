import os
from pathlib import Path
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.base import Base

# Anchor the authoritative application database to the repository root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Ensure environment variables are loaded reliably regardless of execution working directory
_backend_env = BACKEND_DIR / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env)
_root_env = PROJECT_ROOT / ".env"
if _root_env.exists():
    load_dotenv(_root_env)
load_dotenv()

DEFAULT_SQLITE_PATH = PROJECT_ROOT / "behavior_engine.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


def get_database_url() -> str:
    """Resolve the active database URL for development or production."""
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip()
    if not database_url:
        return DEFAULT_DATABASE_URL
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    if database_url.startswith("sqlite:///"):
        path_part = database_url[len("sqlite:///"):]
        if path_part == ":memory:" or not path_part:
            return database_url
        p = Path(path_part)
        if not p.is_absolute():
            # Prevent working-directory divergence by anchoring relative SQLite path to PROJECT_ROOT
            resolved = (PROJECT_ROOT / p).resolve()
            return f"sqlite:///{resolved.as_posix()}"
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

    pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    pool_timeout = float(os.getenv("DB_POOL_TIMEOUT", "30.0"))
    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
    )


engine = _build_engine(get_database_url())
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
    expire_on_commit=False,
)


def get_pool_status() -> dict:
    """Return pool diagnostics if supported by the pool implementation."""
    pool = getattr(engine, "pool", None)
    if pool is None:
        return {"status": "no_pool"}
    status: dict = {
        "class": pool.__class__.__name__,
    }
    if hasattr(pool, "size"):
        try:
            status["size"] = pool.size()
        except Exception:
            pass
    if hasattr(pool, "checkedout"):
        try:
            status["checked_out"] = pool.checkedout()
        except Exception:
            pass
    if hasattr(pool, "overflow"):
        try:
            status["overflow"] = pool.overflow()
        except Exception:
            pass
    if hasattr(pool, "checkedin"):
        try:
            status["checked_in"] = pool.checkedin()
        except Exception:
            pass
    return status


def ensure_schema_compatibility() -> None:
    """Ensure newly added columns exist in existing databases without destructive re-creation."""
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            if engine.url.drivername.startswith("sqlite"):
                raw_conn = getattr(conn, "connection", None)
                if raw_conn is not None and hasattr(raw_conn, "cursor"):
                    cursor = raw_conn.cursor()
                    cursor.execute("PRAGMA table_info(tasks);")
                    existing_cols = {row[1] for row in cursor.fetchall()}
                    if "scheduled_start_time" not in existing_cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN scheduled_start_time DATETIME;"))
                    if "scheduled_end_time" not in existing_cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN scheduled_end_time DATETIME;"))
                    if "reschedule_count" not in existing_cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN reschedule_count INTEGER NOT NULL DEFAULT 0;"))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Schema compatibility check notice: %s", exc)



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
    import backend.app.models  # noqa: F401 - ensure Task, BehaviorData, PlanProposal are registered
    import backend.app.models.auth  # noqa: F401 - ensure User, AuthSession are registered
    Base.metadata.create_all(bind=engine)
    from backend.app.services.task_lifecycle_service import ensure_task_lifecycle_schema_for_bind

    ensure_task_lifecycle_schema_for_bind(engine)
    ensure_schema_compatibility()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI request handling."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
