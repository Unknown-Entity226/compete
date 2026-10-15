"""Head-to-head comparison endpoint."""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_leetcode_client, get_competition_service
from app.core.config import settings
from app.core.limiter import limiter
from app.core.validation import validate_username_str
from app.db.session import async_session_factory
from app.models.statistic import Statistic
from app.services.leetcode_client import LeetCodeClient
from app.services.competition_service import CompetitionService
from app.services.stats_service import get_latest_snapshot
from app.schemas.compare import CompareResponse
from app.schemas.activity import UserActivityResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/compare", tags=["Compare"])


async def _safe_get_activity(
    client: LeetCodeClient, username: str
) -> Optional[UserActivityResponse]:
    """Fetch user activity safely without blocking comparison on upstream failure."""
    try:
        return await client.get_user_activity(username=username, limit=20)
    except Exception as exc:
        logger.debug("Could not fetch recent activity for '%s': %s", username, exc)
        return None


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
    client: LeetCodeClient = Depends(get_leetcode_client),
    competition_service: CompetitionService = Depends(get_competition_service),
) -> CompareResponse:
    first_user = validate_username_str(first_user)
    second_user = validate_username_str(second_user)
    # Query both profiles, activity streams, and historical DB snapshots concurrently
    (
        (first_profile, second_profile),
        (first_activity, second_activity),
        (first_snapshot, second_snapshot),
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
    )

    return await competition_service.compare_profiles(
        first_profile=first_profile,
        second_profile=second_profile,
        first_activity=first_activity,
        second_activity=second_activity,
        first_snapshot=first_snapshot,
        second_snapshot=second_snapshot,
    )
