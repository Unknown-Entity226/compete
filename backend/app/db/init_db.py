"""Database initialization and schema migration runner."""
import logging
from sqlalchemy import text
from app.db.session import engine
from app.models.base import Base
# Import all models so metadata is populated
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create all tables in the database if they do not exist and stamp Alembic head."""
    async with engine.begin() as conn:
        logger.info("Initializing database tables...")
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alembic_version "
                    "(version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
                )
            )
            res = await conn.execute(text("SELECT version_num FROM alembic_version"))
            if res.scalar_one_or_none() is None:
                await conn.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES ('0001_initial_schema')")
                )
                logger.info("Stamped alembic_version with 0001_initial_schema")
        except Exception as exc:
            logger.debug("Alembic version stamping skipped: %s", exc)
        logger.info("Database tables initialized successfully.")

