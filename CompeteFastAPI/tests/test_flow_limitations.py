"""Tests verifying architectural limitations, scoring anomalies, and concurrency edge cases.

These tests prove and document current system limitations across:
1. Contest rating baseline scoring anomaly (unrated outscores rated)
2. History endpoint 404 discrepancy for nonexistent users
3. Rate-limiter IP spoofing via X-Forwarded-For headers
4. Concurrency race conditions in persistence services
5. Streak calculation truncation due to upstream query limits
6. Problem catalog metadata deficiency (missing question numbers and difficulty)
"""
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.main import app
from app.api.deps import get_db, get_leetcode_client
from app.models.base import Base
from app.models.user import User
from app.models.problem import Problem
from app.models.submission import Submission
from app.schemas.user import UserProfileResponse, ProblemStats
from app.schemas.activity import SubmissionItem
from app.schemas.problem import ProblemStatusItem
from app.services.competition_service import CompetitionService
from app.services.problem_service import record_user_problems
from app.services.submission_service import upsert_submissions


@pytest.fixture
async def test_db():
    """Isolated test database sessionmaker and engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Scoring Anomaly: Unrated User Outscores Active Rated Contestant
# ---------------------------------------------------------------------------
def test_scoring_unrated_user_outscores_active_contestant():
    """Limitation: Unrated user (contestRating=None) defaults to 1500 rating,
    earning 150.0 rating points. An active contestant with rating 1300 earns only 50.0,
    unfairly penalizing active participation.
    """
    comp = CompetitionService()

    unrated_profile = UserProfileResponse(
        username="unrated_coder",
        problemStats=ProblemStats(total=20, easy=20, medium=0, hard=0),
        contestRating=None,
        lastUpdated=datetime.now(timezone.utc).isoformat(),
    )
    rated_profile = UserProfileResponse(
        username="active_coder_1300",
        problemStats=ProblemStats(total=20, easy=20, medium=0, hard=0),
        contestRating=1300,
        lastUpdated=datetime.now(timezone.utc).isoformat(),
    )

    unrated_score = comp.compute_user_score(unrated_profile)
    rated_score = comp.compute_user_score(rated_profile)

    # Anomaly demonstration: unrated earns 150.0 while rated 1300 earns 50.0
    assert unrated_score.ratingScore == 150.0
    assert rated_score.ratingScore == 50.0
    assert unrated_score.totalScore > rated_score.totalScore


# ---------------------------------------------------------------------------
# 2. History Endpoint Nonexistent User Discrepancy
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_history_endpoint_returns_200_for_nonexistent_user(test_db):
    """Limitation: /api/users/{username}/history returns HTTP 200 with an empty list
    for nonexistent users instead of returning HTTP 404 Not Found like /api/users/{username}.
    """
    async def override_db():
        async with test_db() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/users/nonexistent_ghost_user_999/history")
        assert res.status_code == 200, (
            "Expected 200 OK currently because get_user_snapshots returns empty list "
            "without verifying user existence"
        )
        data = res.json()
        assert data["username"] == "nonexistent_ghost_user_999"
        assert data["snapshotCount"] == 0
        assert data["snapshots"] == []

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Rate Limiter IP Spoofing via X-Forwarded-For
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limiter_bypass_via_x_forwarded_for_spoofing():
    """Security Limitation: get_client_ip trusts X-Forwarded-For without verifying
    trusted reverse proxies. An attacker sending varying X-Forwarded-For headers
    can exceed the rate limit (60 req/min) indefinitely without triggering HTTP 429.
    """
    class MockClient:
        async def get_user_profile(self, username, client=None):
            return UserProfileResponse(
                username=username,
                problemStats=ProblemStats(total=5, easy=5, medium=0, hard=0),
                lastUpdated=datetime.now(timezone.utc).isoformat(),
            )

    app.dependency_overrides[get_leetcode_client] = lambda: MockClient()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send 70 requests (limit is 60/min) with rotating X-Forwarded-For IPs
        statuses = []
        for i in range(70):
            res = await client.get("/api/users/testuser", headers={"X-Forwarded-For": f"192.168.1.{i}"})
            statuses.append(res.status_code)

        # All 70 requests succeed with 200 OK — rate limiter is completely bypassed!
        assert 429 not in statuses
        assert all(s == 200 for s in statuses)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Persistence Concurrency Collision: Submissions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_upsert_submissions_unique_violation(test_db):
    """Concurrency Limitation: upsert_submissions relies on application-level
    deduplication via select(). Two concurrent requests for the same user with the
    same submission ID collide and raise an IntegrityError upon commit.
    """
    async with test_db() as session:
        user = User(username="race_user")
        session.add(user)
        await session.commit()
        user_id = user.id

    batch = [
        SubmissionItem(
            id="sub_race_101",
            title="Two Sum",
            titleSlug="two-sum",
            status="Accepted",
            lang="python3",
            timestamp=1729000000,
        )
    ]

    async def worker():
        async with test_db() as session:
            async with session.begin():
                user_res = await session.get(User, user_id)
                await upsert_submissions(session, user_res, batch)

    # Run two workers concurrently attempting to persist the same submission
    results = await asyncio.gather(worker(), worker(), return_exceptions=True)
    exceptions = [r for r in results if isinstance(r, Exception)]

    # One worker succeeds, the other fails with IntegrityError (UNIQUE constraint)
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], IntegrityError)


# ---------------------------------------------------------------------------
# 5. Persistence Concurrency Collision: Problem Catalog
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_record_user_problems_unique_violation(test_db):
    """Concurrency Limitation: record_user_problems queries existing problems
    by slug, then creates missing Problem records. When two concurrent requests
    process a new problem, both attempt to insert Problem(title_slug=...) and
    one crashes with an IntegrityError.
    """
    async with test_db() as session:
        u1 = User(username="u1")
        u2 = User(username="u2")
        session.add_all([u1, u2])
        await session.commit()
        u1_id, u2_id = u1.id, u2.id

    problems = [
        ProblemStatusItem(
            id="9999",
            title="Brand New Problem",
            titleSlug="brand-new-problem",
            difficulty="Medium",
            status="SOLVED",
        )
    ]

    async def worker(uid):
        async with test_db() as session:
            async with session.begin():
                user_res = await session.get(User, uid)
                await record_user_problems(session, user_res, problems)

    results = await asyncio.gather(worker(u1_id), worker(u2_id), return_exceptions=True)
    exceptions = [r for r in results if isinstance(r, Exception)]

    # One worker succeeds, the other fails with IntegrityError on problems.title_slug
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], IntegrityError)


# ---------------------------------------------------------------------------
# 6. Streak Calculation Truncation via Upstream Query Limit
# ---------------------------------------------------------------------------
def test_streak_calculation_truncation_by_activity_limit():
    """Workflow Limitation: calculate_streak can only see submissions provided in
    the input list. Because compare.py and users.py fetch at most 20 submissions
    from LeetCode, a 30-day streak is capped at 20 days.
    """
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Generate 30 consecutive days of solves
    all_30_days = [
        SubmissionItem(
            id=str(i),
            title=f"Problem {i}",
            titleSlug=f"problem-{i}",
            status="Accepted",
            lang="python3",
            timestamp=int((now - timedelta(days=i)).timestamp()),
        )
        for i in range(30)
    ]

    true_streak = CompetitionService.calculate_streak(all_30_days, reference_time=now)
    assert true_streak == 30

    # Upstream limit=20 truncation
    fetched_submissions = all_30_days[:20]
    calculated_streak = CompetitionService.calculate_streak(fetched_submissions, reference_time=now)
    assert calculated_streak == 20, (
        f"Streak is artificially limited to {calculated_streak} due to 20-item query limit"
    )


# ---------------------------------------------------------------------------
# 7. Problem Catalog Metadata Deficiencies (Difficulty & Question ID)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_problem_catalog_missing_metadata(test_db):
    """Data Layer Limitation: Problem catalog records created from recent submissions
    have frontend_question_id=None and difficulty='Unknown' because LeetCode's
    recentAcSubmissionList GraphQL query does not provide question number or difficulty.
    """
    async with test_db() as session:
        user = User(username="metadata_user")
        session.add(user)
        await session.commit()

        # Item as received from LeetCode recentAcSubmissionList (no difficulty)
        item = ProblemStatusItem(
            id="1423891024",
            title="Trapping Rain Water",
            titleSlug="trapping-rain-water",
            status="SOLVED",
            timestamp=1729000000,
        )
        await record_user_problems(session, user, [item])
        await session.commit()

        result = await session.execute(
            select(Problem).where(Problem.title_slug == "trapping-rain-water")
        )
        problem = result.scalar_one()

        assert problem.frontend_question_id is None
        assert problem.difficulty == "Unknown"
        assert problem.topic_tags is None

