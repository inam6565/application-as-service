#tests\conftest.py

"""Pytest configuration and fixtures."""

import pytest
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from execution_engine.infrastructure.postgres.database import Base, get_session_factory
from execution_engine.infrastructure.postgres.config import settings
from execution_engine.infrastructure.postgres.repository import PostgresExecutionRepository
from execution_engine.core.models import Execution, ExecutionState
from execution_engine.core.service import ExecutionService
from execution_engine.core.events import MultiEventEmitter, PrintEventEmitter


@pytest.fixture(scope="session")
def test_database_url():
    """Get test database URL."""
    test_db_name = f"{settings.postgres_db}_test"
    return (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{test_db_name}"
    )


@pytest.fixture(scope="session")
def test_engine(test_database_url):
    """Create test database engine."""
    # Connect to default database to create test database
    default_url = (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/postgres"
    )
    default_engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
    
    test_db_name = f"{settings.postgres_db}_test"
    
    # Drop and recreate test database
    with default_engine.connect() as conn:
        # Terminate existing connections
        conn.execute(text(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{test_db_name}'
            AND pid <> pg_backend_pid()
        """))
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
        conn.execute(text(f"CREATE DATABASE {test_db_name}"))
    
    default_engine.dispose()
    
    # Connect to test database
    engine = create_engine(test_database_url, echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    engine.dispose()


@pytest.fixture(scope="function")
def test_session_factory(test_engine):
    """Create session factory for tests."""
    return get_session_factory(test_engine)


@pytest.fixture(scope="function")
def db_session(test_session_factory):
    """Create a new database session for a test."""
    session = test_session_factory()
    
    yield session
    
    session.close()


@pytest.fixture(autouse=True)
def clean_database(test_engine):
    """Clean database before each test."""
    # This runs before each test
    yield
    # This runs after each test
    with test_engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE executions RESTART IDENTITY CASCADE"))
        conn.commit()


@pytest.fixture
def repository(test_session_factory):
    """Create repository with test database session factory."""
    return PostgresExecutionRepository(session_factory=test_session_factory)


@pytest.fixture
def sample_execution():
    """Create a sample execution for testing."""
    return Execution(
        execution_id=uuid4(),
        tenant_id=uuid4(),
        application_id=uuid4(),
        deployment_id=uuid4(),
        runtime_type="docker",
        spec={
            "image": "nginx:alpine",
            "ports": {"80/tcp": 8080}
        },
        state=ExecutionState.CREATED,
        priority=0,
        max_retries=3
    )


@pytest.fixture
def service(repository):
    """Create service with test repository."""
    emitters = MultiEventEmitter([PrintEventEmitter()])
    return ExecutionService(repository, emitters)