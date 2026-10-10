"""FastAPI Dependency Injection Providers."""
from functools import lru_cache
from app.services.leetcode_client import LeetCodeClient


@lru_cache()
def get_leetcode_client() -> LeetCodeClient:
    """Dependency that returns a cached singleton LeetCodeClient instance."""
    return LeetCodeClient()

