"""Database schema migration runner."""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection

from app.db.session import engine

logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]


async def init_db() -> None:
    """Apply pending Alembic migrations without fabricating a revision stamp."""
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option(
        "script_location", str(BACKEND_DIR / "alembic")
    )

    def upgrade(connection: Connection) -> None:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")

    logger.info("Applying pending database migrations...")
    async with engine.connect() as connection:
        await connection.run_sync(upgrade)
    logger.info("Database migrations applied successfully.")
