"""Tests for Phase 3: Persistence — stats_service, submission_service, and problem_service."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.main import app
from app.api.deps import get_db, get_leetcode_client
from app.models.base import Base
from app.models.user import User
from app.models.problem import Problem
from app.models.user_problem import UserProblem
from app.models.statistic import Statistic
from app.models.submission import Submission
from app.schemas.user import UserProfileResponse, ProblemStats, TopicStat
from app.schemas.problem import ProblemStatusItem
from app.schemas.activity import SubmissionItem
from app.services.stats_service import (
    get_or_create_user,
    record_snapshot,
    get_user_snapshots,
    get_latest_snapshot,
    compute_solving_velocity,
)
from app.services.submission_service import upsert_submissions
from app.services.problem_service import (
    record_user_problems,
    get_user_problems_from_db,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def async_db_session():
    """In-memory async SQLite session for testing persistence services."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _make_profile(
    username: str = "test_coder",
    total: int = 300,
    easy: int = 100,
    medium: int = 150,
    hard: int = 50,
    rating: int = 1750,
    ranking: int = 10000,
) -> UserProfileResponse:
    return UserProfileResponse(
        username=username,
        realName="Test Coder",
        avatarUrl=None,
        contestRating=rating,
        globalRanking=ranking,
        problemStats=ProblemStats(total=total, easy=easy, medium=medium, hard=hard),
        strongestArea="Dynamic Programming",
        topicStats=[TopicStat(topic="Dynamic Programming", count=50)],
        lastUpdated=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# get_or_create_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_or_create_user_creates_new(async_db_session):
    """Creating a user for the first time inserts a row."""
    profile = _make_profile(username="new_coder")
    user = await get_or_create_user(async_db_session, profile)
    await async_db_session.commit()

    assert user.id is not None
    assert user.username == "new_coder"
    assert user.contest_rating == 1750
    assert user.global_ranking == 10000


@pytest.mark.asyncio
async def test_get_or_create_user_upserts_existing(async_db_session):
    """Fetching an existing user updates mutable profile fields without creating duplicates."""
    initial_profile = _make_profile(username="returning_coder", rating=1700, ranking=15000)
    initial_user = await get_or_create_user(async_db_session, initial_profile)
    await async_db_session.commit()
    original_id = initial_user.id

    updated_profile = _make_profile(username="returning_coder", rating=1800, ranking=12000)
    updated_user = await get_or_create_user(async_db_session, updated_profile)
    await async_db_session.commit()

    # Same DB row, updated fields
    assert updated_user.id == original_id
    assert updated_user.contest_rating == 1800
    assert updated_user.global_ranking == 12000


# ---------------------------------------------------------------------------
# record_snapshot & throttling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_snapshot_inserts_row(async_db_session):
    """Recording a snapshot persists a Statistic row with correct values."""
    profile = _make_profile(username="snap_coder", total=400)
    user = await get_or_create_user(async_db_session, profile)
    snapshot = await record_snapshot(async_db_session, user, profile)
    await async_db_session.commit()

    assert snapshot.id is not None
    assert snapshot.user_id == user.id
    assert snapshot.total_solved == 400
    assert snapshot.easy_solved == 100
    assert snapshot.medium_solved == 150
    assert snapshot.hard_solved == 50
    assert snapshot.contest_rating == 1750


@pytest.mark.asyncio
async def test_record_snapshot_velocity_no_history(async_db_session):
    """Velocity is 0.0 when no prior snapshot exists."""
    profile = _make_profile(username="fresh_coder", total=50)
    user = await get_or_create_user(async_db_session, profile)
    snapshot = await record_snapshot(async_db_session, user, profile)
    await async_db_session.commit()

    assert snapshot.solving_velocity_7d == 0.0
    assert snapshot.solving_velocity_30d == 0.0


@pytest.mark.asyncio
async def test_record_snapshot_velocity_with_history(async_db_session):
    """Velocity is calculated from an older snapshot within the window."""
    profile = _make_profile(username="velocity_coder", total=100)
    user = await get_or_create_user(async_db_session, profile)

    # Manually insert an "old" snapshot 14 days ago with 86 solved
    old_snap = Statistic(
        user_id=user.id,
        total_solved=86,
        easy_solved=50,
        medium_solved=30,
        hard_solved=6,
        solving_velocity_7d=0.0,
        solving_velocity_30d=0.0,
        snapshot_at=datetime.now(timezone.utc) - timedelta(days=14),
    )
    async_db_session.add(old_snap)
    await async_db_session.commit()

    # 100 - 86 = 14 solved over 14 days → 1.0 per day over 30-day window
    current_profile = _make_profile(username="velocity_coder", total=100)
    snapshot = await record_snapshot(async_db_session, user, current_profile, min_interval_seconds=0)
    await async_db_session.commit()

    assert snapshot.solving_velocity_7d == 0.0   # No snapshot within 7 days
    assert snapshot.solving_velocity_30d == 1.0  # 14/14 = 1.0/day over 30-day window


@pytest.mark.asyncio
async def test_record_snapshot_throttles_rapid_duplicate_calls(async_db_session):
    """Snapshot calls within min_interval_seconds return the existing snapshot."""
    profile = _make_profile(username="rapid_coder", total=200)
    user = await get_or_create_user(async_db_session, profile)

    first_snap = await record_snapshot(async_db_session, user, profile, min_interval_seconds=300)
    await async_db_session.commit()

    # Immediate second call with same total
    second_snap = await record_snapshot(async_db_session, user, profile, min_interval_seconds=300)
    await async_db_session.commit()

    assert first_snap.id == second_snap.id

    # Verify only one row was inserted into DB
    result = await async_db_session.execute(
        select(Statistic).where(Statistic.user_id == user.id)
    )
    assert len(result.scalars().all()) == 1


# ---------------------------------------------------------------------------
# get_user_snapshots / get_latest_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_snapshots_returns_ordered(async_db_session):
    """Snapshots are returned most-recent-first and limited correctly."""
    profile = _make_profile(username="history_coder")
    user = await get_or_create_user(async_db_session, profile)

    for i in range(5):
        snap = Statistic(
            user_id=user.id,
            total_solved=100 + i * 10,
            easy_solved=50,
            medium_solved=40,
            hard_solved=10 + i,
            solving_velocity_7d=0.0,
            solving_velocity_30d=0.0,
            snapshot_at=datetime.now(timezone.utc) - timedelta(days=5 - i),
        )
        async_db_session.add(snap)
    await async_db_session.commit()

    snapshots = await get_user_snapshots(async_db_session, "history_coder", limit=3)
    assert len(snapshots) == 3
    # Most recent first
    assert snapshots[0].total_solved > snapshots[1].total_solved

    # Pagination offset test
    page_2 = await get_user_snapshots(async_db_session, "history_coder", limit=2, offset=2)
    assert len(page_2) == 2
    assert page_2[0].id == snapshots[2].id

    # Date filter test
    now = datetime.now(timezone.utc)
    filtered = await get_user_snapshots(
        async_db_session,
        "history_coder",
        from_date=now - timedelta(days=2),
    )
    assert len(filtered) >= 1
    assert all(s.snapshot_at >= now - timedelta(days=2, hours=1) for s in filtered)


@pytest.mark.asyncio
async def test_get_latest_snapshot(async_db_session):
    """get_latest_snapshot returns only the single most recent entry."""
    profile = _make_profile(username="latest_coder")
    user = await get_or_create_user(async_db_session, profile)

    for days_ago in [7, 3, 1]:
        snap = Statistic(
            user_id=user.id,
            total_solved=100 + (7 - days_ago) * 5,
            easy_solved=50,
            medium_solved=40,
            hard_solved=10,
            solving_velocity_7d=0.0,
            solving_velocity_30d=0.0,
            snapshot_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        )
        async_db_session.add(snap)
    await async_db_session.commit()

    latest = await get_latest_snapshot(async_db_session, "latest_coder")
    assert latest is not None
    assert latest.total_solved == 130


# ---------------------------------------------------------------------------
# upsert_submissions & foreign key linking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_submissions_inserts_new_and_links_problem(async_db_session):
    """New submissions are persisted and link to known catalog problems."""
    profile = _make_profile(username="sub_coder")
    user = await get_or_create_user(async_db_session, profile)

    # Pre-populate problems catalog with Two Sum
    known_problem = Problem(
        frontend_question_id=1,
        title="Two Sum",
        title_slug="two-sum",
        difficulty="Easy",
    )
    async_db_session.add(known_problem)
    await async_db_session.commit()

    submissions = [
        SubmissionItem(id="s1", title="Two Sum", titleSlug="two-sum", status="Accepted", lang="python3", timestamp=1729000000),
        SubmissionItem(id="s2", title="Valid Parentheses", titleSlug="valid-parentheses", status="Accepted", lang="python3", timestamp=1728990000),
    ]
    count = await upsert_submissions(async_db_session, user, submissions)
    await async_db_session.commit()

    assert count == 2

    # Verify that s1 linked to known_problem.id and s2 has problem_id=None
    res = await async_db_session.execute(
        select(Submission).where(Submission.user_id == user.id).order_by(Submission.submission_id)
    )
    rows = res.scalars().all()
    assert rows[0].submission_id == "s1"
    assert rows[0].problem_id == known_problem.id
    assert rows[1].submission_id == "s2"
    assert rows[1].problem_id is None

    # Insert same submissions again — should be skipped (count = 0)
    count_again = await upsert_submissions(async_db_session, user, submissions)
    await async_db_session.commit()
    assert count_again == 0


@pytest.mark.asyncio
async def test_upsert_submissions_partial_update(async_db_session):
    """Only new submissions are inserted when mixed with existing ones."""
    profile = _make_profile(username="partial_sub_coder")
    user = await get_or_create_user(async_db_session, profile)

    first_batch = [
        SubmissionItem(id="p1", title="Problem 1", titleSlug="problem-1", status="Accepted", lang="java", timestamp=1729000000),
    ]
    await upsert_submissions(async_db_session, user, first_batch)
    await async_db_session.commit()

    second_batch = [
        SubmissionItem(id="p1", title="Problem 1", titleSlug="problem-1", status="Accepted", lang="java", timestamp=1729000000),
        SubmissionItem(id="p2", title="Problem 2", titleSlug="problem-2", status="Wrong Answer", lang="java", timestamp=1729001000),
    ]
    count = await upsert_submissions(async_db_session, user, second_batch)
    await async_db_session.commit()

    assert count == 1  # Only p2 is new


# ---------------------------------------------------------------------------
# problem_service (Problem and UserProblem tracking)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_user_problems_creates_problem_and_association(async_db_session):
    """record_user_problems creates Problem entries and UserProblem associations."""
    profile = _make_profile(username="problem_coder")
    user = await get_or_create_user(async_db_session, profile)

    problems = [
        ProblemStatusItem(id="1", title="Two Sum", titleSlug="two-sum", difficulty="Easy", status="SOLVED", timestamp=1729000000),
        ProblemStatusItem(id="2", title="Add Two Numbers", titleSlug="add-two-numbers", difficulty="Medium", status="ATTEMPTED", timestamp=1728990000),
    ]
    recorded = await record_user_problems(async_db_session, user, problems)
    await async_db_session.commit()

    assert recorded == 2

    # Query back from DB
    user_problems = await get_user_problems_from_db(async_db_session, "problem_coder")
    assert len(user_problems) == 2

    # Check status and problem association
    slugs = {up.problem.title_slug: up.status for up in user_problems}
    assert slugs["two-sum"] == "SOLVED"
    assert slugs["add-two-numbers"] == "ATTEMPTED"


@pytest.mark.asyncio
async def test_record_user_problems_updates_status(async_db_session):
    """Recording an updated status for an existing problem updates the record."""
    profile = _make_profile(username="updating_coder")
    user = await get_or_create_user(async_db_session, profile)

    initial = [
        ProblemStatusItem(id="3", title="Longest Substring", titleSlug="longest-substring", difficulty="Medium", status="ATTEMPTED"),
    ]
    await record_user_problems(async_db_session, user, initial)
    await async_db_session.commit()

    # Now user solves it
    solved = [
        ProblemStatusItem(id="3", title="Longest Substring", titleSlug="longest-substring", difficulty="Medium", status="SOLVED", timestamp=1729050000),
    ]
    await record_user_problems(async_db_session, user, solved)
    await async_db_session.commit()

    user_problems = await get_user_problems_from_db(async_db_session, "updating_coder")
    assert len(user_problems) == 1
    assert user_problems[0].status == "SOLVED"
    assert user_problems[0].solved_at is not None


# ---------------------------------------------------------------------------
# API Integration: /api/users/{username}/history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_history_api(async_db_session):
    """Test GET /api/users/{username}/history returns historical snapshots."""
    profile = _make_profile(username="api_history_coder", total=150)
    user = await get_or_create_user(async_db_session, profile)

    snap = Statistic(
        user_id=user.id,
        total_solved=150,
        easy_solved=50,
        medium_solved=80,
        hard_solved=20,
        contest_rating=1820,
        global_ranking=15000,
        solving_velocity_7d=3.5,
        solving_velocity_30d=2.1,
        snapshot_at=datetime.now(timezone.utc),
    )
    async_db_session.add(snap)
    await async_db_session.commit()

    # Override get_db to return our in-memory async session
    async def override_get_db():
        yield async_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/users/api_history_coder/history")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "api_history_coder"
    assert data["snapshotCount"] == 1
    assert len(data["snapshots"]) == 1
    first_snapshot = data["snapshots"][0]
    assert first_snapshot["totalSolved"] == 150
    assert first_snapshot["contestRating"] == 1820
    assert first_snapshot["solvingVelocity7d"] == 3.5
