from __future__ import annotations

import argparse
import logging
from typing import List, Optional

from src.config import get_settings
from src.pipeline import TradePipeline


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("trade-agent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the trade-agent pipeline.")
    parser.add_argument(
        "--user-ids",
        type=str,
        help="Comma-separated list of user IDs to process (overrides settings)",
    )
    return parser.parse_args()


def parse_user_ids(value: Optional[str]) -> Optional[List[int]]:
    if not value:
        return None
    return [int(part.strip()) for part in value.split(",") if part.strip().isdigit()]


def main() -> None:
    args = parse_args()
    settings = get_settings()
    pipeline = TradePipeline(settings)

    user_ids = parse_user_ids(args.user_ids) or settings.user_ids
    logger.info("Starting trade-agent run")
    pipeline.run(user_ids=user_ids)
    logger.info("Run complete")


if __name__ == "__main__":
    main()

