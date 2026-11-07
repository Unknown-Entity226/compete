"""Redis cache with database and in-memory fallbacks plus SingleFlight coalescing."""
import asyncio
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple, TypeVar
import redis.asyncio as aioredis

from app.core.config import settings
from app.services.database_cache_service import DatabaseCacheService
from app.services.single_flight import SingleFlight

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_FALLBACK_ENTRIES = 10_000


class CacheService:
    """Redis cache backed by persistent SQL and bounded local memory."""

    def __init__(
        self,
        redis_url: str = settings.REDIS_URL,
        fallback_enabled: bool = True,
        allow_unix_socket: bool = True,
        database_cache: Optional[DatabaseCacheService] = None,
    ) -> None:
        self.redis_url = redis_url
        self.fallback_enabled = fallback_enabled
        self.allow_unix_socket = allow_unix_socket
        self._redis: Optional[aioredis.Redis] = None
        self._database_cache = database_cache or DatabaseCacheService()
        self._redis_lock = asyncio.Lock()
        self._single_flight = SingleFlight()
        # In-memory fallback storage: key -> (value_str, expire_timestamp)
        self._fallback_store: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        self._last_redis_failure: float = 0.0
        self._redis_retry_interval: float = 30.0

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """Obtain or lazily initialize the Redis client pool."""
        if self._redis is not None:
            return self._redis

        async with self._redis_lock:
            if self._redis is not None:
                return self._redis

            now = time.monotonic()
            if (
                self._last_redis_failure
                and now - self._last_redis_failure < self._redis_retry_interval
            ):
                return None

            urls_to_try = [self.redis_url]
            import os
            if self.allow_unix_socket and os.path.exists("/tmp/redis.sock"):
                urls_to_try.append("unix:///tmp/redis.sock")

            for url in urls_to_try:
                client = aioredis.from_url(
                    url,
                    decode_responses=True,
                    socket_connect_timeout=1.5,
                    socket_timeout=1.5,
                )
                try:
                    await client.ping()
                    self._redis = client
                    self._last_redis_failure = 0.0
                    logger.info("Connected to Redis at %s", url)
                    return client
                except asyncio.CancelledError:
                    await self._close_redis_client(client)
                    raise
                except Exception as e:
                    logger.debug("Failed connecting to Redis at %s: %s", url, e)
                    await self._close_redis_client(client)

            logger.warning(
                "Unable to connect to Redis at %s. Using %s.",
                self.redis_url,
                "database and in-memory fallbacks" if self.fallback_enabled else "no fallback",
            )
            self._last_redis_failure = time.monotonic()
            return None

    async def _mark_redis_unavailable(self, client: aioredis.Redis) -> None:
        """Drop a failed client and allow a reconnect after the cooldown."""
        should_close = False
        async with self._redis_lock:
            if self._redis is client:
                self._redis = None
                self._last_redis_failure = time.monotonic()
                should_close = True
        if should_close:
            try:
                await self._close_redis_client(client)
            except Exception:
                pass

    @staticmethod
    async def _close_redis_client(client: aioredis.Redis) -> None:
        try:
            await client.aclose()
        except Exception as exc:
            logger.debug("Failed closing Redis client: %s", exc)

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a cached string value by key."""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                value = await redis_client.get(key)
                if value is not None:
                    return value
            except Exception as e:
                logger.warning("Redis GET failed for key '%s': %s. Falling back to database.", key, e)
                await self._mark_redis_unavailable(redis_client)
                redis_client = None

        # SQL cache is shared by application workers and survives Redis restarts.
        if not self.fallback_enabled:
            return None
        database_value = await self._database_cache.get(key)
        if database_value is not None:
            value, remaining_ttl = database_value
            self._store_in_memory(key, value, remaining_ttl)
            # Redis may have restarted or been cleared. Refill it without
            # extending the cache entry's original expiration.
            if redis_client is not None:
                try:
                    await redis_client.set(key, value, ex=remaining_ttl)
                except Exception as exc:
                    logger.debug("Redis read-through SET failed for key '%s': %s", key, exc)
                    await self._mark_redis_unavailable(redis_client)
            return value

        # Final fallback for a database outage or isolated local cache.
        if key in self._fallback_store:
            val, expire_at = self._fallback_store[key]
            if time.monotonic() < expire_at:
                self._fallback_store.move_to_end(key)
                return val
            # Expired
            self._fallback_store.pop(key, None)
        return None

    async def set(self, key: str, value: str, ttl_seconds: int = 300) -> bool:
        """Store a string value with TTL in seconds."""
        if ttl_seconds <= 0:
            await self.delete(key)
            return True

        redis_client = await self._get_redis()
        stored = False
        if redis_client:
            try:
                await redis_client.set(key, value, ex=ttl_seconds)
                stored = True
            except Exception as e:
                logger.warning("Redis SET failed for key '%s': %s. Falling back to database.", key, e)
                await self._mark_redis_unavailable(redis_client)

        # Write-through keeps a durable copy ready for Redis failover.
        if not self.fallback_enabled:
            return stored

        stored = await self._database_cache.set(key, value, ttl_seconds) or stored
        self._store_in_memory(key, value, ttl_seconds)
        return True  # The bounded memory tier accepted the write.

    def _store_in_memory(self, key: str, value: str, ttl_seconds: int) -> None:
        """Keep a bounded, process-local copy for a database outage."""
        expire_at = time.monotonic() + ttl_seconds
        self._fallback_store[key] = (value, expire_at)
        self._fallback_store.move_to_end(key)

        # Opportunistically purge expired entries when approaching capacity
        if len(self._fallback_store) > 0.8 * MAX_FALLBACK_ENTRIES:
            now = time.monotonic()
            expired_keys = [k for k, (_, exp) in self._fallback_store.items() if exp < now]
            for k in expired_keys:
                del self._fallback_store[k]

        # Hard cap: evict oldest entries if still over limit
        while len(self._fallback_store) > MAX_FALLBACK_ENTRIES:
            self._fallback_store.popitem(last=False)

    async def get_json(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize JSON value."""
        raw = await self.get(key)
        if raw is not None:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Corrupted JSON in cache key '%s'", key)
                # Remove only the corrupt Redis/local copy first so a valid
                # database replica can restore the key.
                self._fallback_store.pop(key, None)
                redis_client = await self._get_redis()
                if redis_client:
                    try:
                        await redis_client.delete(key)
                    except Exception as exc:
                        logger.debug("Could not remove corrupt Redis key '%s': %s", key, exc)
                        await self._mark_redis_unavailable(redis_client)
                database_raw = await self.get(key)
                if database_raw is not None:
                    try:
                        return json.loads(database_raw)
                    except json.JSONDecodeError:
                        logger.warning("Corrupted JSON in database cache key '%s'", key)
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
            except Exception as exc:
                logger.debug("Redis DELETE failed for key '%s': %s", key, exc)
                await self._mark_redis_unavailable(redis_client)
        if self.fallback_enabled:
            await self._database_cache.delete(key)
        self._fallback_store.pop(key, None)
        return True

    async def clear_all(self) -> None:
        """Clear all entries from every cache tier."""
        self._fallback_store.clear()
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.flushdb()
            except Exception as exc:
                logger.debug("Redis flush failed: %s", exc)
                await self._mark_redis_unavailable(redis_client)
        if self.fallback_enabled:
            await self._database_cache.clear_all()

    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connectivity status."""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.ping()
                return {"status": "connected", "backend": "redis"}
            except Exception as exc:
                logger.debug("Redis health check failed: %s", exc)
                await self._mark_redis_unavailable(redis_client)
        if self.fallback_enabled:
            if await self._database_cache.health_check():
                return {"status": "fallback", "backend": "database"}
            return {"status": "degraded", "backend": "in-memory-fallback"}
        return {"status": "unhealthy", "backend": "unavailable"}

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
        async with self._redis_lock:
            redis_client = self._redis
            self._redis = None
        if redis_client:
            await self._close_redis_client(redis_client)
