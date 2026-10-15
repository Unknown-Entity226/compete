"""Tests for Phase 4: Competition & Scoring Engine."""
from datetime import datetime, timedelta, timezone
import pytest

from app.models.statistic import Statistic
from app.schemas.activity import SubmissionItem, UserActivityResponse
from app.schemas.user import UserProfileResponse, ProblemStats, TopicStat
from app.services.competition_service import (
    CompetitionService,
    RATING_FLOOR,
    RATING_WEIGHT,
    EASY_WEIGHT,
    MEDIUM_WEIGHT,
    HARD_WEIGHT,
    VELOCITY_7D_WEIGHT,
    VELOCITY_30D_WEIGHT,
    STREAK_DAY_WEIGHT,
    WEEKLY_SOLVE_WEIGHT,
)


def _make_profile(
    username: str,
    rating: int = 1800,
    total: int = 300,
    easy: int = 100,
    medium: int = 150,
    hard: int = 50,
    ranking: int = 15000,
) -> UserProfileResponse:
    return UserProfileResponse(
        username=username,
        realName=f"User {username}",
        avatarUrl=None,
        contestRating=rating,
        globalRanking=ranking,
        problemStats=ProblemStats(total=total, easy=easy, medium=medium, hard=hard),
        strongestArea="Dynamic Programming",
        topicStats=[TopicStat(topic="Dynamic Programming", count=45)],
        lastUpdated=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Streak calculation tests
# ---------------------------------------------------------------------------

def test_calculate_streak_empty():
    assert CompetitionService.calculate_streak([]) == 0


def test_calculate_streak_active_today():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Submissions today, yesterday, and 2 days ago
    submissions = [
        SubmissionItem(id="1", title="A", titleSlug="a", status="Accepted", lang="python3", timestamp=int(now.timestamp())),
        SubmissionItem(id="2", title="B", titleSlug="b", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=1)).timestamp())),
        SubmissionItem(id="3", title="C", titleSlug="c", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=2)).timestamp())),
    ]
    streak = CompetitionService.calculate_streak(submissions, reference_time=now)
    assert streak == 3


def test_calculate_streak_broken_gap():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Active today, missed yesterday, active 2 days ago
    submissions = [
        SubmissionItem(id="1", title="A", titleSlug="a", status="Accepted", lang="python3", timestamp=int(now.timestamp())),
        SubmissionItem(id="3", title="C", titleSlug="c", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=2)).timestamp())),
    ]
    streak = CompetitionService.calculate_streak(submissions, reference_time=now)
    assert streak == 1


def test_calculate_streak_inactive():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Last submission 4 days ago
    submissions = [
        SubmissionItem(id="1", title="A", titleSlug="a", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=4)).timestamp())),
    ]
    streak = CompetitionService.calculate_streak(submissions, reference_time=now)
    assert streak == 0


# ---------------------------------------------------------------------------
# Window solves calculation
# ---------------------------------------------------------------------------

def test_calculate_window_solves():
    now = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    submissions = [
        # In window, accepted
        SubmissionItem(id="1", title="Two Sum", titleSlug="two-sum", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=1)).timestamp())),
        # In window, wrong answer (not counted)
        SubmissionItem(id="2", title="Add Two", titleSlug="add-two", status="Wrong Answer", lang="python3", timestamp=int((now - timedelta(days=2)).timestamp())),
        # In window, accepted duplicate problem (unique slug counted once)
        SubmissionItem(id="3", title="Two Sum", titleSlug="two-sum", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=3)).timestamp())),
        # Out of window (10 days ago), accepted
        SubmissionItem(id="4", title="Old Problem", titleSlug="old-problem", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=10)).timestamp())),
    ]
    count = CompetitionService.calculate_window_solves(submissions, window_days=7, reference_time=now)
    assert count == 1  # Only "two-sum" is accepted within last 7 days


# ---------------------------------------------------------------------------
# Scoring formula tests
# ---------------------------------------------------------------------------

