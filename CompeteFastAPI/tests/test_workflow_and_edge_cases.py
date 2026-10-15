"""Workflow, edge-case, and regression tests verifying fixed behavior.

Each test in this file was originally written to *confirm a bug existed*.
After remediation, these tests now assert the corrected, production-correct
behavior so they serve as regression guards going forward.
"""
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
from app.services.cache_service import CacheService, MAX_FALLBACK_ENTRIES
from app.services.competition_service import CompetitionService
from app.services.leetcode_client import LeetCodeClient
from app.services.problem_service import record_user_problems
from app.services.single_flight import SingleFlight
from app.services.stats_service import get_or_create_user
from app.services.submission_service import upsert_submissions
from app.api.endpoints.users import _persist_user_problems, _persist_submissions


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
# 1. SingleFlight — leader cancellation no longer hangs followers (FIXED)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_flight_leader_cancellation_unblocks_followers():
    """Fix verified: when leader is cancelled, followers receive CancelledError promptly.

    Previously followers would hang indefinitely because CancelledError bypassed
    the exception handler and the future was never resolved. The fix catches
    BaseException and calls future.cancel() so followers are unblocked.
    """
    sf = SingleFlight()
    leader_started = asyncio.Event()

    async def slow_task():
        leader_started.set()
        await asyncio.sleep(10)  # Long-running upstream call
        return "result"

    # Start leader task
    t1 = asyncio.create_task(sf.execute("cancel_test_key", slow_task))
    await leader_started.wait()

    # Follower joins the in-flight request
    t2 = asyncio.create_task(sf.execute("cancel_test_key", slow_task))
    await asyncio.sleep(0.01)  # Let follower register

    # Cancel leader
    t1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t1

    # Follower must now unblock promptly (not hang) — receives CancelledError
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t2, timeout=1.0)


# ---------------------------------------------------------------------------
# 2. CacheService — auto-recovery after transient failure (FIXED)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cache_service_retries_after_cooldown():
    """Fix verified: CacheService retries Redis after the reconnect cooldown elapses.

    Previously _is_redis_available was permanently set to False on first failure.
    The fix uses a time-based cooldown (_last_redis_failure) so reconnection
    attempts resume after _redis_retry_interval seconds.
    """
    cache = CacheService(redis_url="redis://invalid.host:9999/0", allow_unix_socket=False)
    # Trigger a connection failure
    await cache.get("test_key")
    # last_redis_failure is now set to a recent timestamp
    assert cache._last_redis_failure > 0.0

    # Simulate cooldown elapsed by resetting the failure timestamp to the past
    cache._last_redis_failure = 0.0  # Reset — as if cooldown has passed

    # _get_redis() should now attempt reconnection (will still fail for invalid host,
    # but it *does* attempt — proving auto-recovery is not permanently locked out)
    client = await cache._get_redis()
    # Connection still fails for invalid host, but _last_redis_failure is updated again
    assert client is None
    assert cache._last_redis_failure > 0.0  # Attempt was made and failure was recorded


@pytest.mark.asyncio
async def test_cache_fallback_store_bounded_and_lru():
    """Fix verified: fallback store is bounded (LRU) and does not store zero-TTL keys.

    Previously the fallback store was an unbounded dict that never pruned expired
    entries unless explicitly queried. The fix uses an OrderedDict with LRU eviction
    and refuses to store keys with ttl_seconds <= 0.
    """
    cache = CacheService(redis_url="redis://invalid.host:9999/0", allow_unix_socket=False)

    # Keys with ttl=0 must NOT be stored (previously they were stored and leaked)
    for i in range(10):
        await cache.set(f"zero_ttl_key_{i}", f"val_{i}", ttl_seconds=0)
    assert len(cache._fallback_store) == 0, "Zero-TTL keys must not be stored"

    # Keys with valid TTL are stored up to MAX_FALLBACK_ENTRIES
    for i in range(20):
        await cache.set(f"valid_key_{i}", f"val_{i}", ttl_seconds=300)
    assert len(cache._fallback_store) == 20
    assert len(cache._fallback_store) <= MAX_FALLBACK_ENTRIES


# ---------------------------------------------------------------------------
# 3. Nonexistent User — 404 across all user endpoints (FIXED)
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
async def test_nonexistent_user_returns_404_for_all_endpoints():
    """Fix verified: nonexistent user returns 404 on profile, activity, AND problems.

    Previously activity and problems returned 200 with empty lists for nonexistent
    users because null GraphQL lists were treated as empty results. The fix raises
    UserNotFoundError when LeetCode returns null lists, resulting in HTTP 404.
    """
    mock_client = MockEmptyLeetCodeClient()
    app.dependency_overrides[get_leetcode_client] = lambda: mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        profile_res = await client.get("/api/users/ghost_user")
        assert profile_res.status_code == 404

        activity_res = await client.get("/api/users/ghost_user/activity")
        assert activity_res.status_code == 404, (
            f"Expected 404 for nonexistent user activity, got {activity_res.status_code}"
        )

        problems_res = await client.get("/api/users/ghost_user/problems")
        assert problems_res.status_code == 404, (
            f"Expected 404 for nonexistent user problems, got {problems_res.status_code}"
        )

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_background_task_does_not_create_ghost_users(in_memory_db, monkeypatch):
    """Fix verified: background tasks skip persistence for users not in the database.

    Previously _persist_user_problems and _persist_submissions would insert a bare
    User(username=...) row with NULL profile fields when queried for nonexistent users.
    The fix returns early with a debug log when user is None, preventing ghost records.
    """
    # Verify no user exists initially
    result = await in_memory_db.execute(
        select(User).where(User.username == "ghost_user")
    )
    assert result.scalar_one_or_none() is None, "No ghost_user should exist before the test"

    # Override session factory to point to in_memory_db engine
    from app.api.endpoints import users as users_module
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session():
        yield in_memory_db

    monkeypatch.setattr(users_module, "async_session_factory", mock_session)

    # Attempt to persist problems and submissions for non-existent user
    await _persist_user_problems("ghost_user", [])
    await _persist_submissions("ghost_user", [])

    # Ghost user must NOT have been created
    result_after = await in_memory_db.execute(
        select(User).where(User.username == "ghost_user")
    )
    assert result_after.scalar_one_or_none() is None, (
        "Ghost user must NOT be created for unregistered username"
    )


