"""Tests for LeetCode GraphQL adapter service."""
import pytest
import httpx
from app.services.leetcode_client import LeetCodeClient
from app.core.exceptions import (
    UserNotFoundError,
    UpstreamRateLimitError,
    UpstreamServiceError,
)
from tests.conftest import (
    MOCK_GRAPHQL_USER_DATA,
    MOCK_GRAPHQL_SUBMISSIONS_DATA,
)


@pytest.mark.asyncio
async def test_get_user_profile_success(mock_leetcode_client):
    """Test successful user profile retrieval and data normalization."""
    profile = await mock_leetcode_client.get_user_profile("algo_master_99")
    
    assert profile.username == "algo_master_99"
    assert profile.contestRating == 1845
    assert profile.globalRanking == 14205
    assert profile.problemStats.total == 450
    assert profile.problemStats.easy == 150
    assert profile.problemStats.medium == 250
    assert profile.problemStats.hard == 50
    assert profile.strongestArea == "Dynamic Programming"
    assert len(profile.topicStats) == 3
    assert profile.topicStats[0].topic == "Dynamic Programming"
    assert profile.topicStats[0].count == 85


@pytest.mark.asyncio
async def test_get_user_profile_not_found(mock_leetcode_client):
    """Test that querying a nonexistent user raises UserNotFoundError."""
    with pytest.raises(UserNotFoundError) as exc_info:
        await mock_leetcode_client.get_user_profile("nonexistent_user")
    assert "nonexistent_user" in str(exc_info.value)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_user_activity(mock_leetcode_client):
    """Test recent submissions normalization."""
    activity = await mock_leetcode_client.get_user_activity("algo_master_99")
    
    assert activity.username == "algo_master_99"
    assert activity.total == 2
    assert activity.submissions[0].title == "Two Sum"
    assert activity.submissions[0].status == "Accepted"
    assert activity.submissions[1].status == "Wrong Answer"


@pytest.mark.asyncio
async def test_get_user_problems(mock_leetcode_client):
    """Test user problem status list normalization."""
    problems_resp = await mock_leetcode_client.get_user_problems("algo_master_99")
    
    assert problems_resp.username == "algo_master_99"
    assert problems_resp.total == 1
    assert problems_resp.problems[0].titleSlug == "two-sum"
    assert problems_resp.problems[0].status == "SOLVED"


@pytest.mark.asyncio
async def test_rate_limit_handling():
    """Test that upstream 429 raises UpstreamRateLimitError."""
    client = LeetCodeClient(max_retries=1, backoff_factor=1.0)

    def mock_transport(request):
        return httpx.Response(status_code=429)

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
    with pytest.raises(UpstreamRateLimitError):
        await client._execute_query("query { test }", {}, client=mock_http)
    await mock_http.aclose()


@pytest.mark.asyncio
async def test_server_error_handling():
    """Test that upstream 500 raises UpstreamServiceError."""
    client = LeetCodeClient(max_retries=1, backoff_factor=1.0)

    def mock_transport(request):
        return httpx.Response(status_code=500)

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
    with pytest.raises(UpstreamServiceError):
        await client._execute_query("query { test }", {}, client=mock_http)
    await mock_http.aclose()


@pytest.mark.asyncio
async def test_get_question_details():
    """Test get_question_details parses question number, difficulty, and tags."""
    client = LeetCodeClient()

    def mock_transport(request):
        return httpx.Response(
            status_code=200,
            json={
                "data": {
                    "question": {
                        "questionFrontendId": "1",
                        "title": "Two Sum",
                        "titleSlug": "two-sum",
                        "difficulty": "Easy",
                        "topicTags": [{"name": "Array", "slug": "array"}],
                    }
                }
            },
        )

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
    details = await client.get_question_details("two-sum", client=mock_http)
    await mock_http.aclose()

    assert details is not None
    assert details["frontendQuestionId"] == 1
    assert details["title"] == "Two Sum"
    assert details["difficulty"] == "Easy"
    assert details["topicTags"] == ["Array"]

