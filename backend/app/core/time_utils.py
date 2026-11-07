"""Timezone helpers shared by persistence and scoring code."""
from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """Treat naive database timestamps as UTC and normalize aware values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
