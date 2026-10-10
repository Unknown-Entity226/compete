"""Head-to-head comparison schemas."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.user import ProblemStats, TopicStat


class CompetitorStats(BaseModel):
    """Normalized profile stats for one competitor."""
    leetcodeId: str
    realName: Optional[str] = None
    avatarUrl: Optional[str] = None
    contestRating: Optional[int] = None
    globalRanking: Optional[int] = None
    problemStats: ProblemStats
    strongestArea: Optional[str] = None
    topicStats: List[TopicStat] = Field(default_factory=list)
    score: float = Field(default=0.0, description="Calculated competition score")


class CompetitionMetrics(BaseModel):
    """Comparative differential metrics between competitors."""
    ratingDiff: Optional[int] = None
    totalSolvedDiff: int = 0
    easyDiff: int = 0
    mediumDiff: int = 0
    hardDiff: int = 0
    higherRankedUser: Optional[str] = None


class CompareResponse(BaseModel):
    """Full head-to-head duel comparison response."""
    comparisonId: str
    lastUpdated: str
    winner: Optional[str] = None
    score: Dict[str, float] = Field(default_factory=dict)
    metrics: CompetitionMetrics
    competitionData: Dict[str, Any] = Field(
        ...,
        description="Nested object compatible directly with CompeteFrontend state expectations"
    )

