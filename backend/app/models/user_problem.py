"""User-Problem association SQLAlchemy ORM model."""
from typing import Optional
from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserProblem(Base, TimestampMixin):
    """Tracks a user's progress and solve status for a specific problem."""
    __tablename__ = "user_problems"
    __table_args__ = (
        UniqueConstraint("user_id", "problem_id", name="uq_user_problem"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="SOLVED",
        nullable=False,
        index=True,
    )
    solved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_attempted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="user_problems")
    problem: Mapped["Problem"] = relationship("Problem", back_populates="user_problems")

    def __repr__(self) -> str:
        return f"<UserProblem user={self.user_id} problem={self.problem_id} status={self.status}>"