def test_compute_user_score_rated():
    service = CompetitionService()
    profile = _make_profile(username="coder_a", rating=1800, total=300, easy=100, medium=150, hard=50)

    breakdown = service.compute_user_score(
        profile=profile,
        velocity_7d=2.0,
        velocity_30d=1.5,
        streak_days=5,
        weekly_solved=7,
    )

    expected_rating = (1800 - RATING_FLOOR) * RATING_WEIGHT  # (1800 - 1200) * 0.5 = 300.0
    expected_difficulty = (100 * EASY_WEIGHT) + (150 * MEDIUM_WEIGHT) + (50 * HARD_WEIGHT)  # 100 + 450 + 300 = 850.0
    expected_velocity = (2.0 * VELOCITY_7D_WEIGHT) + (1.5 * VELOCITY_30D_WEIGHT)  # 20 + 7.5 = 27.5
    expected_streak = (5 * STREAK_DAY_WEIGHT) + (7 * WEEKLY_SOLVE_WEIGHT)  # 40 + 28 = 68.0
    expected_total = expected_rating + expected_difficulty + expected_velocity + expected_streak  # 300 + 850 + 27.5 + 68 = 1245.5

    assert breakdown.ratingScore == expected_rating
    assert breakdown.difficultyScore == expected_difficulty
    assert breakdown.velocityScore == expected_velocity
    assert breakdown.streakScore == expected_streak
    assert breakdown.totalScore == expected_total


def test_compute_user_score_unrated():
    service = CompetitionService()
    profile = _make_profile(username="unrated_coder", rating=0, total=100, easy=50, medium=40, hard=10)

    breakdown = service.compute_user_score(profile=profile)
    # Unrated user receives 0.0 rating points so active contestants are not penalized
    assert breakdown.ratingScore == 0.0
    assert breakdown.difficultyScore == (50 * 1.0) + (40 * 3.0) + (10 * 6.0)
    assert breakdown.totalScore == breakdown.difficultyScore


# ---------------------------------------------------------------------------
# Head-to-head comparison tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compare_profiles_first_user_wins():
    service = CompetitionService()
    first_profile = _make_profile(username="senior_coder", rating=2000, total=500, easy=100, medium=300, hard=100, ranking=1000)
    second_profile = _make_profile(username="junior_coder", rating=1500, total=100, easy=60, medium=35, hard=5, ranking=50000)

    result = await service.compare_profiles(
        first_profile=first_profile,
        second_profile=second_profile,
    )

    assert result.winner == "senior_coder"
    assert result.score["senior_coder"] > result.score["junior_coder"]
    assert result.metrics.higherRankedUser == "senior_coder"
    assert result.metrics.totalSolvedDiff == 400


@pytest.mark.asyncio
async def test_compare_profiles_tie():
    service = CompetitionService()
    first_profile = _make_profile(username="twin_a", rating=1700, total=200, easy=50, medium=100, hard=50, ranking=20000)
    second_profile = _make_profile(username="twin_b", rating=1700, total=200, easy=50, medium=100, hard=50, ranking=20000)

    result = await service.compare_profiles(
        first_profile=first_profile,
        second_profile=second_profile,
    )

    assert result.winner == "TIE"
    assert result.score["twin_a"] == result.score["twin_b"]


@pytest.mark.asyncio
async def test_compare_profiles_with_db_snapshots_and_activity():
    service = CompetitionService()
    first_profile = _make_profile(username="active_coder", rating=1800, total=300)
    second_profile = _make_profile(username="idle_coder", rating=1800, total=300)

    # Active coder has historical velocity snapshot
    first_snap = Statistic(
        total_solved=300,
        easy_solved=100,
        medium_solved=150,
        hard_solved=50,
        solving_velocity_7d=3.0,
        solving_velocity_30d=2.0,
    )

    # Active coder has recent submissions today and yesterday
    now = datetime.now(timezone.utc)
    first_activity = UserActivityResponse(
        username="active_coder",
        total=2,
        submissions=[
            SubmissionItem(id="1", title="A", titleSlug="a", status="Accepted", lang="python3", timestamp=int(now.timestamp())),
            SubmissionItem(id="2", title="B", titleSlug="b", status="Accepted", lang="python3", timestamp=int((now - timedelta(days=1)).timestamp())),
        ],
    )

    result = await service.compare_profiles(
        first_profile=first_profile,
        second_profile=second_profile,
        first_activity=first_activity,
        first_snapshot=first_snap,
    )

    # Both have same base stats and rating, but active_coder wins due to velocity & streak
    assert result.winner == "active_coder"
    assert result.metrics.velocity7dDiff == 3.0
    assert result.metrics.streakDiff == 2
    assert "scoreBreakdown" in result.model_dump()
    assert result.scoreBreakdown["active_coder"].velocityScore > 0
    assert result.scoreBreakdown["active_coder"].streakScore > 0
