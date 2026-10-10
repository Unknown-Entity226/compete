"""Database initialization and schema migration runner."""
import logging
from app.db.session import engine
from app.models.base import Base
# Import all models so metadata is populated
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create all tables in the database if they do not exist."""
    async with engine.begin() as conn:
        logger.info("Initializing database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully.")

