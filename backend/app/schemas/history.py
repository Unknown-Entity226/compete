"""Schemas for historical statistics snapshots and solving velocity."""
from typing import List, Optional
from pydantic import BaseModel, Field


class SnapshotEntry(BaseModel):
    """Single point-in-time statistics snapshot for a user."""
    snapshotAt: str = Field(..., description="ISO 8601 timestamp of when snapshot was taken")
    totalSolved: int
    easySolved: int
    mediumSolved: int
    hardSolved: int
    contestRating: Optional[int] = None
    globalRanking: Optional[int] = None
    solvingVelocity7d: float = Field(0.0, description="Average problems solved per day over last 7 days")
    solvingVelocity30d: float = Field(0.0, description="Average problems solved per day over last 30 days")


class UserHistoryResponse(BaseModel):
    """Historical snapshots for a single user."""
    username: str
    snapshotCount: int
    snapshots: List[SnapshotEntry]

