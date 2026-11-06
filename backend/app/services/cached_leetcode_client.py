"""Cached and Coalesced LeetCode Client.

Wraps the low-level LeetCodeClient with Redis caching, TTL expiration,
and SingleFlight request coalescing to protect upstream LeetCode servers.
"""
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings
from app.schemas.user import UserProfileResponse
from app.schemas.problem import UserProblemsResponse
from app.schemas.activity import UserActivityResponse
from app.services.leetcode_client import LeetCodeClient
from app.services.cache_service import CacheService


class CachedLeetCodeClient:
    """LeetCode client with transparent Redis TTL caching and SingleFlight coalescing."""

    def __init__(
        self,
        leetcode_client: Optional[LeetCodeClient] = None,
        cache_service: Optional[CacheService] = None,
    ) -> None:
        self.client = leetcode_client or LeetCodeClient()
        self.cache = cache_service or CacheService()

    async def get_user_profile(
        self,
        username: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> UserProfileResponse:
        """Retrieve user profile with 10-minute TTL and request coalescing."""
        normalized_username = username.lower().strip()
        cache_key = f"compete:user:profile:{normalized_username}"

        async def _fetch():
            return await self.client.get_user_profile(username=username, client=client)

        return await self.cache.get_or_compute(
            key=cache_key,
            ttl_seconds=settings.CACHE_USER_STATS_TTL_SECONDS,
            fetch_fn=_fetch,
            serializer=lambda p: p.model_dump(),
            deserializer=lambda d: UserProfileResponse(**d),
        )

    async def get_user_activity(
        self,
        username: str,
        limit: int = 20,
        client: Optional[httpx.AsyncClient] = None,
    ) -> UserActivityResponse:
        """Retrieve user activity with 5-minute TTL and request coalescing."""
        limit = min(max(1, limit), 50)
        normalized_username = username.lower().strip()
        cache_key = f"compete:user:activity:{normalized_username}:{limit}"

        async def _fetch():
            return await self.client.get_user_activity(username=username, limit=limit, client=client)

        return await self.cache.get_or_compute(
            key=cache_key,
            ttl_seconds=settings.CACHE_USER_ACTIVITY_TTL_SECONDS,
            fetch_fn=_fetch,
            serializer=lambda a: a.model_dump(),
            deserializer=lambda d: UserActivityResponse(**d),
        )

    async def get_user_problems(
        self,
        username: str,
        limit: int = 50,
        client: Optional[httpx.AsyncClient] = None,
    ) -> UserProblemsResponse:
        """Retrieve user problems with 30-minute TTL and request coalescing."""
        limit = min(max(1, limit), 50)
        normalized_username = username.lower().strip()
        cache_key = f"compete:user:problems:{normalized_username}:{limit}"

        async def _fetch():
            return await self.client.get_user_problems(username=username, limit=limit, client=client)

        return await self.cache.get_or_compute(
            key=cache_key,
            ttl_seconds=settings.CACHE_USER_PROBLEMS_TTL_SECONDS,
            fetch_fn=_fetch,
            serializer=lambda p: p.model_dump(),
            deserializer=lambda d: UserProblemsResponse(**d),
        )

    async def get_question_details(
        self,
        title_slug: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch metadata for a problem not yet present in the local catalog."""
        return await self.client.get_question_details(title_slug=title_slug, client=client)

