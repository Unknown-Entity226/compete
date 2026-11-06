"""Tests for FastAPI REST endpoints."""
import pytest


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Test health endpoint returns 200 OK when healthy, 503 when unhealthy."""
    response = await async_client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert data["service"] == "CompeteFastAPI"


@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    """Test root endpoint returns API links."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_get_user_profile_endpoint(async_client):
    """Test GET /api/users/{username} returns normalized profile."""
    response = await async_client.get("/api/users/algo_master_99")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "algo_master_99"
    assert data["contestRating"] == 1845
    assert data["problemStats"]["total"] == 450
    assert data["strongestArea"] == "Dynamic Programming"


@pytest.mark.asyncio
async def test_get_user_not_found(async_client):
    """Test GET /api/users/{username} returns 404 for nonexistent user."""
    response = await async_client.get("/api/users/nonexistent_user")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "not found" in data["message"].lower()


@pytest.mark.asyncio
async def test_get_user_activity_endpoint(async_client):
    """Test GET /api/users/{username}/activity returns submission list."""
    response = await async_client.get("/api/users/algo_master_99/activity")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "algo_master_99"
    assert data["total"] == 2
    assert len(data["submissions"]) == 2


@pytest.mark.asyncio
async def test_get_user_problems_endpoint(async_client):
    """Test GET /api/users/{username}/problems returns solved problem list."""
    response = await async_client.get("/api/users/algo_master_99/problems")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "algo_master_99"
    assert len(data["problems"]) == 1
    assert data["problems"][0]["titleSlug"] == "two-sum"


@pytest.mark.asyncio
async def test_compare_users_endpoint(async_client):
    """Test GET /api/compare/{first_user}/{second_user} calculates metrics and frontend format."""
    response = await async_client.get("/api/compare/algo_master_99/binary_ninja")
    assert response.status_code == 200
    data = response.json()

    assert data["comparisonId"] == "algo_master_99-vs-binary_ninja"
    assert data["winner"] == "algo_master_99"
    assert "algo_master_99" in data["score"]
    assert "binary_ninja" in data["score"]
    assert data["score"]["algo_master_99"] > data["score"]["binary_ninja"]

    metrics = data["metrics"]
    assert metrics["ratingDiff"] == 1845 - 1720
    assert metrics["totalSolvedDiff"] == 450 - 415
    assert metrics["higherRankedUser"] == "algo_master_99"

    # Frontend-compatible competitionData verification
    comp_data = data["competitionData"]
    assert "users" in comp_data
    assert len(comp_data["users"]) == 2
    assert comp_data["users"][0]["leetcodeId"] == "algo_master_99"
    assert comp_data["users"][0]["contestRating"] == 1845
    assert comp_data["users"][1]["leetcodeId"] == "binary_ninja"
    assert comp_data["users"][1]["contestRating"] == 1720

