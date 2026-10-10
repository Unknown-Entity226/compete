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
    "/{user1}/{user2}",
    response_model=CompareResponse,
    summary="Compare two LeetCode users head-to-head",
    description="Fetches both profiles concurrently, computes duel metrics and winner score.",
)
async def compare_users(
    user1: str,
    user2: str,
    client: LeetCodeClient = Depends(get_leetcode_client),
) -> CompareResponse:
    # Query both profiles concurrently
    profile1, profile2 = await asyncio.gather(
        client.get_user_profile(user1),
        client.get_user_profile(user2),
    )

    score1 = calculate_user_score(profile1)
    score2 = calculate_user_score(profile2)

    winner = None
    if score1 > score2:
        winner = profile1.username
    elif score2 > score1:
        winner = profile2.username
    else:
        winner = "TIE"

    # Higher ranked user (smaller ranking number is better)
    higher_ranked = None
    if profile1.globalRanking and profile2.globalRanking:
        higher_ranked = profile1.username if profile1.globalRanking < profile2.globalRanking else profile2.username
    elif profile1.globalRanking:
        higher_ranked = profile1.username
    elif profile2.globalRanking:
        higher_ranked = profile2.username

    rating_diff = None
    if profile1.contestRating is not None and profile2.contestRating is not None:
        rating_diff = profile1.contestRating - profile2.contestRating

    metrics = CompetitionMetrics(
        ratingDiff=rating_diff,
        totalSolvedDiff=profile1.problemStats.total - profile2.problemStats.total,
        easyDiff=profile1.problemStats.easy - profile2.problemStats.easy,
        mediumDiff=profile1.problemStats.medium - profile2.problemStats.medium,
        hardDiff=profile1.problemStats.hard - profile2.problemStats.hard,
        higherRankedUser=higher_ranked,
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    # Frontend-compatible competitionData payload
    competition_data = {
        "lastUpdated": now_iso,
        "users": [
            {
                "leetcodeId": profile1.username,
                "contestRating": profile1.contestRating,
                "problemStats": profile1.problemStats.model_dump(),
                "strongestArea": profile1.strongestArea,
                "topicStats": [t.model_dump() for t in profile1.topicStats[:5]],
            },
            {
                "leetcodeId": profile2.username,
                "contestRating": profile2.contestRating,
                "problemStats": profile2.problemStats.model_dump(),
                "strongestArea": profile2.strongestArea,
                "topicStats": [t.model_dump() for t in profile2.topicStats[:5]],
            },
        ],
    }

    return CompareResponse(
        comparisonId=f"{profile1.username}-vs-{profile2.username}",
        lastUpdated=now_iso,
        winner=winner,
        score={
            profile1.username: score1,
            profile2.username: score2,
        },
        metrics=metrics,
        competitionData=competition_data,
    )

