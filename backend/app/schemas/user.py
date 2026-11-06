"""User profile and statistics Pydantic schemas."""
from typing import List, Optional
from pydantic import BaseModel, Field


class ProblemStats(BaseModel):
    """Problem counts broken down by difficulty."""
    total: int = Field(default=0, description="Total problems solved")
    easy: int = Field(default=0, description="Easy problems solved")
    medium: int = Field(default=0, description="Medium problems solved")
    hard: int = Field(default=0, description="Hard problems solved")


class TopicStat(BaseModel):
    """Tag-specific problem solving counts."""
    topic: str = Field(..., description="Problem category or tag name")
    count: int = Field(default=0, description="Number of problems solved in this category")


class UserProfileResponse(BaseModel):
    """Normalized public user profile response."""
    username: str
    realName: Optional[str] = None
    avatarUrl: Optional[str] = None
    contestRating: Optional[int] = None
    globalRanking: Optional[int] = None
    problemStats: ProblemStats
    strongestArea: Optional[str] = None
    topicStats: List[TopicStat] = Field(default_factory=list)
    lastUpdated: str

