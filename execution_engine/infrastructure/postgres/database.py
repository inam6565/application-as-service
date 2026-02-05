#execution_engine\infrastructure\postgres\database.py

"""SQLAlchemy database setup and session management."""

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool

from execution_engine.infrastructure.postgres.config import settings


# ============================================
# Base for ORM models
# ============================================
Base = declarative_base()


# ============================================
# Engine configuration
# ============================================
def create_db_engine(database_url: Optional[str] = None) -> Engine:
    """Create SQLAlchemy engine with connection pooling."""
    
    url = database_url or settings.database_url
    
    engine = create_engine(
        url,
        echo=settings.echo_sql,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout,
        pool_recycle=settings.pool_recycle,
    )
    
    # Set PostgreSQL-specific settings
    @event.listens_for(engine, "connect")
    def set_search_path(dbapi_conn, connection_record):
        """Set default schema on connect."""
        cursor = dbapi_conn.cursor()
        cursor.execute("SET search_path TO public")
        cursor.close()
    
    return engine


# Global engine instance (for production use)
engine = create_db_engine()

# Session factory (for production use)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)


# ============================================
# Session factory function
# ============================================
def get_session_factory(engine_instance: Optional[Engine] = None):
    """
    Get a session factory bound to the given engine.
    
    If no engine provided, uses the default production engine.
    This allows tests to inject their own test engine.
    """
    if engine_instance is None:
        engine_instance = engine
    
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine_instance,
        expire_on_commit=False
    )


# ============================================
# Session management
# ============================================
@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Usage:
        with get_db_session() as session:
            execution = session.query(ExecutionORM).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """
    Get a new database session.
    
    Note: Caller is responsible for closing the session.
    """
    return SessionLocal()


# ============================================
# Database initialization
# ============================================
def init_db(engine_instance: Optional[Engine] = None) -> None:
    """Create all tables (for testing only - use Alembic in production)."""
    if engine_instance is None:
        engine_instance = engine
    Base.metadata.create_all(bind=engine_instance)


def drop_db(engine_instance: Optional[Engine] = None) -> None:
    """Drop all tables (for testing only)."""
    if engine_instance is None:
        engine_instance = engine
    Base.metadata.drop_all(bind=engine_instance)