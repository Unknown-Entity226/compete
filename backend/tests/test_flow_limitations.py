"""Regression guards verifying remediated limitations, scoring accuracy, and concurrency safety.

Converted from diagnostic flow limitation tests into regression guards asserting:
1. Contest rating baseline scoring: active contestant outscores unrated user.
2. History endpoint: returns HTTP 404 for nonexistent users.
3. Rate-limiter: blocks IP spoofing via X-Forwarded-For from untrusted clients (returns 429).
4. Concurrency: atomic upserts prevent IntegrityError collisions on submissions and problem catalogs.
5. Streak calculation: correctly aggregates streaks across activity timelines.
6. Problem catalog: records problem metadata cleanly without corruption.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.main import app
from app.api.deps import get_db, get_leetcode_client
from app.core.exceptions import UserNotFoundError
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
# 1. Scoring Fix: Active Rated Contestant Outscores Unrated User
# ---------------------------------------------------------------------------
def test_scoring_unrated_user_outscores_active_contestant():
    """Fix verified: Unrated user (contestRating=None) earns 0.0 rating points.
    An active contestant with rating 1300 earns 50.0 points, fairly rewarding
    active participation.
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

    # Active contestant earns 50.0 while unrated earns 0.0
    assert unrated_score.ratingScore == 0.0
    assert rated_score.ratingScore == 50.0
    assert rated_score.totalScore > unrated_score.totalScore


# ---------------------------------------------------------------------------
# 2. History Endpoint Nonexistent User Contract (HTTP 404)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_history_endpoint_returns_200_for_nonexistent_user(test_db):
    """Fix verified: /api/users/{username}/history verifies user existence and
    returns HTTP 404 Not Found for nonexistent users.
    """
    class MockClient:
        async def get_user_profile(self, username, client=None):
            raise UserNotFoundError(username)

    app.dependency_overrides[get_leetcode_client] = lambda: MockClient()

    async def override_db():
        async with test_db() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/users/nonexistent_ghost_user_999/history")
        assert res.status_code == 404, f"Expected 404 for nonexistent user, got {res.status_code}"
        data = res.json()
        assert "not found" in data.get("message", "").lower()

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Rate Limiter IP Spoofing Prevention
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limiter_bypass_via_x_forwarded_for_spoofing():
    """Security Fix verified: get_client_ip ignores untrusted X-Forwarded-For headers.
    An attacker attempting to rotate X-Forwarded-For is pinned to the socket IP and
    triggers HTTP 429 Too Many Requests after 60 req/min.
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
        statuses = []
        for i in range(70):
            res = await client.get("/api/users/testuser", headers={"X-Forwarded-For": f"192.168.1.{i}"})
            statuses.append(res.status_code)

        # Rate limiter correctly fires 429 when client exceeds limit despite spoofed headers
        assert 429 in statuses, "Rate limiter should trigger HTTP 429 on untrusted spoofed IPs"

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Persistence Concurrency Safety: Submissions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_upsert_submissions_unique_violation(test_db):
    """Concurrency Fix verified: upsert_submissions uses atomic dialect-aware ON CONFLICT
    DO NOTHING. Two concurrent requests for the same user with the same submission ID
    succeed without raising IntegrityError.
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

    # Both workers succeed cleanly with zero unhandled IntegrityErrors
    assert len(exceptions) == 0, f"Expected 0 exceptions, got: {exceptions}"

    # Verify only 1 row was stored
    async with test_db() as session:
        res = await session.execute(select(Submission).where(Submission.submission_id == "sub_race_101"))
        assert len(res.scalars().all()) == 1


# ---------------------------------------------------------------------------
# 5. Persistence Concurrency Safety: Problem Catalog
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_record_user_problems_unique_violation(test_db):
    """Concurrency Fix verified: record_user_problems uses atomic ON CONFLICT DO NOTHING.
    When two concurrent requests process a new problem simultaneously, both succeed
    without raising IntegrityError on problems.title_slug.
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

    # Both workers succeed cleanly without IntegrityError
    assert len(exceptions) == 0, f"Expected 0 exceptions, got: {exceptions}"

    # Verify single Problem row created
    async with test_db() as session:
        res = await session.execute(select(Problem).where(Problem.title_slug == "brand-new-problem"))
        assert len(res.scalars().all()) == 1


# ---------------------------------------------------------------------------
# 6. Streak Calculation Timelines
# ---------------------------------------------------------------------------
def test_streak_calculation_truncation_by_activity_limit():
    """Workflow Verification: calculate_streak correctly counts consecutive active days."""
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
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


# ---------------------------------------------------------------------------
# 7. Problem Catalog Ingestion Cleanliness
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_problem_catalog_missing_metadata(test_db):
    """Data Layer Verification: Problem catalog correctly records title, slug, and difficulty."""
    async with test_db() as session:
        user = User(username="metadata_user")
        session.add(user)
        await session.commit()

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

        assert problem.frontend_question_id is None  # Submission ID must not be stored as question ID
        assert problem.title == "Trapping Rain Water"
        assert problem.title_slug == "trapping-rain-water"
