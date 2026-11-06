"""Head-to-head comparison endpoint."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_leetcode_client, get_competition_service
from app.core.config import settings
from app.core.limiter import limiter
from app.core.validation import validate_username_str
from app.db.session import async_session_factory
from app.models.statistic import Statistic
from app.services.leetcode_client import LeetCodeClientProtocol
from app.services.competition_service import CompetitionService
from app.services.stats_service import get_latest_snapshot
from app.services.submission_service import (
    get_user_recent_solve_slugs,
    get_user_solve_date_timestamps,
)
from app.schemas.compare import CompareResponse
from app.schemas.activity import UserActivityResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/compare", tags=["Compare"])


async def _safe_get_activity(
    client: LeetCodeClientProtocol, username: str
) -> Optional[UserActivityResponse]:
    """Fetch user activity safely without blocking comparison on upstream failure."""
    try:
        return await client.get_user_activity(username=username, limit=50)
    except Exception as exc:
        logger.debug("Could not fetch recent activity for '%s': %s", username, exc)
        return None


async def _safe_get_solve_history(username: str) -> tuple[list[int], list[str], list[str]]:
    """Read saved solve dates and recent distinct solves from existing submissions."""
    try:
        reference_time = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            solve_dates = await get_user_solve_date_timestamps(session, username)
            weekly_slugs = await get_user_recent_solve_slugs(
                session, username, 7, reference_time
            )
            monthly_slugs = await get_user_recent_solve_slugs(
                session, username, 30, reference_time
            )
            return solve_dates, weekly_slugs, monthly_slugs
    except Exception as exc:
        logger.debug("Stored solve history unavailable for '%s': %s", username, exc)
        return [], [], []


async def _safe_get_snapshot(username: str) -> Optional[Statistic]:
    """Retrieve the latest DB snapshot safely if database is accessible."""
    try:
        async with async_session_factory() as session:
            return await get_latest_snapshot(session, username)
    except Exception as exc:
        logger.debug("Database snapshot lookup skipped for '%s': %s", username, exc)
        return None


@router.get(
    "/{first_user}/{second_user}",
    response_model=CompareResponse,
    summary="Compare two LeetCode users head-to-head",
    description=(
        "Concurrently fetches both user profiles and activity, analyzes contest ratings, "
        "difficulty-weighted solves, solving velocity, and consistency streaks to compute "
        "a multi-factor competition duel score."
    ),
)
@limiter.limit(settings.RATE_LIMIT_COMPARE)
async def compare_users(
    request: Request,
    first_user: str,
    second_user: str,
    client: LeetCodeClientProtocol = Depends(get_leetcode_client),
    competition_service: CompetitionService = Depends(get_competition_service),
) -> CompareResponse:
    first_user = validate_username_str(first_user)
    second_user = validate_username_str(second_user)
    if first_user.lower() == second_user.lower():
        raise HTTPException(
            status_code=400,
            detail="Cannot compare a user against themselves. Please specify two distinct usernames.",
        )
    # Query both profiles, activity streams, and historical DB snapshots concurrently
    (
        (first_profile, second_profile),
        (first_activity, second_activity),
        (first_snapshot, second_snapshot),
        (first_solve_history, second_solve_history),
    ) = await asyncio.gather(
        asyncio.gather(
            client.get_user_profile(first_user),
            client.get_user_profile(second_user),
        ),
        asyncio.gather(
            _safe_get_activity(client, first_user),
            _safe_get_activity(client, second_user),
        ),
        asyncio.gather(
            _safe_get_snapshot(first_user),
            _safe_get_snapshot(second_user),
        ),
        asyncio.gather(
            _safe_get_solve_history(first_user),
            _safe_get_solve_history(second_user),
        ),
    )

    return await competition_service.compare_profiles(
        first_profile=first_profile,
        second_profile=second_profile,
        first_activity=first_activity,
        second_activity=second_activity,
        first_snapshot=first_snapshot,
        second_snapshot=second_snapshot,
        first_stored_solve_timestamps=first_solve_history[0],
        second_stored_solve_timestamps=second_solve_history[0],
        first_stored_weekly_slugs=first_solve_history[1],
        second_stored_weekly_slugs=second_solve_history[1],
        first_stored_monthly_slugs=first_solve_history[2],
        second_stored_monthly_slugs=second_solve_history[2],
    )
