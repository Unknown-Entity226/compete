"""APScheduler asynchronous background worker.

Periodically synchronizes statistics snapshots and velocities for all
registered users in the database, avoiding stale data without client requests.
"""
import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.user import User
from app.services.stats_service import record_snapshot
from app.api.deps import get_leetcode_client

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


async def sync_tracked_users_snapshots() -> int:
    """Scheduled task: iterate through all users in DB and refresh stats snapshot.

    Fetches only usernames (lightweight query), then processes each user in its
    own isolated async session and transaction. A brief delay between upstream
    LeetCode calls avoids triggering rate limits.

    Returns the count of successfully refreshed users.
    """
    logger.info("Starting scheduled background user snapshot synchronization...")
    synced_count = 0
    client = get_leetcode_client()

    # Fetch only usernames — lightweight, avoids loading full ORM objects en masse
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(User.username))
            usernames = [row[0] for row in result.fetchall()]
    except Exception as exc:
        logger.error("Failed to fetch tracked usernames for sync: %s", exc)
        return 0

    if not usernames:
        logger.info("No tracked users in database to sync.")
        return 0

    for username in usernames:
        try:
            profile = await client.get_user_profile(username)
            # Each user gets its own session and transaction — failures are isolated
            async with async_session_factory() as session:
                result = await session.execute(select(User).where(User.username == username))
                user = result.scalar_one_or_none()
                if user is None:
                    logger.debug("User '%s' disappeared between query and sync; skipping.", username)
                    continue
                await record_snapshot(session, user, profile)
                await session.commit()
            synced_count += 1
            logger.debug("Synced snapshot for '%s'.", username)
        except Exception as exc:
            logger.warning(
                "Scheduled sync failed for user '%s': %s",
                username,
                exc,
            )
        # Brief delay to avoid triggering LeetCode upstream rate limits
        await asyncio.sleep(0.5)

    logger.info(
        "Completed background synchronization: refreshed %d/%d users.",
        synced_count,
        len(usernames),
    )
    return synced_count


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

