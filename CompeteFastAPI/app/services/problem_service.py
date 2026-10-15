"""Problem and UserProblem persistence repository.

Handles cataloging problems into the problems table and tracking
user-to-problem solve states in the user_problems table.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.problem import Problem
from app.models.user import User
from app.models.user_problem import UserProblem
from app.schemas.problem import ProblemStatusItem

logger = logging.getLogger(__name__)


def _get_insert_fn(session: AsyncSession):
    """Return the dialect-appropriate atomic insert function."""
    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name == "sqlite":
        return sqlite_insert
    return pg_insert


async def record_user_problems(
    session: AsyncSession,
    user: User,
    problems: List[ProblemStatusItem],
    problem_details: Optional[Dict[str, Dict[str, Any]]] = None,
) -> int:
    """Upsert problems and user-problem associations.

    1. Ensures each problem exists in the `problems` catalog table via atomic ON CONFLICT DO NOTHING.
    2. Upserts `user_problems` tracking the solve status and timestamps atomically.
    Returns the count of user problems processed.
    """
    if not problems:
        return 0

    recorded_count = 0
    slugs = list({p.titleSlug for p in problems if p.titleSlug})

    # Pre-fetch existing problems by slug
    existing_problems_res = await session.execute(
        select(Problem).where(Problem.title_slug.in_(slugs))
    )
    existing_problems = {p.title_slug: p for p in existing_problems_res.scalars().all()}

    # Insert any missing problems atomically
    problem_details = problem_details or {}
    missing_problems_by_slug = {}
    for item in problems:
        if (
            item.titleSlug
            and item.titleSlug not in existing_problems
            and item.titleSlug not in missing_problems_by_slug
        ):
            missing_problems_by_slug[item.titleSlug] = {
                "id": uuid.uuid4(),
                "frontend_question_id": problem_details.get(item.titleSlug, {}).get("frontendQuestionId"),
                "title": item.title,
                "title_slug": item.titleSlug,
                "difficulty": problem_details.get(item.titleSlug, {}).get("difficulty") or item.difficulty or "Unknown",
                "topic_tags": problem_details.get(item.titleSlug, {}).get("topicTags"),
            }

    if missing_problems_by_slug:
        insert_fn = _get_insert_fn(session)
        stmt = (
            insert_fn(Problem)
            .values(list(missing_problems_by_slug.values()))
            .on_conflict_do_nothing(index_elements=["title_slug"])
        )
        await session.execute(stmt)

        # Refresh existing_problems map to retrieve full Problem entities
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
            continue

        details = problem_details.get(item.titleSlug)
        if details:
            if details.get("frontendQuestionId") is not None:
                problem.frontend_question_id = details["frontendQuestionId"]
            if details.get("difficulty"):
                problem.difficulty = details["difficulty"]
            if details.get("topicTags") is not None:
                problem.topic_tags = details["topicTags"]

        solved_datetime = None
        if item.timestamp:
            solved_datetime = datetime.fromtimestamp(item.timestamp, tz=timezone.utc)
        elif item.status == "SOLVED":
            solved_datetime = datetime.now(timezone.utc)

        user_problem = existing_user_problems.get(problem.id)
        if user_problem is None:
            insert_fn = _get_insert_fn(session)
            stmt_up = (
                insert_fn(UserProblem)
                .values(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    problem_id=problem.id,
                    status=item.status or "SOLVED",
                    solved_at=solved_datetime,
                    last_attempted_at=solved_datetime or datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["user_id", "problem_id"])
            )
            await session.execute(stmt_up)

            up_res = await session.execute(
                select(UserProblem).where(
                    UserProblem.user_id == user.id,
                    UserProblem.problem_id == problem.id,
                )
            )
            user_problem = up_res.scalar_one_or_none()
            if user_problem:
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

