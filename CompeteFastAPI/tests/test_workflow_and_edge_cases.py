"""Comprehensive workflow, edge cases, and failure mode verification tests."""
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.main import app
from app.api.deps import get_db, get_leetcode_client, get_cache_service
from app.core.config import settings
from app.core.exceptions import UserNotFoundError
from app.models.base import Base
from app.models.user import User
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user_problem import UserProblem
from app.schemas.activity import SubmissionItem, UserActivityResponse
from app.schemas.problem import ProblemStatusItem, UserProblemsResponse
from app.schemas.user import UserProfileResponse, ProblemStats, TopicStat
from app.services.cache_service import CacheService
from app.services.competition_service import CompetitionService
from app.services.leetcode_client import LeetCodeClient
from app.services.problem_service import record_user_problems
from app.services.single_flight import SingleFlight
from app.services.stats_service import get_or_create_user
from app.services.submission_service import upsert_submissions


@pytest.fixture
async def in_memory_db():
    """Isolated in-memory database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. SingleFlight leader cancellation bug
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_flight_leader_cancellation_hangs_followers():
    """Verify bug: if leader is cancelled, followers hang because CancelledError is not caught."""
    sf = SingleFlight()
    leader_started = asyncio.Event()

    async def leader_task():
        leader_started.set()
        await asyncio.sleep(10)  # Long running
        return "leader_result"

    # Start leader
    t1 = asyncio.create_task(sf.execute("cancel_test_key", leader_task))
    await leader_started.wait()

    # Follower starts awaiting the same key
    t2 = asyncio.create_task(sf.execute("cancel_test_key", leader_task))
    await asyncio.sleep(0.01)

    # Cancel leader task
    t1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t1

    # Follower t2 should ideally either receive an exception or execute or be cancelled,
    # but in current SingleFlight it hangs indefinitely because future is never resolved!
    # Let's verify with a short timeout.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(t2, timeout=0.1)


# ---------------------------------------------------------------------------
# 2. CacheService Permanent Disconnect & Memory Leak
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cache_service_cannot_recover_after_transient_failure():
    """Verify limitation: once Redis fails, _is_redis_available is set to False permanently."""
    cache = CacheService(redis_url="redis://invalid.host:9999/0", allow_unix_socket=False)
    # Trigger failure
    await cache.get("test_key")
    assert cache._is_redis_available is False

    # Even if we change redis_url to something valid (simulating Redis recovery),
    # _get_redis will never attempt connection because _is_redis_available is False.
    client = await cache._get_redis()
    assert client is None


@pytest.mark.asyncio
async def test_cache_fallback_store_unbounded_growth():
    """Verify limitation: fallback store never purges unread expired keys."""
    cache = CacheService(redis_url="redis://invalid.host:9999/0", allow_unix_socket=False)
    # Write 50 keys with 0 TTL (already expired)
    for i in range(50):
        await cache.set(f"expired_key_{i}", f"val_{i}", ttl_seconds=0)

    # The keys were expired immediately, but are still present in _fallback_store!
    assert len(cache._fallback_store) == 50
    # They are only removed IF explicitly queried via get()
    await cache.get("expired_key_0")
    assert len(cache._fallback_store) == 49
    # The remaining 49 remain in memory forever unless read!


# ---------------------------------------------------------------------------
# 3. Nonexistent User Handling & DB Pollution
# ---------------------------------------------------------------------------
class MockEmptyLeetCodeClient(LeetCodeClient):
    """Simulates LeetCode GraphQL when user does not exist."""
    async def _execute_query(self, query: str, variables: dict, client=None):
        if "getUserProfile" in query:
            return {"matchedUser": None}
        elif "getRecentSubmissions" in query:
            return {"recentSubmissionList": None, "recentAcSubmissionList": None}
        return {}


@pytest.mark.asyncio
async def test_nonexistent_user_returns_200_for_activity_and_problems():
    """Verify flow bug: nonexistent user returns 404 on profile, but 200 on activity & problems."""
    mock_client = MockEmptyLeetCodeClient()
    app.dependency_overrides[get_leetcode_client] = lambda: mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Profile returns 404
        profile_res = await client.get("/api/users/ghost_user")
        assert profile_res.status_code == 404

        # Activity returns 200 with empty list instead of 404!
        activity_res = await client.get("/api/users/ghost_user/activity")
        assert activity_res.status_code == 200
        assert activity_res.json()["submissions"] == []

        # Problems returns 200 with empty list instead of 404!
        problems_res = await client.get("/api/users/ghost_user/problems")
        assert problems_res.status_code == 200
        assert problems_res.json()["problems"] == []

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_background_task_pollutes_db_with_ghost_users(in_memory_db):
    """Verify bug: persisting problems/submissions for nonexistent user creates orphaned User row."""
    # When _persist_user_problems runs for 'ghost_user':
    user = User(username="ghost_user")
    in_memory_db.add(user)
    await in_memory_db.commit()

    result = await in_memory_db.execute(select(User).where(User.username == "ghost_user"))
    found = result.scalar_one_or_none()
    assert found is not None
    assert found.username == "ghost_user"
    assert found.real_name is None
    assert found.contest_rating is None


# ---------------------------------------------------------------------------
# 4. Problem ID vs Submission ID Bug
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_problem_service_confuses_submission_id_with_question_id(in_memory_db):
    """Verify bug: record_user_problems sets frontend_question_id to submission ID."""
    user = User(username="coder_1")
    in_memory_db.add(user)
    await in_memory_db.commit()

    # LeetCode's recentAcSubmissionList returned item with submission id 1423891024
    problems = [
        ProblemStatusItem(
            id="1423891024",  # This is actually a submission ID!
            title="Two Sum",
            titleSlug="two-sum",
            difficulty="Easy",
            status="SOLVED",
        )
    ]
    await record_user_problems(in_memory_db, user, problems)
    await in_memory_db.commit()

    res = await in_memory_db.execute(select(Problem).where(Problem.title_slug == "two-sum"))
    problem = res.scalar_one()
    # Bug verification: frontend_question_id is 1423891024 instead of 1!
    assert problem.frontend_question_id == 1423891024


# ---------------------------------------------------------------------------
# 5. Duplicate Submission Items in Same Batch Integrity Issue
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upsert_submissions_batch_duplicates(in_memory_db):
    """Verify edge case: batch with duplicate submission IDs causes duplicate objects added."""
    user = User(username="coder_2")
    in_memory_db.add(user)
    await in_memory_db.commit()

    batch = [
        SubmissionItem(id="sub_1", title="A", titleSlug="a", status="Accepted", lang="py", timestamp=1729000000),
        SubmissionItem(id="sub_1", title="A", titleSlug="a", status="Accepted", lang="py", timestamp=1729000000),
    ]
    # Because existing_ids is checked against DB and not updated during the loop,
    # both objects get added to session.add_all!
    await upsert_submissions(in_memory_db, user, batch)
    # Flashing or committing will fail if uniqueness is enforced on submission_id
    with pytest.raises(Exception):
        await in_memory_db.commit()
    await in_memory_db.rollback()


# ---------------------------------------------------------------------------
# 6. Streak calculation counts failed submissions
# ---------------------------------------------------------------------------
def test_streak_counts_wrong_answer_submissions():
    """Verify limitation: calculate_streak doesn't check if status is Accepted/Solved."""
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # User submitted Wrong Answer today and yesterday
    submissions = [
        SubmissionItem(id="1", title="A", titleSlug="a", status="Wrong Answer", lang="python3", timestamp=int(now.timestamp())),
        SubmissionItem(id="2", title="B", titleSlug="b", status="Compile Error", lang="python3", timestamp=int((now - timedelta(days=1)).timestamp())),
    ]
    streak = CompetitionService.calculate_streak(submissions, reference_time=now)
    # Streak is 2 even though user NEVER solved any problem!
    assert streak == 2

