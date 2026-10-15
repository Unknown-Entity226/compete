"""APScheduler asynchronous background worker.

Periodically synchronizes statistics snapshots and velocities for all
registered users in the database, avoiding stale data without client requests.
"""
import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.user import User
from app.services.stats_service import prune_old_snapshots, record_snapshot
from app.api.deps import get_leetcode_client, get_cache_service

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
_LOCK_TTL_SECONDS = 90
_LOCK_RENEW_SECONDS = 30
_RENEW_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""
_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


async def _renew_lock(redis_client, lock_key: str, lock_token: str, lock_lost: asyncio.Event) -> None:
    while True:
        await asyncio.sleep(_LOCK_RENEW_SECONDS)
        try:
            renewed = await redis_client.eval(
                _RENEW_LOCK_SCRIPT,
                1,
                lock_key,
                lock_token,
                _LOCK_TTL_SECONDS,
            )
        except Exception as exc:
            logger.error("Could not renew scheduler lock; stopping this sync: %s", exc)
            lock_lost.set()
            return
        if not renewed:
            logger.error("Scheduler lock ownership was lost; stopping this sync.")
            lock_lost.set()
            return


async def _sync_users(client, lock_lost: asyncio.Event) -> int:
    """Run one bounded batch at a time while this process owns the lock."""
    try:
        async with async_session_factory() as session:
            pruned = await prune_old_snapshots(session)
            result = await session.execute(select(User.username))
            usernames = [row[0] for row in result.fetchall()]
            await session.commit()
        if pruned:
            logger.info("Pruned %d statistics snapshots beyond the retention window.", pruned)
    except Exception as exc:
        logger.error("Failed to prepare tracked-user sync: %s", exc)
        return 0

    if not usernames:
        logger.info("No tracked users in database to sync.")
        return 0

    concurrency = max(1, settings.BACKGROUND_SYNC_CONCURRENCY)
    semaphore = asyncio.Semaphore(concurrency)

    async def _sync_single_user(username: str) -> bool:
        async with semaphore:
            try:
                profile = await client.get_user_profile(username)
                async with async_session_factory() as session:
                    result = await session.execute(select(User).where(User.username == username))
                    user = result.scalar_one_or_none()
                    if user is None:
                        logger.debug("User '%s' disappeared between query and sync; skipping.", username)
                        return False
                    await record_snapshot(session, user, profile)
                    await session.commit()
                logger.debug("Synced snapshot for '%s'.", username)
                return True
            except Exception as exc:
                logger.warning("Scheduled sync failed for user '%s': %s", username, exc)
                return False
            finally:
                await asyncio.sleep(0.2)

    synced_count = 0
    batch_size = concurrency * 4
    for start in range(0, len(usernames), batch_size):
        if lock_lost.is_set():
            break
        batch = usernames[start : start + batch_size]
        results = await asyncio.gather(*(_sync_single_user(username) for username in batch))
        synced_count += sum(1 for result in results if result)

    logger.info(
        "Completed background synchronization: refreshed %d/%d users.",
        synced_count,
        len(usernames),
    )
    return synced_count


async def sync_tracked_users_snapshots() -> int:
    """Scheduled task: refresh stats snapshots for registered users.

    Uses a Redis distributed lock to ensure only one worker runs the job in
    multi-process/scaled deployments. Processes users concurrently using an
    asyncio.Semaphore pool to prevent timeout bottlenecks.

    Returns the count of successfully refreshed users.
    """
    logger.info("Starting scheduled background user snapshot synchronization...")
    client = get_leetcode_client()
    cache = get_cache_service()
    try:
        redis_client = await cache._get_redis()
    except Exception as exc:
        logger.error("Redis is unavailable; skipping scheduled sync: %s", exc)
        return 0
    lock_key = "compete:scheduler:lock"
    if redis_client is None:
        logger.error("Redis is unavailable; skipping scheduled sync because lock ownership cannot be guaranteed.")
        return 0

    lock_token = uuid4().hex
    try:
        lock_acquired = await redis_client.set(
            lock_key,
            lock_token,
            ex=_LOCK_TTL_SECONDS,
            nx=True,
        )
    except Exception as exc:
        logger.error("Could not acquire scheduler lock; skipping sync: %s", exc)
        return 0
    if not lock_acquired:
        logger.info("Another worker is executing scheduled user sync; skipping.")
        return 0

    lock_lost = asyncio.Event()
    renewal_task = asyncio.create_task(
        _renew_lock(redis_client, lock_key, lock_token, lock_lost)
    )
    sync_task = asyncio.create_task(_sync_users(client, lock_lost))
    lost_task = asyncio.create_task(lock_lost.wait())
    try:
        done, _ = await asyncio.wait(
            {sync_task, lost_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if lost_task in done and not sync_task.done():
            sync_task.cancel()
            await asyncio.gather(sync_task, return_exceptions=True)
            return 0
        return await sync_task
    finally:
        renewal_task.cancel()
        lost_task.cancel()
        await asyncio.gather(renewal_task, lost_task, return_exceptions=True)
        try:
            await redis_client.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)
        except Exception as exc:
            logger.debug("Could not release scheduler lock: %s", exc)


def start_scheduler() -> AsyncIOScheduler:
    """Initialize and start the AsyncIOScheduler background job runner."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.debug("Scheduler already running.")
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone=timezone.utc)

    interval_hours = max(1, settings.SNAPSHOT_SYNC_INTERVAL_HOURS)
    _scheduler.add_job(
        sync_tracked_users_snapshots,
        trigger="interval",
        hours=interval_hours,
        id="sync_tracked_users_snapshots",
        name="Sync Tracked Users Statistics Snapshots",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()
    logger.info(
        "APScheduler started: 'sync_tracked_users_snapshots' scheduled every %d hour(s).",
        interval_hours,
    )
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler background scheduler stopped.")
    _scheduler = None


def get_scheduler_status() -> Dict[str, Any]:
    """Return runtime diagnostic status of the scheduler for health checks."""
    if _scheduler is None or not _scheduler.running:
        return {
            "status": "stopped",
            "running": False,
            "jobs_count": 0,
            "jobs": [],
        }

    jobs_info = [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in _scheduler.get_jobs()
    ]

    return {
        "status": "running",
        "running": True,
        "jobs_count": len(jobs_info),
        "jobs": jobs_info,
    }

