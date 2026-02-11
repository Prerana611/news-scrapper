"""
Entrypoint: run daily job once (for cron/CI) or start in-process scheduler.
"""
import logging
import sys
import os

# Ensure project root is on path when running as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import LOG_LEVEL
from src.scheduler.daily_job import run_daily_job

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the daily scrape + summarize + store job once."""
    logger.info("Starting daily news job")
    try:
        run_daily_job(skip_existing_urls=True, max_articles_per_source=25)
    except Exception as e:
        logger.exception("Daily job failed: %s", e)
        sys.exit(1)
    logger.info("Daily job completed successfully")


if __name__ == "__main__":
    main()
