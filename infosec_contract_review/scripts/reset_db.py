"""
Reset database: drop all tables and re-run migrations + seeds.

WARNING: Destroys all data. For local development only.

Usage:
    python -m infosec_contract_review.scripts.reset_db
"""
import logging
import sys

from alembic import command
from alembic.config import Config

from infosec_contract_review.core.database import SessionLocal, engine
from infosec_contract_review.models.base import Base
from infosec_contract_review.seed.loader import load_all_seeds

# Ensure all models are imported
import infosec_contract_review.models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.warning("Dropping ALL tables ...")
    Base.metadata.drop_all(bind=engine)

    logger.info("Running Alembic migrations ...")
    cfg = Config("alembic.ini")
    try:
        # Stamp as base first so Alembic knows the DB is clean
        command.stamp(cfg, "base")
        command.upgrade(cfg, "head")
    except Exception:
        logger.exception("Migration failed.")
        sys.exit(1)

    logger.info("Loading seeds ...")
    session = SessionLocal()
    try:
        results = load_all_seeds(session)
        logger.info("Reset complete. Seed summary:")
        for name, count in results.items():
            logger.info("  %-25s %d records", name, count)
    except Exception:
        logger.exception("Seed loading failed.")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
