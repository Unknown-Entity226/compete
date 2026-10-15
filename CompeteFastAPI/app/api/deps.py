"""FastAPI Dependency Injection Providers."""
from functools import lru_cache
from typing import AsyncGenerator, cast
import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.services.cache_service import CacheService
from app.services.leetcode_client import LeetCodeClient, LeetCodeClientProtocol
from app.services.cached_leetcode_client import CachedLeetCodeClient
from app.services.competition_service import CompetitionService


@lru_cache()
def get_cache_service() -> CacheService:
    """Dependency that returns a singleton CacheService instance."""
    return CacheService()


@lru_cache()
def get_leetcode_client() -> LeetCodeClientProtocol:
    """Dependency that returns a singleton CachedLeetCodeClient instance."""
    cache = get_cache_service()
    raw_client = LeetCodeClient()
    return CachedLeetCodeClient(leetcode_client=raw_client, cache_service=cache)


def set_leetcode_http_client(client: httpx.AsyncClient | None) -> None:
    """Attach or detach the shared HTTP pool from the cached adapter."""
    cached_client = cast(CachedLeetCodeClient, get_leetcode_client())
    cached_client.client.set_http_client(client)


@lru_cache()
def get_competition_service() -> CompetitionService:
    """Dependency that returns a singleton CompetitionService instance."""
    return CompetitionService()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency providing a scoped async database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
