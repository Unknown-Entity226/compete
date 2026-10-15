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
    SNAPSHOT_MIN_INTERVAL_SECONDS: int = 300      # 5 minutes between snapshots per user

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

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

