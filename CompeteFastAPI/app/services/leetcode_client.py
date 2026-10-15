"""LeetCode GraphQL Adapter Service.

Queries LeetCode's public GraphQL endpoint, handles retries, backoff,
error normalization, and transforms raw responses into validated Pydantic models.
"""
import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.exceptions import (
    UserNotFoundError,
    UpstreamRateLimitError,
    UpstreamServiceError,
)
from app.schemas.user import ProblemStats, TopicStat, UserProfileResponse
from app.schemas.problem import ProblemStatusItem, UserProblemsResponse
from app.schemas.activity import SubmissionItem, UserActivityResponse

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

QUESTION_DATA_QUERY = """
query getQuestionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId
    title
    titleSlug
    difficulty
    topicTags {
      name
      slug
    }
  }
}
"""

USER_PROFILE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    githubUrl
    profile {
      realName
      userAvatar
      ranking
    }
    submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
    tagProblemCounts {
      advanced {
        tagName
        problemsSolved
      }
      intermediate {
        tagName
        problemsSolved
      }
      fundamental {
        tagName
        problemsSolved
      }
    }
  }
  userContestRanking(username: $username) {
    rating
    globalRanking
    attendedContestsCount
    topPercentage
  }
}
"""

USER_SUBMISSIONS_QUERY = """
query getRecentSubmissions($username: String!, $limit: Int!) {
  recentSubmissionList(username: $username, limit: $limit) {
    id
    title
    titleSlug
    statusDisplay
    lang
    timestamp
  }
  recentAcSubmissionList(username: $username, limit: $limit) {
    id
    title
    titleSlug
    timestamp
  }
}
"""


class LeetCodeClient:
    """Asynchronous client for interacting with LeetCode's GraphQL API."""

    def __init__(
        self,
        base_url: str = settings.LEETCODE_GRAPHQL_URL,
        timeout: float = settings.LEETCODE_TIMEOUT_SECONDS,
        max_retries: int = settings.LEETCODE_MAX_RETRIES,
        backoff_factor: float = settings.LEETCODE_BACKOFF_FACTOR,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://leetcode.com",
            "Origin": "https://leetcode.com",
        }

    async def _execute_query(
        self,
        query: str,
        variables: Dict[str, Any],
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query with retries and exponential backoff."""
        payload = {"query": query, "variables": variables}
        last_exception: Optional[Exception] = None

        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True

        try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    headers = {**self.headers, "User-Agent": random.choice(USER_AGENTS)}
                    response = await client.post(
                        self.base_url,
                        json=payload,
                        headers=headers,
                    )
                    
                    if response.status_code == 429:
                        logger.warning(
                            "LeetCode upstream rate limit (429) hit on attempt %d/%d",
                            attempt,
                            self.max_retries,
                        )
                        if attempt == self.max_retries:
                            raise UpstreamRateLimitError()
                        sleep_time = self.backoff_factor ** attempt
                        await asyncio.sleep(sleep_time)
                        continue

                    if response.status_code >= 500:
                        logger.warning(
                            "LeetCode upstream server error (%d) on attempt %d/%d",
                            response.status_code,
                            attempt,
                            self.max_retries,
                        )
                        if attempt == self.max_retries:
                            raise UpstreamServiceError(
                                f"LeetCode returned status code {response.status_code}"
                            )
                        sleep_time = self.backoff_factor ** attempt
                        await asyncio.sleep(sleep_time)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # Handle GraphQL top-level errors if any
                    if "errors" in data and not data.get("data"):
                        error_msg = "; ".join(e.get("message", "Unknown error") for e in data["errors"])
                        raise UpstreamServiceError(f"GraphQL Error: {error_msg}")

                    return data.get("data", {})

                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    logger.warning(
                        "Network error querying LeetCode on attempt %d/%d: %s",
                        attempt,
                        self.max_retries,
                        exc,
                    )
                    last_exception = exc
                    if attempt == self.max_retries:
                        raise UpstreamServiceError(f"LeetCode request timed out or connection failed: {exc}")
                    await asyncio.sleep(self.backoff_factor ** attempt)

            raise UpstreamServiceError(f"Failed to query LeetCode: {last_exception}")

        finally:
            if close_client:
                await client.aclose()

    async def get_user_profile(
        self,
        username: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> UserProfileResponse:
        """Fetch and normalize user public profile and problem-solving statistics."""
        data = await self._execute_query(
            USER_PROFILE_QUERY,
            variables={"username": username},
            client=client,
        )

        matched_user = data.get("matchedUser")
        if not matched_user:
            raise UserNotFoundError(username)

        profile = matched_user.get("profile") or {}
        real_name = profile.get("realName")
        avatar_url = profile.get("userAvatar")
        global_ranking = profile.get("ranking")

        # Parse problem solved statistics
        submit_stats = (matched_user.get("submitStatsGlobal") or {}).get("acSubmissionNum") or []
        stats_dict = {"total": 0, "easy": 0, "medium": 0, "hard": 0}
        for item in submit_stats:
            diff = (item.get("difficulty") or "").lower()
            cnt = item.get("count", 0)
            if diff == "all":
                stats_dict["total"] = cnt
            elif diff in stats_dict:
                stats_dict[diff] = cnt

        problem_stats = ProblemStats(**stats_dict)

        # Parse tag problem counts
        tag_counts = matched_user.get("tagProblemCounts") or {}
        topic_map: Dict[str, int] = {}
        for category in ("fundamental", "intermediate", "advanced"):
            for entry in tag_counts.get(category) or []:
                tag_name = entry.get("tagName")
                solved = entry.get("problemsSolved", 0)
                if tag_name and solved > 0:
                    topic_map[tag_name] = topic_map.get(tag_name, 0) + solved

        # Sort topics by count descending
        sorted_topics = sorted(topic_map.items(), key=lambda x: x[1], reverse=True)
        topic_stats = [TopicStat(topic=t, count=c) for t, c in sorted_topics]
        strongest_area = sorted_topics[0][0] if sorted_topics else None

        # Parse contest ranking
        contest_data = data.get("userContestRanking") or {}
        contest_rating: Optional[int] = None
        if contest_data.get("rating"):
            try:
                contest_rating = int(round(float(contest_data["rating"])))
            except (ValueError, TypeError):
                contest_rating = None

        if contest_data.get("globalRanking"):
            global_ranking = contest_data["globalRanking"]

        return UserProfileResponse(
            username=matched_user.get("username", username),
            realName=real_name,
            avatarUrl=avatar_url,
            contestRating=contest_rating,
            globalRanking=global_ranking,
            problemStats=problem_stats,
            strongestArea=strongest_area,
            topicStats=topic_stats,
            lastUpdated=datetime.now(timezone.utc).isoformat(),
        )

    async def get_user_activity(
        self,
        username: str,
        limit: int = 20,
        client: Optional[httpx.AsyncClient] = None,
    ) -> UserActivityResponse:
        """Fetch and normalize user's recent submissions activity."""
        data = await self._execute_query(
            USER_SUBMISSIONS_QUERY,
            variables={"username": username, "limit": limit},
            client=client,
        )

        # Check if user exists: LeetCode returns null lists for nonexistent users
        if data.get("recentSubmissionList") is None and data.get("recentAcSubmissionList") is None:
            raise UserNotFoundError(username)

        submissions_raw = data.get("recentSubmissionList") or []
        submissions: List[SubmissionItem] = []
        for item in submissions_raw:
            try:
                submissions.append(
                    SubmissionItem(
                        id=str(item.get("id")),
                        title=item.get("title", ""),
                        titleSlug=item.get("titleSlug", ""),
                        status=item.get("statusDisplay", "Unknown"),
                        lang=item.get("lang", "unknown"),
                        timestamp=int(item.get("timestamp", 0)),
                    )
                )
            except Exception as e:
                logger.debug("Skipping malformed submission item %s: %s", item, e)

        return UserActivityResponse(
            username=username,
            total=len(submissions),
            submissions=submissions,
        )

    async def get_user_problems(
        self,
        username: str,
        limit: int = 50,
        client: Optional[httpx.AsyncClient] = None,
    ) -> UserProblemsResponse:
        """Fetch accepted problems for a user."""
        data = await self._execute_query(
            USER_SUBMISSIONS_QUERY,
            variables={"username": username, "limit": limit},
            client=client,
        )

        # Check if user exists: LeetCode returns null for nonexistent users
        if data.get("recentAcSubmissionList") is None:
            raise UserNotFoundError(username)

        ac_raw = data.get("recentAcSubmissionList") or []
        problems: List[ProblemStatusItem] = []
        seen_slugs = set()

        for item in ac_raw:
            slug = item.get("titleSlug")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                problems.append(
                    ProblemStatusItem(
                        id=str(item.get("id")),
                        title=item.get("title", ""),
                        titleSlug=slug,
                        status="SOLVED",
                        timestamp=int(item.get("timestamp", 0)) if item.get("timestamp") else None,
                    )
                )

        return UserProblemsResponse(
            username=username,
            total=len(problems),
            problems=problems,
        )

    async def get_question_details(
        self,
        title_slug: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch problem details including frontend question ID, difficulty, and topic tags."""
        try:
            data = await self._execute_query(
                QUESTION_DATA_QUERY,
                variables={"titleSlug": title_slug},
                client=client,
            )
            q = data.get("question")
            if not q:
                return None
            frontend_id_raw = q.get("questionFrontendId")
            frontend_id = int(frontend_id_raw) if frontend_id_raw and str(frontend_id_raw).isdigit() else None
            return {
                "frontendQuestionId": frontend_id,
                "title": q.get("title"),
                "titleSlug": q.get("titleSlug"),
                "difficulty": q.get("difficulty", "Unknown"),
                "topicTags": [t.get("name") for t in (q.get("topicTags") or []) if t.get("name")],
            }
        except Exception as exc:
            logger.debug("Failed to fetch question details for '%s': %s", title_slug, exc)
            return None

