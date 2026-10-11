"""Tests for CacheService (Redis and In-Memory Fallback)."""
import asyncio
import pytest
from app.services.cache_service import CacheService


@pytest.mark.asyncio
async def test_cache_service_set_and_get():
    """Verify storing and retrieving string values."""
    cache = CacheService()
    try:
        await cache.set("test:greeting", "hello_world", ttl_seconds=10)
        value = await cache.get("test:greeting")
        assert value == "hello_world"
    finally:
        await cache.delete("test:greeting")
        await cache.close()


@pytest.mark.asyncio
async def test_cache_service_json_serialization():
    """Verify storing and retrieving complex JSON dicts."""
    cache = CacheService()
    payload = {"username": "test_dev", "score": 98.5, "tags": ["graph", "dp"]}
    try:
        await cache.set_json("test:json_data", payload, ttl_seconds=10)
        fetched = await cache.get_json("test:json_data")
        assert fetched == payload
    finally:
        await cache.delete("test:json_data")
        await cache.close()


@pytest.mark.asyncio
async def test_cache_service_get_or_compute():
    """Verify get_or_compute caches results and avoids redundant computations."""
    cache = CacheService()
    compute_count = 0

    async def compute_data():
        nonlocal compute_count
        compute_count += 1
        return {"data": 42}

    key = "test:computed_key"
    try:
        # First call: computes and stores in cache
        first = await cache.get_or_compute(key, ttl_seconds=60, fetch_fn=compute_data)
        assert first == {"data": 42}
        assert compute_count == 1

        # Second call: returns cached without computing
        second = await cache.get_or_compute(key, ttl_seconds=60, fetch_fn=compute_data)
        assert second == {"data": 42}
        assert compute_count == 1
    finally:
        await cache.delete(key)
        await cache.close()


@pytest.mark.asyncio
async def test_in_memory_fallback():
    """Verify that in-memory fallback works when Redis is forced unavailable."""
    # Point to an invalid unreachable Redis URL and disable socket fallback
    cache = CacheService(redis_url="redis://127.0.0.1:59999/0", allow_unix_socket=False)
    try:
        await cache.set("fallback:key", "fallback_val", ttl_seconds=10)
        val = await cache.get("fallback:key")
        assert val == "fallback_val"

        health = await cache.health_check()
        assert health["backend"] == "in-memory-fallback"
    finally:
        await cache.close()
