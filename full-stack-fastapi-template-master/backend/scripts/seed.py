import logging
from sqlmodel import Session

from app.core.db import engine, init_db
from app.seed.catalog import seed_catalog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Initializing database...")
    with Session(engine) as session:
        init_db(session)
        logger.info("Seeding Brightloop catalog...")
        counts = seed_catalog(session)
        logger.info(f"Seeding completed successfully: {counts}")


if __name__ == "__main__":
    main()

