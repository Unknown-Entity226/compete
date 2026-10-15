import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_leetcode_client, get_db
from app.core.config import settings
from app.core.limiter import limiter
from app.core.validation import validate_username_str
from app.db.session import async_session_factory
from app.models.user import User
from app.models.problem import Problem
from app.services.leetcode_client import LeetCodeClientProtocol
from app.services.stats_service import (
    get_or_create_user,
    record_snapshot,
    get_user_snapshots,
)
from app.services.submission_service import upsert_submissions
from app.services.problem_service import record_user_problems
from app.schemas.user import UserProfileResponse
from app.schemas.problem import ProblemStatusItem, UserProblemsResponse
from app.schemas.activity import SubmissionItem, UserActivityResponse
from app.schemas.history import SnapshotEntry, UserHistoryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])


async def _persist_profile_snapshot(profile: UserProfileResponse) -> None:
    """Background task: upsert user and persist a statistics snapshot using an isolated session."""
    try:
        async with async_session_factory() as session:
            user = await get_or_create_user(session, profile)
            await record_snapshot(session, user, profile)
            await session.commit()
            logger.debug("Background snapshot persisted for '%s'", profile.username)
    except Exception as exc:
        logger.warning("Background snapshot failed for '%s': %s", profile.username, exc)


async def _persist_user_problems(
    username: str,
    problems: List[ProblemStatusItem],
    client: LeetCodeClientProtocol,
) -> None:
    """Background task: persist problems and user solve status."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            if user is None:
                logger.debug(
                    "Skipping problem persistence for unregistered user '%s': "
                    "user must be fetched via profile endpoint first.",
                    username,
                )
                return

            slugs = {problem.titleSlug for problem in problems if problem.titleSlug}
            existing_result = await session.execute(
                select(Problem).where(Problem.title_slug.in_(slugs))
            )
            existing_problems = list(existing_result.scalars().all())
            existing_slugs = {problem.title_slug for problem in existing_problems}
            incomplete_slugs = {
                problem.title_slug
                for problem in existing_problems
                if problem.frontend_question_id is None
                or problem.difficulty == "Unknown"
                or problem.topic_tags is None
            }

        # Keep metadata lookups bounded per request so catalog enrichment does
        # not turn one user request into dozens of upstream GraphQL calls.
        missing_slugs = sorted((slugs - existing_slugs) | incomplete_slugs)[:5]
        semaphore = asyncio.Semaphore(5)

        async def _fetch_details(slug: str):
            async with semaphore:
                try:
                    return slug, await client.get_question_details(slug)
                except Exception as exc:
                    logger.debug("Problem metadata lookup failed for '%s': %s", slug, exc)
                    return slug, None

        detail_results = await asyncio.gather(*(_fetch_details(slug) for slug in missing_slugs))
        details_by_slug = {
            slug: details for slug, details in detail_results if details is not None
        }

        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            if user is None:
                return
            inserted = await record_user_problems(
                session,
                user,
                problems,
                problem_details=details_by_slug,
            )
            await session.commit()
            logger.debug("Background user-problems persisted (%d items) for '%s'", inserted, username)
    except Exception as exc:
        logger.warning("Background user-problems persistence failed for '%s': %s", username, exc)


async def _persist_submissions(
    username: str,
    submissions: List[SubmissionItem],
) -> None:
    """Background task: persist submissions using an isolated session."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            if user is None:
                logger.debug(
                    "Skipping submission persistence for unregistered user '%s': "
                    "user must be fetched via profile endpoint first.",
                    username,
                )
                return
            inserted = await upsert_submissions(session, user, submissions)
            await session.commit()
            logger.debug("Background submissions persisted (%d items) for '%s'", inserted, username)
    except Exception as exc:
        logger.warning("Background submissions persistence failed for '%s': %s", username, exc)


