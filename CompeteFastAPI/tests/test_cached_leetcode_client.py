"""Tests for CachedLeetCodeClient with SingleFlight coalescing."""
import asyncio
import pytest
from app.services.cached_leetcode_client import CachedLeetCodeClient
from app.services.cache_service import CacheService
from tests.conftest import MockLeetCodeClient


class CountingMockLeetCodeClient(MockLeetCodeClient):
    """Mock client that counts query executions."""
    def __init__(self):
        super().__init__()
        self.query_count = 0

    async def _execute_query(self, query: str, variables: dict, client=None):
        self.query_count += 1
        # Artificial delay to simulate network latency
        await asyncio.sleep(0.05)
        return await super()._execute_query(query, variables, client)


@pytest.mark.asyncio
async def test_cached_client_avoids_repeated_upstream_calls():
    """Verify that cached client does not query upstream on subsequent requests."""
    mock_raw = CountingMockLeetCodeClient()
    # Use isolated cache service
    cache = CacheService()
    cached_client = CachedLeetCodeClient(leetcode_client=mock_raw, cache_service=cache)
    
    username = "algo_master_99"
    cache_key = f"compete:user:profile:{username}"
    await cache.delete(cache_key)

    try:
        # 1. First fetch: queries upstream
        p1 = await cached_client.get_user_profile(username)
        assert p1.username == username
        assert mock_raw.query_count == 1

        # 2. Second fetch: served from cache
        p2 = await cached_client.get_user_profile(username)
        assert p2.username == username
        assert mock_raw.query_count == 1  # Query count did not increase!
        assert p1.problemStats.total == p2.problemStats.total
    finally:
        await cache.delete(cache_key)
        await cache.close()


@pytest.mark.asyncio
async def test_cached_client_single_flight_coalescing():
    """Verify that 10 concurrent requests result in only 1 upstream GraphQL fetch."""
    mock_raw = CountingMockLeetCodeClient()
    cache = CacheService()
    cached_client = CachedLeetCodeClient(leetcode_client=mock_raw, cache_service=cache)
    
    username = "algo_master_99"
    cache_key = f"compete:user:profile:{username}"
    await cache.delete(cache_key)

    try:
        # Launch 10 simultaneous profile requests
        profiles = await asyncio.gather(*[
            cached_client.get_user_profile(username)
            for _ in range(10)
        ])

        assert len(profiles) == 10
        for p in profiles:
            assert p.username == username
            assert p.problemStats.total == 450

        # Stampede request coalescing verified: exactly 1 upstream query!
        assert mock_raw.query_count == 1
    finally:
        await cache.delete(cache_key)
        await cache.close()


@pytest.mark.asyncio
async def test_cached_client_activity_and_problems_caching():
    """Verify activity and problem list caching."""
    mock_raw = CountingMockLeetCodeClient()
    cache = CacheService()
    cached_client = CachedLeetCodeClient(leetcode_client=mock_raw, cache_service=cache)

    username = "algo_master_99"
    activity_key = f"compete:user:activity:{username}:20"
    problems_key = f"compete:user:problems:{username}:50"
    await cache.delete(activity_key)
    await cache.delete(problems_key)

    try:
        # Fetch activity twice
        a1 = await cached_client.get_user_activity(username, limit=20)
        a2 = await cached_client.get_user_activity(username, limit=20)
        assert a1.total == a2.total
        assert mock_raw.query_count == 1

        # Fetch problems twice
        p1 = await cached_client.get_user_problems(username, limit=50)
        p2 = await cached_client.get_user_problems(username, limit=50)
        assert p1.total == p2.total
        assert mock_raw.query_count == 2
    finally:
        await cache.delete(activity_key)
        await cache.delete(problems_key)
        await cache.close()

