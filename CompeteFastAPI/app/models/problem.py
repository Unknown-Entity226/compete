"""Problem SQLAlchemy ORM model."""
from typing import List, Optional, Any
import uuid
from sqlalchemy import String, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Problem(Base, TimestampMixin):
    """Stores LeetCode problem catalog entries."""
    __tablename__ = "problems"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    frontend_question_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    title_slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    difficulty: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    topic_tags: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    user_problems: Mapped[List["UserProblem"]] = relationship(
        "UserProblem",
        back_populates="problem",
        cascade="all, delete-orphan",
    )
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="problem",
    )

    def __repr__(self) -> str:
        return f"<Problem #{self.frontend_question_id}: {self.title} ({self.difficulty})>"