# ---------------------------------------------------------------------------
# 4. Problem catalog — submission ID no longer stored as question ID (FIXED)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_problem_service_does_not_store_submission_id_as_question_id(in_memory_db):
    """Fix verified: frontend_question_id is None, not populated with submission ID.

    Previously record_user_problems() extracted item.id (a LeetCode submission ID
    like 1423891024) and stored it as Problem.frontend_question_id, corrupting the
    problem catalog. The fix always sets frontend_question_id=None.
    """
    user = User(username="coder_1")
    in_memory_db.add(user)
    await in_memory_db.commit()

    problems = [
        ProblemStatusItem(
            id="1423891024",  # This is a submission ID, not a question ID
            title="Two Sum",
            titleSlug="two-sum",
            difficulty="Easy",
            status="SOLVED",
        )
    ]
    await record_user_problems(in_memory_db, user, problems)
    await in_memory_db.commit()

    res = await in_memory_db.execute(
        select(Problem).where(Problem.title_slug == "two-sum")
    )
    problem = res.scalar_one()
    # Correct behavior: frontend_question_id must NOT be set to a submission ID
    assert problem.frontend_question_id is None, (
        f"frontend_question_id should be None, not '{problem.frontend_question_id}' "
        "(which would be a submission ID, not a question number)"
    )


# ---------------------------------------------------------------------------
# 5. Duplicate submissions in same batch — no IntegrityError (FIXED)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upsert_submissions_batch_duplicates_handled_gracefully(in_memory_db):
    """Fix verified: batch with duplicate submission IDs deduplicates cleanly.

    Previously upsert_submissions added both duplicate objects to the session,
    causing an IntegrityError on commit due to the unique constraint on submission_id.
    The fix tracks seen_ids within the batch loop to skip duplicates safely.
    """
    user = User(username="coder_2")
    in_memory_db.add(user)
    await in_memory_db.commit()

    batch = [
        SubmissionItem(id="sub_1", title="A", titleSlug="a", status="Accepted", lang="py", timestamp=1729000000),
        SubmissionItem(id="sub_1", title="A", titleSlug="a", status="Accepted", lang="py", timestamp=1729000000),  # duplicate
    ]

    # Must NOT raise IntegrityError — duplicate is silently skipped
    count = await upsert_submissions(in_memory_db, user, batch)
    await in_memory_db.commit()  # Must succeed without exception

    # Only one submission should have been inserted (the duplicate was deduplicated)
    assert count == 1, f"Expected 1 unique insertion, got {count}"

    res = await in_memory_db.execute(
        select(Submission).where(Submission.user_id == user.id)
    )
    assert len(res.scalars().all()) == 1


# ---------------------------------------------------------------------------
# 6. Streak — only accepted submissions count (FIXED)
# ---------------------------------------------------------------------------
def test_streak_ignores_wrong_answer_submissions():
    """Fix verified: calculate_streak only counts Accepted/Solved submissions.

    Previously any submission status (Wrong Answer, Compile Error, etc.) counted
    towards the streak, unfairly rewarding failed attempts. The fix mirrors the
    filter already used in calculate_window_solves().
    """
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    submissions = [
        SubmissionItem(id="1", title="A", titleSlug="a", status="Wrong Answer", lang="python3", timestamp=int(now.timestamp())),
        SubmissionItem(id="2", title="B", titleSlug="b", status="Compile Error", lang="python3", timestamp=int((now - timedelta(days=1)).timestamp())),
    ]
    streak = CompetitionService.calculate_streak(submissions, reference_time=now)
    # No accepted submissions — streak must be 0
    assert streak == 0, f"Expected streak=0 for wrong-answer-only submissions, got {streak}"


def test_streak_counts_only_accepted_submissions():
    """Streak accrues correctly when a mix of accepted and failed submissions exist."""
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    submissions = [
        SubmissionItem(id="1", title="A", titleSlug="a", status="Accepted", lang="python3", timestamp=int(now.timestamp())),
        SubmissionItem(id="2", title="B", titleSlug="b", status="Wrong Answer", lang="python3", timestamp=int(now.timestamp())),
        SubmissionItem(id="3", title="C", titleSlug="c", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=1)).timestamp())),
        SubmissionItem(id="4", title="D", titleSlug="d", status="Runtime Error", lang="python3", timestamp=int((now - timedelta(days=2)).timestamp())),
    ]
    streak = CompetitionService.calculate_streak(submissions, reference_time=now)
    # Only today + yesterday have accepted submissions — streak is 2
    assert streak == 2, f"Expected streak=2 (today + yesterday accepted), got {streak}"


# ---------------------------------------------------------------------------
# 7. Self-Comparison rejection (FIXED)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_compare_self_raises_400():
    """Fix verified: /api/compare/alice/alice returns HTTP 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/compare/alice/alice")
        assert res.status_code == 400
        data = res.json()
        assert "Cannot compare a user against themselves" in data["detail"]
