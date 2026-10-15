"""Submission persistence repository.

Handles bulk-upsert of recent submission records, avoiding duplicates
via the unique submission_id constraint.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.schemas.activity import SubmissionItem

logger = logging.getLogger(__name__)


def _get_insert_fn(session: AsyncSession):
    """Return the dialect-appropriate atomic insert function."""
    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name == "sqlite":
        return sqlite_insert
    return pg_insert


async def upsert_submissions(
    session: AsyncSession,
    user: User,
    submissions: List[SubmissionItem],
) -> int:
    """Persist new submissions for a user, skipping already-stored ones.

    Links submission to known problems in the catalog when available.
    Uses atomic ON CONFLICT DO NOTHING to eliminate race conditions.
    Returns the count of newly inserted submissions.
    """
    if not submissions:
        return 0

    # Fetch existing submission IDs to avoid duplicates
    existing_ids_result = await session.execute(
        select(Submission.submission_id).where(Submission.user_id == user.id)
    )
    existing_ids = {row[0] for row in existing_ids_result.fetchall()}
    seen_ids = set(existing_ids)  # Track IDs encountered during this batch iteration too

    # Look up existing problems matching submission slugs
    slugs = {item.titleSlug for item in submissions if item.titleSlug}
    problems_by_slug = {}
    if slugs:
        problems_res = await session.execute(
            select(Problem.title_slug, Problem.id).where(Problem.title_slug.in_(slugs))
        )
        problems_by_slug = {row[0]: row[1] for row in problems_res.fetchall()}

    values = []
    for item in submissions:
        if not item.id or item.id in seen_ids:
            continue
        seen_ids.add(item.id)  # Mark as seen to prevent within-batch duplicates
        values.append(
            {
                "id": uuid.uuid4(),
                "user_id": user.id,
                "problem_id": problems_by_slug.get(item.titleSlug),
                "submission_id": item.id,
                "problem_title": item.title,
                "problem_slug": item.titleSlug,
                "status_display": item.status,
                "lang": item.lang,
                "submitted_at": datetime.fromtimestamp(item.timestamp, tz=timezone.utc),
            }
        )

    if values:
        insert_fn = _get_insert_fn(session)
        stmt = (
            insert_fn(Submission)
            .values(values)
            .on_conflict_do_nothing(index_elements=["submission_id"])
            .returning(Submission.id)
        )
        res = await session.execute(stmt)
        inserted_ids = res.scalars().all()
        inserted_count = len(inserted_ids)
        logger.debug(
            "Inserted %d new submissions for user '%s'",
            inserted_count,
            user.username,
        )
        return inserted_count

    return 0

