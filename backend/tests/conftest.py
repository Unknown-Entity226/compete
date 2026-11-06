"""Pytest fixtures and mock data for CompeteFastAPI tests."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.leetcode_client import LeetCodeClient
from app.api.deps import get_leetcode_client


MOCK_GRAPHQL_USER_DATA = {
    "matchedUser": {
        "username": "algo_master_99",
        "githubUrl": "https://github.com/algo_master_99",
        "profile": {
            "realName": "Algo Master",
            "userAvatar": "https://assets.leetcode.com/avatar/algo.png",
            "ranking": 14205,
        },
        "submitStatsGlobal": {
            "acSubmissionNum": [
                {"difficulty": "All", "count": 450},
                {"difficulty": "Easy", "count": 150},
                {"difficulty": "Medium", "count": 250},
                {"difficulty": "Hard", "count": 50},
            ]
        },
        "tagProblemCounts": {
            "advanced": [
                {"tagName": "Dynamic Programming", "problemsSolved": 85},
            ],
            "intermediate": [
                {"tagName": "Graphs", "problemsSolved": 62},
            ],
            "fundamental": [
                {"tagName": "Two Pointers", "problemsSolved": 45},
            ],
        },
    },
    "userContestRanking": {
        "rating": 1845.32,
        "globalRanking": 14205,
        "attendedContestsCount": 24,
        "topPercentage": 8.5,
    },
}

MOCK_GRAPHQL_USER_DATA_2 = {
    "matchedUser": {
        "username": "binary_ninja",
        "githubUrl": "https://github.com/binary_ninja",
        "profile": {
            "realName": "Binary Ninja",
            "userAvatar": "https://assets.leetcode.com/avatar/ninja.png",
            "ranking": 21000,
        },
        "submitStatsGlobal": {
            "acSubmissionNum": [
                {"difficulty": "All", "count": 415},
                {"difficulty": "Easy", "count": 190},
                {"difficulty": "Medium", "count": 200},
                {"difficulty": "Hard", "count": 25},
            ]
        },
        "tagProblemCounts": {
            "advanced": [
                {"tagName": "Trees", "problemsSolved": 92},
            ],
            "intermediate": [
                {"tagName": "Hash Table", "problemsSolved": 75},
            ],
            "fundamental": [
                {"tagName": "Binary Search", "problemsSolved": 38},
            ],
        },
    },
    "userContestRanking": {
        "rating": 1720.15,
        "globalRanking": 21000,
        "attendedContestsCount": 18,
        "topPercentage": 14.2,
    },
}

MOCK_GRAPHQL_SUBMISSIONS_DATA = {
    "recentSubmissionList": [
        {
            "id": "1001",
            "title": "Two Sum",
            "titleSlug": "two-sum",
            "statusDisplay": "Accepted",
            "lang": "python3",
            "timestamp": 1729000000,
        },
        {
            "id": "1002",
            "title": "Add Two Numbers",
            "titleSlug": "add-two-numbers",
            "statusDisplay": "Wrong Answer",
            "lang": "python3",
            "timestamp": 1728990000,
        },
    ],
    "recentAcSubmissionList": [
        {
            "id": "1001",
            "title": "Two Sum",
            "titleSlug": "two-sum",
            "timestamp": 1729000000,
        },
    ],
}


class MockLeetCodeClient(LeetCodeClient):
    """Mock LeetCode client returning deterministic test data."""

    async def _execute_query(self, query: str, variables: dict, client=None):
        username = variables.get("username")
        if username == "algo_master_99":
            if "recentSubmissionList" in query:
                return MOCK_GRAPHQL_SUBMISSIONS_DATA
            return MOCK_GRAPHQL_USER_DATA
        elif username == "binary_ninja":
            if "recentSubmissionList" in query:
                return MOCK_GRAPHQL_SUBMISSIONS_DATA
            return MOCK_GRAPHQL_USER_DATA_2
        elif username == "nonexistent_user":
            return {"matchedUser": None}
        return {"matchedUser": None}


@pytest.fixture
def mock_leetcode_client():
    return MockLeetCodeClient()


@pytest_asyncio.fixture
async def async_client(mock_leetcode_client):
    """Test client overriding the leetcode client dependency."""
    app.dependency_overrides[get_leetcode_client] = lambda: mock_leetcode_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
