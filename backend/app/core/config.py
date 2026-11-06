from pathlib import Path
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CompeteFastAPI Configuration Settings."""
    
    PROJECT_NAME: str = "CompeteFastAPI"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # LeetCode Upstream Configuration
    LEETCODE_GRAPHQL_URL: str = "https://leetcode.com/graphql"
    LEETCODE_TIMEOUT_SECONDS: float = 12.0
    LEETCODE_MAX_RETRIES: int = 3
    LEETCODE_BACKOFF_FACTOR: float = 1.5
    LEETCODE_HTTP_MAX_CONNECTIONS: int = 50
    LEETCODE_HTTP_MAX_KEEPALIVE_CONNECTIONS: int = 20
    
    # Redis Cache Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_USER_STATS_TTL_SECONDS: int = 600       # 10 minutes
    CACHE_USER_PROBLEMS_TTL_SECONDS: int = 1800   # 30 minutes
    CACHE_USER_ACTIVITY_TTL_SECONDS: int = 300    # 5 minutes

    # PostgreSQL Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/compete_db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: float = 30.0
    INIT_DB_ON_STARTUP: bool = True

    # Persistence: snapshot minimum interval to avoid flooding the statistics table
    SNAPSHOT_MIN_INTERVAL_SECONDS: int = 86400    # At most one unchanged snapshot per day
    SNAPSHOT_RETENTION_DAYS: int = 365

    # Rate Limiting (SlowAPI)
    DEFAULT_RATE_LIMIT: str = "60/minute"
    RATE_LIMIT_COMPARE: str = "30/minute"
    TRUSTED_PROXIES: List[str] = []

    # Background Scheduler (APScheduler)
    SNAPSHOT_SYNC_INTERVAL_HOURS: int = 1
    ENABLE_BACKGROUND_SCHEDULER: bool = True
    BACKGROUND_SYNC_CONCURRENCY: int = 5
    
    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def assemble_async_db_url(cls, v: str) -> str:
        """Ensure standard postgresql:// connection strings use the asyncpg driver."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("BACKEND_CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, origins: List[str]) -> List[str]:
        normalized = [origin.strip() for origin in origins]
        if "*" in normalized:
            raise ValueError("BACKEND_CORS_ORIGINS must list explicit origins when credentials are enabled")
        return normalized

    @field_validator("SNAPSHOT_RETENTION_DAYS")
    @classmethod
    def validate_snapshot_retention(cls, days: int) -> int:
        if days < 31:
            raise ValueError("SNAPSHOT_RETENTION_DAYS must preserve at least 30 days of velocity history")
        return days

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

