"""Problem and UserProblem persistence repository.

Handles cataloging problems into the problems table and tracking
user-to-problem solve states in the user_problems table.
"""
import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.problem import Problem
from app.models.user import User
from app.models.user_problem import UserProblem
from app.schemas.problem import ProblemStatusItem

logger = logging.getLogger(__name__)


async def record_user_problems(
    session: AsyncSession,
    user: User,
    problems: List[ProblemStatusItem],
) -> int:
    """Upsert problems and user-problem associations.

    1. Ensures each problem exists in the `problems` catalog table.
    2. Upserts `user_problems` tracking the solve status and timestamps.
    Returns the count of user problems processed.
    """
    if not problems:
        return 0

    recorded_count = 0
    slugs = [p.titleSlug for p in problems if p.titleSlug]

    # Pre-fetch existing problems by slug
    existing_problems_res = await session.execute(
        select(Problem).where(Problem.title_slug.in_(slugs))
    )
    existing_problems = {p.title_slug: p for p in existing_problems_res.scalars().all()}

    # Pre-fetch existing user_problems for this user
    existing_up_res = await session.execute(
        select(UserProblem)
        .where(UserProblem.user_id == user.id)
    )
    existing_user_problems = {up.problem_id: up for up in existing_up_res.scalars().all()}

    for item in problems:
        if not item.titleSlug:
            continue

        problem = existing_problems.get(item.titleSlug)

        if problem is None:
            problem = Problem(
                frontend_question_id=None,  # LeetCode item.id is a submission ID, not question ID
                title=item.title,
                title_slug=item.titleSlug,
                difficulty=item.difficulty or "Unknown",
            )
            session.add(problem)
            await session.flush()
            existing_problems[item.titleSlug] = problem
        # Note: frontend_question_id is intentionally left None
        # as item.id from recentAcSubmissionList is a submission ID, not the question number

        # Now link user_problem
        solved_datetime = None
        if item.timestamp:
            solved_datetime = datetime.fromtimestamp(item.timestamp, tz=timezone.utc)
        elif item.status == "SOLVED":
            solved_datetime = datetime.now(timezone.utc)

        user_problem = existing_user_problems.get(problem.id)
        if user_problem is None:
            user_problem = UserProblem(
                user_id=user.id,
                problem_id=problem.id,
                status=item.status or "SOLVED",
                solved_at=solved_datetime,
                last_attempted_at=solved_datetime or datetime.now(timezone.utc),
            )
            session.add(user_problem)
            existing_user_problems[problem.id] = user_problem
            recorded_count += 1
        else:
            # Update existing state if changed
            if item.status and user_problem.status != item.status:
                user_problem.status = item.status
            if solved_datetime and not user_problem.solved_at:
                user_problem.solved_at = solved_datetime
            user_problem.last_attempted_at = solved_datetime or datetime.now(timezone.utc)
            recorded_count += 1

    logger.debug(
        "Recorded %d user-problem entries for user '%s'",
        recorded_count,
        user.username,
    )
    return recorded_count


async def get_user_problems_from_db(
    session: AsyncSession,
    username: str,
    limit: int = 50,
) -> List[UserProblem]:
    """Retrieve user-problem records joined with problem details."""
    result = await session.execute(
        select(UserProblem)
        .join(User, User.id == UserProblem.user_id)
        .options(selectinload(UserProblem.problem))
        .where(User.username == username)
        .order_by(UserProblem.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

