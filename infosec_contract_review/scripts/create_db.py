"""
Run Alembic migrations to bring the database to the current schema.

Usage:
    python -m infosec_contract_review.scripts.create_db
"""
import logging
import sys

from alembic import command
from alembic.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Running Alembic migrations ...")
    cfg = Config("alembic.ini")
    try:
        command.upgrade(cfg, "head")
        logger.info("Database schema is up to date.")
    except Exception:
        logger.exception("Migration failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
