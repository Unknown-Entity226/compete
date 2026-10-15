"""Independent competition scoring engine and head-to-head duel analyzer.

Evaluates developers across contest rating, problem-solving difficulty,
solving velocity, and active daily streaks. Decoupled from upstream fetching.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statistic import Statistic
from app.schemas.activity import SubmissionItem, UserActivityResponse
from app.schemas.compare import (
    CompareResponse,
    CompetitionMetrics,
    ScoreBreakdown,
)
from app.schemas.user import UserProfileResponse
from app.services.leetcode_client import LeetCodeClient
from app.services.stats_service import get_latest_snapshot

logger = logging.getLogger(__name__)

# Scoring weights and constants
RATING_FLOOR = 1200.0
RATING_DEFAULT_BASELINE = 1500.0
RATING_WEIGHT = 0.5

EASY_WEIGHT = 1.0
MEDIUM_WEIGHT = 3.0
HARD_WEIGHT = 6.0

VELOCITY_7D_WEIGHT = 10.0
VELOCITY_30D_WEIGHT = 5.0

STREAK_DAY_WEIGHT = 8.0
WEEKLY_SOLVE_WEIGHT = 4.0
MAX_STREAK_POINTS = 100.0


class CompetitionService:
    """Independent service calculating multi-factor competition metrics and scores."""

    def __init__(self, leetcode_client: Optional[LeetCodeClient] = None):
        self.leetcode_client = leetcode_client

    @staticmethod
    def calculate_streak(
        submissions: List[SubmissionItem],
        reference_time: Optional[datetime] = None,
    ) -> int:
        """Calculate consecutive daily solving streak from submission timestamps.

        Considers submissions grouped by UTC calendar date. If the user was active
        today or yesterday, counts consecutive preceding days.
        """
        if not submissions:
            return 0

        now = reference_time or datetime.now(timezone.utc)
        today = now.date()
        yesterday = today - timedelta(days=1)

        # Collect distinct submission dates
        active_dates = set()
        for s in submissions:
            if s.timestamp and (s.status or "").lower() in ("accepted", "solved"):
                sub_date = datetime.fromtimestamp(s.timestamp, tz=timezone.utc).date()
                active_dates.add(sub_date)

        if not active_dates:
            return 0

        # Streak must include today or yesterday to still be alive
        if today in active_dates:
            current_check = today
        elif yesterday in active_dates:
            current_check = yesterday
        else:
            return 0

        streak = 0
        while current_check in active_dates:
            streak += 1
            current_check -= timedelta(days=1)

        return streak

    @staticmethod
    def calculate_window_solves(
        submissions: List[SubmissionItem],
        window_days: int = 7,
        reference_time: Optional[datetime] = None,
    ) -> int:
        """Count distinct accepted problems solved within the last N days."""
        if not submissions:
            return 0

        now = reference_time or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=window_days)
        accepted_slugs = set()

        for s in submissions:
            if not s.timestamp:
                continue
            sub_dt = datetime.fromtimestamp(s.timestamp, tz=timezone.utc)
            if sub_dt >= cutoff and s.status.lower() in ("accepted", "solved"):
                accepted_slugs.add(s.titleSlug)

        return len(accepted_slugs)

    def compute_user_score(
        self,
        profile: UserProfileResponse,
        velocity_7d: float = 0.0,
        velocity_30d: float = 0.0,
        streak_days: int = 0,
        weekly_solved: int = 0,
    ) -> ScoreBreakdown:
        """Calculate multi-factor score breakdown for a single user."""
        # 1. Rating component
        if profile.contestRating and profile.contestRating > 0:
            effective_rating = float(profile.contestRating)
        else:
            effective_rating = RATING_DEFAULT_BASELINE

        rating_points = max(0.0, (effective_rating - RATING_FLOOR) * RATING_WEIGHT)

        # 2. Difficulty-weighted solves component
        p = profile.problemStats
        difficulty_points = (
            (p.easy * EASY_WEIGHT)
            + (p.medium * MEDIUM_WEIGHT)
            + (p.hard * HARD_WEIGHT)
        )

        # 3. Solving velocity component
        velocity_points = (velocity_7d * VELOCITY_7D_WEIGHT) + (velocity_30d * VELOCITY_30D_WEIGHT)

        # 4. Consistency & Streak component
        raw_streak_points = (streak_days * STREAK_DAY_WEIGHT) + (weekly_solved * WEEKLY_SOLVE_WEIGHT)
        streak_points = min(MAX_STREAK_POINTS, raw_streak_points)

        total_score = round(
            rating_points + difficulty_points + velocity_points + streak_points,
            2,
        )

        return ScoreBreakdown(
            ratingScore=round(rating_points, 2),
            difficultyScore=round(difficulty_points, 2),
            velocityScore=round(velocity_points, 2),
            streakScore=round(streak_points, 2),
            totalScore=total_score,
        )

    async def compare_profiles(
        self,
        first_profile: UserProfileResponse,
        second_profile: UserProfileResponse,
        first_activity: Optional[UserActivityResponse] = None,
        second_activity: Optional[UserActivityResponse] = None,
        first_snapshot: Optional[Statistic] = None,
        second_snapshot: Optional[Statistic] = None,
    ) -> CompareResponse:
        """Perform head-to-head comparison between two fully loaded profiles."""
        # Extract or compute velocities
        first_v7d = first_snapshot.solving_velocity_7d if first_snapshot else 0.0
        first_v30d = first_snapshot.solving_velocity_30d if first_snapshot else 0.0
        second_v7d = second_snapshot.solving_velocity_7d if second_snapshot else 0.0
        second_v30d = second_snapshot.solving_velocity_30d if second_snapshot else 0.0

        # Calculate streaks and weekly solves from activity if available
        first_submissions = first_activity.submissions if first_activity else []
        second_submissions = second_activity.submissions if second_activity else []

        first_streak = self.calculate_streak(first_submissions)
        second_streak = self.calculate_streak(second_submissions)

        first_weekly = self.calculate_window_solves(first_submissions, window_days=7)
        second_weekly = self.calculate_window_solves(second_submissions, window_days=7)

        # If DB velocity was 0 but activity exists, derive 7d velocity from activity
        if first_v7d == 0.0 and first_weekly > 0:
            first_v7d = round(first_weekly / 7.0, 2)
        if second_v7d == 0.0 and second_weekly > 0:
            second_v7d = round(second_weekly / 7.0, 2)

        # Compute scores
        first_breakdown = self.compute_user_score(
            profile=first_profile,
            velocity_7d=first_v7d,
            velocity_30d=first_v30d,
            streak_days=first_streak,
            weekly_solved=first_weekly,
        )
        second_breakdown = self.compute_user_score(
            profile=second_profile,
            velocity_7d=second_v7d,
            velocity_30d=second_v30d,
            streak_days=second_streak,
            weekly_solved=second_weekly,
        )

        first_score = first_breakdown.totalScore
        second_score = second_breakdown.totalScore

        # Winner resolution
        if first_score > second_score:
            winner = first_profile.username
        elif second_score > first_score:
            winner = second_profile.username
        else:
            winner = "TIE"

        # Higher ranked user resolution (lower integer is better)
        higher_ranked = None
        if first_profile.globalRanking and second_profile.globalRanking:
            if first_profile.globalRanking < second_profile.globalRanking:
                higher_ranked = first_profile.username
            elif second_profile.globalRanking < first_profile.globalRanking:
                higher_ranked = second_profile.username
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
            velocity7dDiff=round(first_v7d - second_v7d, 2),
            weeklySolvedDiff=first_weekly - second_weekly,
            streakDiff=first_streak - second_streak,
            higherRankedUser=higher_ranked,
        )

        now_iso = datetime.now(timezone.utc).isoformat()

        # Frontend-compatible competitionData payload
        competition_data: Dict[str, Any] = {
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
            scoreBreakdown={
                first_profile.username: first_breakdown,
                second_profile.username: second_breakdown,
            },
            metrics=metrics,
            competitionData=competition_data,
        )
