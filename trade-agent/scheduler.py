from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from src.config import get_settings
from src.data_ingestion import SQLiteDataLoader
from src.pipeline import TradePipeline


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("trade-agent-scheduler")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Schedule trade-agent runs after fetch-data-agent completes."
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=int(getattr(get_settings(), "trade_interval_minutes", 40)),
        help="Minutes between trade-agent runs (default: 30).",
    )
    parser.add_argument(
        "--initial-delay-minutes",
        type=int,
        default=5,
        help="Delay the first run to give fetch-data-agent time to finish (default: 5).",
    )
    return parser.parse_args()


def latest_snapshot_age_minutes(loader: SQLiteDataLoader) -> Optional[float]:
    timestamp = loader.latest_snapshot_timestamp()
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Could not parse last_fetched_at timestamp '%s'", timestamp)
        return None
    delta = datetime.now(timezone.utc) - parsed
    return delta.total_seconds() / 60


def run_scheduler(interval_minutes: int, initial_delay_minutes: int) -> None:
    settings = get_settings()
    loader = SQLiteDataLoader(settings.sqlite_path)
    pipeline = TradePipeline(settings)
    freshness_limit = settings.snapshot_freshness_minutes

    if initial_delay_minutes > 0:
        logger.info("Waiting %d minute(s) before first run.", initial_delay_minutes)
        time.sleep(initial_delay_minutes * 60)

    logger.info(
        "Scheduler started (interval=%d min, freshness window=%d min).",
        interval_minutes,
        freshness_limit,
    )

    while True:
        start = time.time()
        age_minutes = latest_snapshot_age_minutes(loader)
        if age_minutes is None:
            logger.warning("No snapshot metadata available yet; skipping this run.")
        elif age_minutes > freshness_limit:
            logger.warning(
                "Snapshots are stale (age=%.1f min > %d); skipping trade run.",
                age_minutes,
                freshness_limit,
            )
        else:
            logger.info("Snapshots fresh (age=%.1f min). Running trade-agent.", age_minutes)
            pipeline.run()

        elapsed = time.time() - start
        sleep_seconds = max(0, interval_minutes * 60 - elapsed)
        if sleep_seconds:
            time.sleep(sleep_seconds)


def main() -> None:
    args = parse_args()
    run_scheduler(args.interval_minutes, args.initial_delay_minutes)


if __name__ == "__main__":
    main()

