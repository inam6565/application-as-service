"""MySQL database provisioning helper."""

from functools import lru_cache
import logging
import re
from typing import Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema

from execution_engine.infrastructure.postgres.config import settings

logger = logging.getLogger(__name__)


def normalize_database_name(name: str) -> str:
    """Normalize a database name into a MySQL-safe identifier."""
    normalized = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
    if not normalized:
        normalized = "wp_default"
    if not normalized[0].isalpha():
        normalized = f"wp_{normalized}"
    return normalized[:64]


@lru_cache(maxsize=1)
def get_mysql_engine() -> Engine:
    """Create a cached SQLAlchemy engine for MySQL administrative access."""
    return create_engine(
        settings.mysql_admin_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )


class MySQLProvisioner:
    """Provision MySQL databases on the shared MySQL host."""

    def __init__(self, engine: Engine | None = None):
        self._engine = engine or get_mysql_engine()

    def create_database(self, database_name: str) -> Dict[str, str | int]:
        """Ensure a database exists and return connection details."""
        normalized_name = normalize_database_name(database_name)
        logger.info("[mysql] ensuring database exists: %s", normalized_name)

        with self._engine.begin() as connection:
            connection.execute(CreateSchema(normalized_name, if_not_exists=True))

        return {
            "db_name": normalized_name,
            "db_host": settings.mysql_runtime_host,
            "db_port": settings.mysql_port,
        }
