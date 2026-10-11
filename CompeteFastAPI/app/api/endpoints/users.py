"""User statistics and activity REST API endpoints."""
from fastapi import APIRouter, Depends, Query
from app.api.deps import get_leetcode_client
from app.services.leetcode_client import LeetCodeClient
from app.schemas.user import UserProfileResponse
from app.schemas.problem import UserProblemsResponse
from app.schemas.activity import UserActivityResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/{username}",
    response_model=UserProfileResponse,
    summary="Get user profile and statistics",
    description="Returns normalized LeetCode user statistics, difficulty distribution, ranking, and top topic areas.",
)
async def get_user_profile(
    username: str,
    client: LeetCodeClient = Depends(get_leetcode_client),
) -> UserProfileResponse:
    return await client.get_user_profile(username=username)


@router.get(
    "/{username}/problems",
    response_model=UserProblemsResponse,
    summary="Get user's solved problems",
    description="Returns problem status list for the specified LeetCode user.",
)
async def get_user_problems(
    username: str,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of problems to return"),
    client: LeetCodeClient = Depends(get_leetcode_client),
) -> UserProblemsResponse:
    return await client.get_user_problems(username=username, limit=limit)


@router.get(
    "/{username}/activity",
    response_model=UserActivityResponse,
    summary="Get user's recent submission activity",
    description="Returns recent submission history including timestamps, languages, and statuses.",
)
async def get_user_activity(
    username: str,
    limit: int = Query(default=20, ge=1, le=50, description="Maximum number of submissions to return"),
    client: LeetCodeClient = Depends(get_leetcode_client),
) -> UserActivityResponse:
    return await client.get_user_activity(username=username, limit=limit)

