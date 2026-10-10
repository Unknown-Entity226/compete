"""User recent activity and submissions schemas."""
from typing import List
from pydantic import BaseModel, Field


class SubmissionItem(BaseModel):
    """Normalized single submission record."""
    id: str = Field(..., description="LeetCode submission ID")
    title: str = Field(..., description="Problem title")
    titleSlug: str = Field(..., description="Problem slug")
    status: str = Field(..., description="Submission status (e.g. Accepted, Wrong Answer)")
    lang: str = Field(..., description="Programming language used")
    timestamp: int = Field(..., description="Epoch timestamp of submission")


class UserActivityResponse(BaseModel):
    """Response containing recent submissions for a user."""
    username: str
    total: int
    submissions: List[SubmissionItem] = Field(default_factory=list)