@router.get(
    "/{username}",
    response_model=UserProfileResponse,
    summary="Get user profile and statistics",
    description=(
        "Returns normalized LeetCode user statistics, difficulty distribution, "
        "ranking, and top topic areas. Persists a statistics snapshot in the background."
    ),
)
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_user_profile(
    request: Request,
    username: str,
    background_tasks: BackgroundTasks,
    client: LeetCodeClientProtocol = Depends(get_leetcode_client),
) -> UserProfileResponse:
    username = validate_username_str(username)
    profile = await client.get_user_profile(username=username)
    # Persist snapshot asynchronously in the background
    background_tasks.add_task(_persist_profile_snapshot, profile)
    return profile


@router.get(
    "/{username}/problems",
    response_model=UserProblemsResponse,
    summary="Get user's solved problems",
    description="Returns problem status list for the specified LeetCode user.",
)
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_user_problems(
    request: Request,
    username: str,
    background_tasks: BackgroundTasks,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number requested; LeetCode currently returns at most 50",
    ),
    client: LeetCodeClientProtocol = Depends(get_leetcode_client),
) -> UserProblemsResponse:
    username = validate_username_str(username)
    problems_response = await client.get_user_problems(username=username, limit=limit)
    background_tasks.add_task(
        _persist_user_problems,
        username,
        problems_response.problems,
        client,
    )
    return problems_response


@router.get(
    "/{username}/activity",
    response_model=UserActivityResponse,
    summary="Get user's recent submission activity",
    description=(
        "Returns recent submission history. "
        "Persists new submissions to the database in the background."
    ),
)
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_user_activity(
    request: Request,
    username: str,
    background_tasks: BackgroundTasks,
    limit: int = Query(default=20, ge=1, le=50, description="Maximum number of submissions to return"),
    client: LeetCodeClientProtocol = Depends(get_leetcode_client),
) -> UserActivityResponse:
    username = validate_username_str(username)
    activity = await client.get_user_activity(username=username, limit=limit)
    background_tasks.add_task(_persist_submissions, username, activity.submissions)
    return activity


@router.get(
    "/{username}/history",
    response_model=UserHistoryResponse,
    summary="Get user's historical statistics snapshots",
    description=(
        "Returns time-series statistics snapshots from the database, "
        "useful for rendering progress charts and velocity trends."
    ),
)
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_user_history(
    request: Request,
    username: str,
    limit: int = Query(default=30, ge=1, le=90, description="Number of snapshots to return (most recent first)"),
    offset: int = Query(default=0, ge=0, description="Number of snapshots to skip for pagination"),
    from_date: Optional[datetime] = Query(default=None, description="Filter snapshots taken on or after this timestamp"),
    to_date: Optional[datetime] = Query(default=None, description="Filter snapshots taken on or before this timestamp"),
    db: AsyncSession = Depends(get_db),
    client: LeetCodeClientProtocol = Depends(get_leetcode_client),
) -> UserHistoryResponse:
    username = validate_username_str(username)

    # Verify user exists: check DB first; if not in DB, verify with upstream LeetCode
    user_res = await db.execute(select(User).where(User.username == username))
    user = user_res.scalar_one_or_none()
    if user is None:
        # If user does not exist on LeetCode, client raises UserNotFoundError (HTTP 404)
        await client.get_user_profile(username=username)

    snapshots = await get_user_snapshots(
        db,
        username=username,
        limit=limit,
        offset=offset,
        from_date=from_date,
        to_date=to_date,
    )
    return UserHistoryResponse(
        username=username,
        snapshotCount=len(snapshots),
        snapshots=[
            SnapshotEntry(
                snapshotAt=s.snapshot_at.isoformat(),
                totalSolved=s.total_solved,
                easySolved=s.easy_solved,
                mediumSolved=s.medium_solved,
                hardSolved=s.hard_solved,
                contestRating=s.contest_rating,
                globalRanking=s.global_ranking,
                solvingVelocity7d=s.solving_velocity_7d,
                solvingVelocity30d=s.solving_velocity_30d,
            )
            for s in snapshots
        ],
    )
