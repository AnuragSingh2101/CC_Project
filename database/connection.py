"""
Database connection and session management.
Supports SQLite (default) and PostgreSQL (cloud).
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from config.settings import DATABASE_URL, IS_POSTGRES
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def create_db_engine(db_url: str = None, test_mode: bool = False):
    """
    Create and configure the database engine.
    
    For SQLite: enables WAL mode and foreign key enforcement.
    For PostgreSQL: uses connection pooling.
    """
    url = db_url or DATABASE_URL
    
    if url.startswith("sqlite"):
        if test_mode:
            # In-memory database for tests
            engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False,
            )
        else:
            engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                echo=False,
            )

        # Enable WAL mode for better concurrency and foreign keys
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    else:
        # PostgreSQL
        engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )

    return engine


# Default engine and session factory
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    return _SessionLocal


def get_session():
    """Get a database session. Use as a context manager."""
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise


def init_database():
    """Create all tables if they don't exist."""
    from database import schema  # noqa - ensures models are registered
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized: {DATABASE_URL.split('://')[0]}")


def reset_engine():
    """Reset the engine (used in tests)."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
