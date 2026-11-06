"""Problem and user-problem status Pydantic schemas."""
from typing import List, Optional
from pydantic import BaseModel, Field


class ProblemStatusItem(BaseModel):
    """Problem item with user solve status."""
    id: Optional[str] = None
    title: str
    titleSlug: str
    difficulty: Optional[str] = None
    status: str = Field(default="SOLVED", description="Solve status: SOLVED, ATTEMPTED, NOT_ATTEMPTED")
    timestamp: Optional[int] = Field(default=None, description="Unix timestamp of resolution")


class UserProblemsResponse(BaseModel):
    """List of problems with status for a specific user."""
    username: str
    total: int
    problems: List[ProblemStatusItem] = Field(default_factory=list)

