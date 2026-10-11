"""SingleFlight Request Coalescer.

Prevents cache stampedes by ensuring that only one in-flight execution of a
coroutine occurs for a given key at any given time. Concurrent callers await
the leader's result and receive the identical value or exception.
"""
import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SingleFlight:
    """Async single-flight request coalescer."""

    def __init__(self) -> None:
        self._calls: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        key: str,
        fn: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Execute fn if no call is in-flight for key; otherwise await in-flight call."""
        is_leader = False
        future: asyncio.Future

        async with self._lock:
            if key in self._calls:
                future = self._calls[key]
                logger.debug("SingleFlight: Request coalesced for key '%s'", key)
            else:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                self._calls[key] = future
                is_leader = True

        if is_leader:
            try:
                result = await fn()
                if not future.done():
                    future.set_result(result)
                return result
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)
                raise
            finally:
                async with self._lock:
                    self._calls.pop(key, None)
        else:
            # Follower waits for leader's execution to resolve
            return await asyncio.shield(future)

