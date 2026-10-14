"""User and statistics CRUD (Create, Read, Upsert) repository.

Handles all database interactions for the User and Statistic models —
upsert-on-fetch, snapshot insertion, and velocity calculation.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.models.user import User
from app.models.statistic import Statistic
from app.schemas.user import UserProfileResponse

logger = logging.getLogger(__name__)


async def get_or_create_user(
    session: AsyncSession,
    profile: UserProfileResponse,
) -> User:
    """Upsert a user row from a normalized profile response.

    If the user already exists, updates their mutable profile fields
    (real_name, avatar_url, contest_rating, global_ranking).
    Returns the User ORM object (already attached to the session).
    """
    result = await session.execute(
        select(User).where(User.username == profile.username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            username=profile.username,
            real_name=profile.realName,
            avatar_url=profile.avatarUrl,
            contest_rating=profile.contestRating,
            global_ranking=profile.globalRanking,
        )
        session.add(user)
        logger.info("Created new user record for '%s'", profile.username)
    else:
        # Refresh mutable fields
        user.real_name = profile.realName
        user.avatar_url = profile.avatarUrl
        user.contest_rating = profile.contestRating
        user.global_ranking = profile.globalRanking
        logger.debug("Updated existing user record for '%s'", profile.username)

    await session.flush()  # Obtain the user.id without committing
    return user


async def compute_solving_velocity(
    session: AsyncSession,
    user_id: uuid.UUID,
    current_total: int,
    window_days: int,
) -> float:
    """Calculate average daily solve rate over the last N days.

    Finds the oldest snapshot *within* the window (i.e. snapshot_at >= cutoff)
    and computes (current_total - baseline_total) / elapsed_days.

    Returns 0.0 if no reference snapshot exists within the window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # Oldest snapshot inside the window → gives us the longest possible baseline
    result = await session.execute(
        select(Statistic)
        .where(
            Statistic.user_id == user_id,
            Statistic.snapshot_at >= cutoff,
        )
        .order_by(Statistic.snapshot_at.asc())
        .limit(1)
    )
    reference_snapshot = result.scalar_one_or_none()

    if reference_snapshot is None:
        return 0.0

    delta_solved = max(0, current_total - reference_snapshot.total_solved)
    elapsed_days = max(
        1,
        (datetime.now(timezone.utc) - reference_snapshot.snapshot_at).days,
    )
    return round(delta_solved / elapsed_days, 2)


async def record_snapshot(
    session: AsyncSession,
    user: User,
    profile: UserProfileResponse,
    min_interval_seconds: Optional[int] = None,
) -> Statistic:
    """Persist a historical statistics snapshot for a user.

    Calculates 7-day and 30-day solving velocity from prior snapshots,
    then inserts a new Statistic row. If a recent snapshot exists within
    min_interval_seconds with identical total_solved, avoids duplicate insertion.
    """
    if min_interval_seconds is None:
        min_interval_seconds = settings.SNAPSHOT_MIN_INTERVAL_SECONDS

    current_total = profile.problemStats.total

    if min_interval_seconds > 0:
        latest = await get_latest_snapshot(session, user.username)
        if latest is not None:
            elapsed = (datetime.now(timezone.utc) - latest.snapshot_at).total_seconds()
            if elapsed < min_interval_seconds and latest.total_solved == current_total:
                logger.debug(
                    "Skipping duplicate snapshot for '%s': last snapshot was %.1fs ago (< %ds limit)",
                    user.username,
                    elapsed,
                    min_interval_seconds,
                )
                return latest

    velocity_7d = await compute_solving_velocity(
        session, user.id, current_total, window_days=7
    )
    velocity_30d = await compute_solving_velocity(
        session, user.id, current_total, window_days=30
    )

    snapshot = Statistic(
        user_id=user.id,
        total_solved=current_total,
        easy_solved=profile.problemStats.easy,
        medium_solved=profile.problemStats.medium,
        hard_solved=profile.problemStats.hard,
        contest_rating=profile.contestRating,
        global_ranking=profile.globalRanking,
        solving_velocity_7d=velocity_7d,
        solving_velocity_30d=velocity_30d,
        snapshot_at=datetime.now(timezone.utc),
    )
    session.add(snapshot)
    logger.debug(
        "Recorded snapshot for '%s': total=%d, v7d=%.2f, v30d=%.2f",
        user.username,
        current_total,
        velocity_7d,
        velocity_30d,
    )
    return snapshot


async def get_user_snapshots(
    session: AsyncSession,
    username: str,
    limit: int = 30,
) -> List[Statistic]:
    """Retrieve the most recent N historical snapshots for a user."""
    result = await session.execute(
        select(Statistic)
        .join(User, User.id == Statistic.user_id)
        .where(User.username == username)
        .order_by(Statistic.snapshot_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_snapshot(
    session: AsyncSession,
    username: str,
) -> Optional[Statistic]:
    """Return the single most-recent snapshot for a user, or None."""
    result = await session.execute(
        select(Statistic)
        .join(User, User.id == Statistic.user_id)
        .where(User.username == username)
        .order_by(Statistic.snapshot_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
