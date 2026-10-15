"""Services package."""
from app.services.single_flight import SingleFlight
from app.services.cache_service import CacheService
from app.services.leetcode_client import LeetCodeClient
from app.services.cached_leetcode_client import CachedLeetCodeClient
from app.services.stats_service import (
    get_or_create_user,
    record_snapshot,
    get_user_snapshots,
    get_latest_snapshot,
    compute_solving_velocity,
)
from app.services.submission_service import upsert_submissions
from app.services.problem_service import (
    record_user_problems,
    get_user_problems_from_db,
)
from app.services.competition_service import CompetitionService

__all__ = [
    "SingleFlight",
    "CacheService",
    "LeetCodeClient",
    "CachedLeetCodeClient",
    "CompetitionService",
    "get_or_create_user",
    "record_snapshot",
    "get_user_snapshots",
    "get_latest_snapshot",
    "compute_solving_velocity",
    "upsert_submissions",
    "record_user_problems",
    "get_user_problems_from_db",
]
