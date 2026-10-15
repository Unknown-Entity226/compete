"""Head-to-head comparison schemas."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.user import ProblemStats, TopicStat


class ScoreBreakdown(BaseModel):
    """Detailed multi-factor competitive score breakdown."""
    ratingScore: float = Field(..., description="Points earned from contest rating")
    difficultyScore: float = Field(..., description="Points earned from difficulty-weighted solved problems")
    velocityScore: float = Field(..., description="Points earned from recent solving velocity")
    streakScore: float = Field(..., description="Points earned from daily consistency and weekly volume")
    totalScore: float = Field(..., description="Total combined competition score")


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
    streakDays: int = Field(default=0, description="Current consecutive active days")
    weeklySolved: int = Field(default=0, description="Problems solved in last 7 days")
    monthlySolved: int = Field(default=0, description="Problems solved in last 30 days")
    score: float = Field(default=0.0, description="Calculated competition score")
    scoreBreakdown: Optional[ScoreBreakdown] = None


class CompetitionMetrics(BaseModel):
    """Comparative differential metrics between competitors."""
    ratingDiff: Optional[int] = None
    totalSolvedDiff: int = 0
    easyDiff: int = 0
    mediumDiff: int = 0
    hardDiff: int = 0
    velocity7dDiff: float = 0.0
    weeklySolvedDiff: int = 0
    streakDiff: int = 0
    higherRankedUser: Optional[str] = None


class CompareResponse(BaseModel):
    """Full head-to-head duel comparison response."""
    comparisonId: str
    lastUpdated: str
    winner: Optional[str] = None
    score: Dict[str, float] = Field(default_factory=dict)
    scoreBreakdown: Dict[str, ScoreBreakdown] = Field(default_factory=dict)
    metrics: CompetitionMetrics
    competitionData: Dict[str, Any] = Field(
        ...,
        description="Nested object compatible directly with CompeteFrontend state expectations"
    )
