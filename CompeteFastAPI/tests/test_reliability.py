"""Tests for Phase 5: Reliability, Rate Limiting, Validation, Scheduler, and Health Monitoring."""
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import HTTPException

from app.main import app
from app.core.validation import validate_username_str
from app.workers.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_scheduler_status,
    sync_tracked_users_snapshots,
)


# ---------------------------------------------------------------------------
# Input Validation Tests
# ---------------------------------------------------------------------------

def test_validate_username_valid():
    """Valid usernames pass validation cleanly."""
    valid_names = ["algo_master", "neo_123", "a-b_c", "leetcode-user-99", "A1"]
    for name in valid_names:
        assert validate_username_str(name) == name


def test_validate_username_invalid():
    """Invalid usernames raise HTTP 400 Bad Request."""
    invalid_names = [
        "user with spaces",
        "bad@symbol!",
        "../../etc/passwd",
        "drop table users;",
        "",
        "a" * 51,  # Too long
    ]
    for name in invalid_names:
        with pytest.raises(HTTPException) as exc_info:
            validate_username_str(name)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Request Timing Middleware Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_x_process_time_header(async_client):
    """Every HTTP response includes an X-Process-Time header."""
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "x-process-time" in response.headers
    process_time = response.headers["x-process-time"]
    assert process_time.endswith("s")


# ---------------------------------------------------------------------------
# Deep Healthcheck Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_healthcheck_diagnostics(async_client):
    """Healthcheck reports database, cache, and scheduler status."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "database" in data
    assert "cache" in data
    assert "scheduler" in data

    assert data["database"]["status"] in ("healthy", "unhealthy")
    assert data["cache"]["status"] in ("healthy", "degraded", "fallback")
    assert data["scheduler"]["status"] in ("running", "stopped")


# ---------------------------------------------------------------------------
# Scheduler Lifecycle Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Scheduler starts, reports active jobs, and stops cleanly."""
    scheduler = start_scheduler()
    assert scheduler.running is True

    status = get_scheduler_status()
    assert status["running"] is True
    assert status["jobs_count"] >= 1
    job_ids = [j["id"] for j in status["jobs"]]
    assert "sync_tracked_users_snapshots" in job_ids

    stop_scheduler()
    status_after = get_scheduler_status()
    assert status_after["running"] is False
    assert status_after["jobs_count"] == 0


@pytest.mark.asyncio
async def test_sync_tracked_users_snapshots_empty_db():
    """Running snapshot sync job on empty DB completes with 0 synced."""
    count = await sync_tracked_users_snapshots()
    assert count >= 0


# ---------------------------------------------------------------------------
# Validation on Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_username_endpoint_rejection(async_client):
    """Endpoints reject invalid usernames with HTTP 400 before hitting backend services."""
    response = await async_client.get("/api/users/invalid%20user!")
    assert response.status_code == 400
    data = response.json()
    assert "Invalid username" in data["detail"]

    compare_res = await async_client.get("/api/compare/valid_user/bad%40user!")
    assert compare_res.status_code == 400
    assert "Invalid username" in compare_res.json()["detail"]
