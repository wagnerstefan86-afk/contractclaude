"""
Load all YAML seed data into the database.

Usage:
    python -m infosec_contract_review.scripts.seed_db
"""
import logging
import sys

from infosec_contract_review.core.database import SessionLocal
from infosec_contract_review.seed.loader import load_all_seeds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting seed loader ...")
    session = SessionLocal()
    try:
        results = load_all_seeds(session)
        logger.info("Seed loading complete. Summary:")
        for name, count in results.items():
            logger.info("  %-25s %d records", name, count)
    except Exception:
        logger.exception("Seed loading failed.")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
