"""Submission history SQLAlchemy ORM model."""
from typing import Optional
from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Submission(Base):
    """Tracks individual problem-solving submission events."""
    __tablename__ = "submissions"

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
    problem_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submission_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    problem_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    problem_slug: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    status_display: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    lang: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="submissions")
    problem: Mapped[Optional["Problem"]] = relationship("Problem", back_populates="submissions")

    def __repr__(self) -> str:
        return f"<Submission #{self.submission_id}: {self.problem_title} ({self.status_display})>"

