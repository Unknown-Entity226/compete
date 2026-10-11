"""Head-to-head comparison endpoint."""
import asyncio
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Depends

from app.api.deps import get_leetcode_client
from app.services.leetcode_client import LeetCodeClient
from app.schemas.compare import (
    CompareResponse,
    CompetitionMetrics,
)
from app.schemas.user import UserProfileResponse

router = APIRouter(prefix="/compare", tags=["Compare"])


def calculate_user_score(profile: UserProfileResponse) -> float:
    """Calculate weighted competitive score for a profile."""
    # Rating weight (defaults to baseline 1500 if unrated)
    rating_baseline = float(profile.contestRating) if profile.contestRating else 1500.0
    rating_component = rating_baseline * 0.4
    
    # Problem solving difficulty weights: Easy: 1.0, Medium: 3.0, Hard: 6.0
    p = profile.problemStats
    problem_component = (p.easy * 1.0) + (p.medium * 3.0) + (p.hard * 6.0)
    
    return round(rating_component + problem_component, 2)


@router.get(
    "/{first_user}/{second_user}",
    response_model=CompareResponse,
    summary="Compare two LeetCode users head-to-head",
    description="Fetches both profiles concurrently, computes duel metrics and winner score.",
)
async def compare_users(
    first_user: str,
    second_user: str,
    client: LeetCodeClient = Depends(get_leetcode_client),
) -> CompareResponse:
    # Query both profiles concurrently
    first_profile, second_profile = await asyncio.gather(
        client.get_user_profile(first_user),
        client.get_user_profile(second_user),
    )

    first_score = calculate_user_score(first_profile)
    second_score = calculate_user_score(second_profile)

    winner = None
    if first_score > second_score:
        winner = first_profile.username
    elif second_score > first_score:
        winner = second_profile.username
    else:
        winner = "TIE"

    # Higher ranked user (smaller ranking number is better)
    higher_ranked = None
    if first_profile.globalRanking and second_profile.globalRanking:
        higher_ranked = first_profile.username if first_profile.globalRanking < second_profile.globalRanking else second_profile.username
    elif first_profile.globalRanking:
        higher_ranked = first_profile.username
    elif second_profile.globalRanking:
        higher_ranked = second_profile.username

    rating_diff = None
    if first_profile.contestRating is not None and second_profile.contestRating is not None:
        rating_diff = first_profile.contestRating - second_profile.contestRating

    metrics = CompetitionMetrics(
        ratingDiff=rating_diff,
        totalSolvedDiff=first_profile.problemStats.total - second_profile.problemStats.total,
        easyDiff=first_profile.problemStats.easy - second_profile.problemStats.easy,
        mediumDiff=first_profile.problemStats.medium - second_profile.problemStats.medium,
        hardDiff=first_profile.problemStats.hard - second_profile.problemStats.hard,
        higherRankedUser=higher_ranked,
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    # Frontend-compatible competitionData payload
    competition_data = {
        "lastUpdated": now_iso,
        "users": [
            {
                "leetcodeId": first_profile.username,
                "contestRating": first_profile.contestRating,
                "problemStats": first_profile.problemStats.model_dump(),
                "strongestArea": first_profile.strongestArea,
                "topicStats": [t.model_dump() for t in first_profile.topicStats[:5]],
            },
            {
                "leetcodeId": second_profile.username,
                "contestRating": second_profile.contestRating,
                "problemStats": second_profile.problemStats.model_dump(),
                "strongestArea": second_profile.strongestArea,
                "topicStats": [t.model_dump() for t in second_profile.topicStats[:5]],
            },
        ],
    }

    return CompareResponse(
        comparisonId=f"{first_profile.username}-vs-{second_profile.username}",
        lastUpdated=now_iso,
        winner=winner,
        score={
            first_profile.username: first_score,
            second_profile.username: second_score,
        },
        metrics=metrics,
        competitionData=competition_data,
    )

