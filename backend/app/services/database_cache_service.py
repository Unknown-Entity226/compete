"""SQL-backed cache store used as the durable Redis fallback."""
import asyncio
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.session import async_session_factory
from app.models.cache_entry import CacheEntry

logger = logging.getLogger(__name__)


class DatabaseCacheService:
    """Persist serialized cache values in the application's SQL database."""

    def __init__(self, session_factory=async_session_factory) -> None:
        self._session_factory = session_factory
        self._operation_timeout_seconds = 2.0
        self._last_prune = 0.0
        self._prune_interval_seconds = 300.0

    async def get(self, key: str) -> Optional[Tuple[str, int]]:
        """Return a value and remaining TTL, removing it if it has expired."""
        try:
            async with asyncio.timeout(self._operation_timeout_seconds):
                async with self._session_factory() as session:
                    result = await session.execute(
                        select(CacheEntry.value, CacheEntry.expires_at).where(
                            CacheEntry.key == key
                        )
                    )
                    entry = result.one_or_none()
                    if entry is None:
                        return None

                    expires_at = entry.expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    remaining = math.ceil(
                        (expires_at - datetime.now(timezone.utc)).total_seconds()
                    )
                    if remaining <= 0:
                        await session.execute(
                            delete(CacheEntry).where(CacheEntry.key == key)
                        )
                        await session.commit()
                        return None
                    return entry.value, remaining
        except Exception as exc:
            logger.warning("Database cache GET failed for key '%s': %s", key, exc)
            return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Upsert a value with an absolute expiry timestamp."""
        if ttl_seconds <= 0:
            return await self.delete(key)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        values = {"key": key, "value": value, "expires_at": expires_at}
        try:
            async with asyncio.timeout(self._operation_timeout_seconds):
                async with self._session_factory() as session:
                    bind = session.get_bind()
                    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
                    if dialect_name == "sqlite":
                        insert = sqlite_insert
                    else:
                        insert = pg_insert

                    statement = insert(CacheEntry).values(**values).on_conflict_do_update(
                        index_elements=[CacheEntry.key],
                        set_={"value": value, "expires_at": expires_at},
                    )
                    await session.execute(statement)
                    await session.commit()
            await self._maybe_prune_expired()
            return True
        except Exception as exc:
            logger.warning("Database cache SET failed for key '%s': %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        """Remove a value from the SQL cache."""
        try:
            async with asyncio.timeout(self._operation_timeout_seconds):
                async with self._session_factory() as session:
                    await session.execute(delete(CacheEntry).where(CacheEntry.key == key))
                    await session.commit()
            return True
        except Exception as exc:
            logger.warning("Database cache DELETE failed for key '%s': %s", key, exc)
            return False

    async def clear_all(self) -> bool:
        """Remove all persistent cache values."""
        try:
            async with asyncio.timeout(self._operation_timeout_seconds):
                async with self._session_factory() as session:
                    await session.execute(delete(CacheEntry))
                    await session.commit()
            return True
        except Exception as exc:
            logger.warning("Database cache clear failed: %s", exc)
            return False

    async def health_check(self) -> bool:
        """Check whether the database can serve cache reads."""
        try:
            async with asyncio.timeout(self._operation_timeout_seconds):
                async with self._session_factory() as session:
                    await session.execute(select(CacheEntry.key).limit(1))
            return True
        except Exception as exc:
            logger.debug("Database cache health probe failed: %s", exc)
            return False

    async def _maybe_prune_expired(self) -> None:
        """Periodically remove expired rows that are never requested again."""
        now = time.monotonic()
        if now - self._last_prune < self._prune_interval_seconds:
            return
        self._last_prune = now
        try:
            async with asyncio.timeout(self._operation_timeout_seconds):
                async with self._session_factory() as session:
                    await session.execute(
                        delete(CacheEntry).where(
                            CacheEntry.expires_at <= datetime.now(timezone.utc)
                        )
                    )
                    await session.commit()
        except Exception as exc:
            logger.debug("Database cache expiry cleanup failed: %s", exc)
