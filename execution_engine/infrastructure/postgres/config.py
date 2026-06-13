#execution_engine\infrastructure\postgres\config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class DatabaseSettings(BaseSettings):
    """Database configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # PostgreSQL connection (NO DEFAULTS)
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    postgres_db: str

    # MySQL connection used for WordPress database provisioning
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_root_user: str = "root"
    mysql_root_password: str
    mysql_application_host: str | None = None

    # Connection pool
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

    # SQLAlchemy
    echo_sql: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def mysql_admin_url(self) -> str:
        return str(
            URL.create(
                drivername="mysql+pymysql",
                username=self.mysql_root_user,
                password=self.mysql_root_password,
                host=self.mysql_host,
                port=self.mysql_port,
                database="mysql",
            ).render_as_string(hide_password=False)
        )

    @property
    def mysql_runtime_host(self) -> str:
        if self.mysql_application_host:
            return self.mysql_application_host
        if self.mysql_host in {"localhost", "127.0.0.1"}:
            return "host.docker.internal"
        return self.mysql_host


settings = DatabaseSettings()
# Define the POSTGRES_DSN for import in other modules
POSTGRES_DSN = settings.database_url
