"""Redis and In-Memory Fallback Cache Service with SingleFlight Coalescing."""
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple, TypeVar
import redis.asyncio as aioredis

from app.core.config import settings
from app.services.single_flight import SingleFlight

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheService:
    """Async Cache Service backed by Redis with in-memory TTL fallback and coalescing."""

    def __init__(
        self,
        redis_url: str = settings.REDIS_URL,
        fallback_enabled: bool = True,
        allow_unix_socket: bool = True,
    ) -> None:
        self.redis_url = redis_url
        self.fallback_enabled = fallback_enabled
        self.allow_unix_socket = allow_unix_socket
        self._redis: Optional[aioredis.Redis] = None
        self._single_flight = SingleFlight()
        # In-memory fallback storage: key -> (value_str, expire_timestamp)
        self._fallback_store: Dict[str, Tuple[str, float]] = {}
        self._is_redis_available = True

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """Obtain or lazily initialize the Redis client pool."""
        if self._redis is None and self._is_redis_available:
            urls_to_try = [self.redis_url]
            import os
            if self.allow_unix_socket and os.path.exists("/tmp/redis.sock"):
                urls_to_try.append("unix:///tmp/redis.sock")

            connected = False
            for url in urls_to_try:
                try:
                    client = aioredis.from_url(
                        url,
                        decode_responses=True,
                        socket_connect_timeout=1.5,
                        socket_timeout=1.5,
                    )
                    await client.ping()
                    self._redis = client
                    logger.info("Connected to Redis at %s", url)
                    connected = True
                    break
                except Exception as e:
                    logger.debug("Failed connecting to Redis at %s: %s", url, e)

            if not connected:
                logger.warning(
                    "Unable to connect to Redis at %s. Using in-memory fallback cache.",
                    self.redis_url,
                )
                self._is_redis_available = False
                self._redis = None
        return self._redis

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a cached string value by key."""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                return await redis_client.get(key)
            except Exception as e:
                logger.warning("Redis GET failed for key '%s': %s. Falling back to memory.", key, e)
                self._is_redis_available = False

        # In-memory fallback
        if key in self._fallback_store:
            val, expire_at = self._fallback_store[key]
            if time.time() < expire_at:
                return val
            # Expired
            self._fallback_store.pop(key, None)
        return None

    async def set(self, key: str, value: str, ttl_seconds: int = 300) -> bool:
        """Store a string value with TTL in seconds."""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.set(key, value, ex=ttl_seconds)
                return True
            except Exception as e:
                logger.warning("Redis SET failed for key '%s': %s. Falling back to memory.", key, e)
                self._is_redis_available = False

        # In-memory fallback
        expire_at = time.time() + ttl_seconds
        self._fallback_store[key] = (value, expire_at)
        return True

    async def get_json(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize JSON value."""
        raw = await self.get(key)
        if raw is not None:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Corrupted JSON in cache key '%s'", key)
                await self.delete(key)
        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Serialize and store a JSON value with TTL."""
        try:
            raw = json.dumps(value)
            return await self.set(key, raw, ttl_seconds=ttl_seconds)
        except (TypeError, ValueError) as e:
            logger.error("Failed to serialize cache value for key '%s': %s", key, e)
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.delete(key)
            except Exception:
                pass
        self._fallback_store.pop(key, None)
        return True

    async def clear_all(self) -> None:
        """Clear all entries from in-memory fallback."""
        self._fallback_store.clear()
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.flushdb()
            except Exception:
                pass

    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connectivity status."""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.ping()
                return {"status": "connected", "backend": "redis"}
            except Exception:
                pass
        return {"status": "degraded", "backend": "in-memory-fallback"}

    async def get_or_compute(
        self,
        key: str,
        ttl_seconds: int,
        fetch_fn: Callable[[], Coroutine[Any, Any, T]],
        serializer: Callable[[T], Any] = lambda x: x,
        deserializer: Callable[[Any], T] = lambda x: x,
    ) -> T:
        """Get cached value, or compute it safely using SingleFlight coalescing."""
        # 1. Fast path: cache hit
        cached_raw = await self.get_json(key)
        if cached_raw is not None:
            logger.debug("Cache HIT for key '%s'", key)
            return deserializer(cached_raw)

        logger.debug("Cache MISS for key '%s'", key)

        # 2. Coalesce concurrent requests for this key
        async def _fetch_and_cache() -> T:
            # Check cache again inside leader in case another leader finished
            raw = await self.get_json(key)
            if raw is not None:
                return deserializer(raw)

            data = await fetch_fn()
            # Store in cache
            serialized = serializer(data)
            await self.set_json(key, serialized, ttl_seconds=ttl_seconds)
            return data

        return await self._single_flight.execute(key, _fetch_and_cache)

    async def close(self) -> None:
        """Close connection pool."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
