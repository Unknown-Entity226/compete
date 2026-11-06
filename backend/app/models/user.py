"""User SQLAlchemy ORM model."""
from typing import List, Optional
import uuid
from sqlalchemy import String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Stores persistent LeetCode user profile data."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    real_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    contest_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    global_ranking: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    # Relationships
    statistics: Mapped[List["Statistic"]] = relationship(
        "Statistic",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Statistic.snapshot_at)",
    )
    user_problems: Mapped[List["UserProblem"]] = relationship(
        "UserProblem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Submission.submitted_at)",
    )

    def __repr__(self) -> str:
        return f"<User {self.username} (rating={self.contest_rating})>"

