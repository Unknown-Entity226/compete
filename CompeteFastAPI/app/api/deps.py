"""FastAPI Dependency Injection Providers."""
from functools import lru_cache
from typing import Union
from app.services.cache_service import CacheService
from app.services.leetcode_client import LeetCodeClient
from app.services.cached_leetcode_client import CachedLeetCodeClient


@lru_cache()
def get_cache_service() -> CacheService:
    """Dependency that returns a singleton CacheService instance."""
    return CacheService()


@lru_cache()
def get_leetcode_client() -> Union[CachedLeetCodeClient, LeetCodeClient]:
    """Dependency that returns a singleton CachedLeetCodeClient instance."""
    cache = get_cache_service()
    raw_client = LeetCodeClient()
    return CachedLeetCodeClient(leetcode_client=raw_client, cache_service=cache)
