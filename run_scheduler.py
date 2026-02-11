"""
In-process scheduler: runs the daily job every day at 9:00 AM (configurable).
For production, prefer system cron or GitHub Actions and use main.py as the command.
"""
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import LOG_LEVEL, DAILY_RUN_HOUR, DAILY_RUN_MINUTE
from src.scheduler.daily_job import run_daily_job

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    import schedule
    import time

    def job() -> None:
        try:
            run_daily_job(skip_existing_urls=True, max_articles_per_run=100)
        except Exception as e:
            logger.exception("Scheduled job failed: %s", e)

    schedule.every().day.at(f"{DAILY_RUN_HOUR:02d}:{DAILY_RUN_MINUTE:02d}").do(job)
    logger.info("Scheduler started; daily run at %02d:%02d", DAILY_RUN_HOUR, DAILY_RUN_MINUTE)
    # Run once on start (optional)
    job()
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
