"""Historical User Statistics Snapshot SQLAlchemy ORM model."""
from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Statistic(Base):
    """Captures periodic historical snapshots of user progress and velocity."""
    __tablename__ = "statistics"

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
    total_solved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    easy_solved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    medium_solved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    hard_solved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    contest_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    global_ranking: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    solving_velocity_7d: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    solving_velocity_30d: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="statistics")

    def __repr__(self) -> str:
        return f"<Statistic user={self.user_id} solved={self.total_solved} rating={self.contest_rating}>"

