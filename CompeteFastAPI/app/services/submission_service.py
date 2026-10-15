"""Submission persistence repository.

Handles bulk-upsert of recent submission records, avoiding duplicates
via the unique submission_id constraint.
"""
import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.schemas.activity import SubmissionItem

logger = logging.getLogger(__name__)


async def upsert_submissions(
    session: AsyncSession,
    user: User,
    submissions: List[SubmissionItem],
) -> int:
    """Persist new submissions for a user, skipping already-stored ones.

    Links submission to known problems in the catalog when available.
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

    new_submissions: List[Submission] = []
    for item in submissions:
        if not item.id or item.id in seen_ids:
            continue
        seen_ids.add(item.id)  # Mark as seen to prevent within-batch duplicates
        new_submissions.append(
            Submission(
                user_id=user.id,
                problem_id=problems_by_slug.get(item.titleSlug),
                submission_id=item.id,
                problem_title=item.title,
                problem_slug=item.titleSlug,
                status_display=item.status,
                lang=item.lang,
                submitted_at=datetime.fromtimestamp(item.timestamp, tz=timezone.utc),
            )
        )

    if new_submissions:
        session.add_all(new_submissions)
        logger.debug(
            "Inserted %d new submissions for user '%s'",
            len(new_submissions),
            user.username,
        )

    return len(new_submissions)

