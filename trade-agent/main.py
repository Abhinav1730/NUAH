from __future__ import annotations

import argparse
import asyncio
import logging
from typing import List, Optional

from src.config import get_settings
from src.pipeline import TradePipeline, FastTradePipeline


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("trade-agent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NUAH Trade Agent - Supports standard and fast (pump.fun) trading modes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Trading Modes:
  standard  - Traditional interval-based trading (30-60 min cycles)
              Best for: Stable coins, longer-term positions
              
  fast      - Real-time pump.fun-style trading (5-15 sec cycles)
              Best for: Meme coins, volatile markets, quick scalps
              
Examples:
  python main.py --mode fast --user-ids 1,2,3,4,5
  python main.py --mode standard --user-ids 1
  python main.py --mode fast --duration 3600  # Run for 1 hour
        """
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["standard", "fast"],
        default="fast",
        help="Trading mode: 'standard' (interval) or 'fast' (real-time). Default: fast",
    )
    parser.add_argument(
        "--user-ids",
        type=str,
        help="Comma-separated list of user IDs to process",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration to run in seconds (fast mode only). Default: indefinite",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no real trades)",
    )
    return parser.parse_args()


def parse_user_ids(value: Optional[str]) -> Optional[List[int]]:
    if not value:
        return None
    return [int(part.strip()) for part in value.split(",") if part.strip().isdigit()]


def run_standard_mode(settings, user_ids: List[int]):
    """Run standard interval-based trading"""
    logger.info("=" * 60)
    logger.info("🔄 STANDARD MODE: Interval-based trading")
    logger.info("=" * 60)
    
    pipeline = TradePipeline(settings)
    pipeline.run(user_ids=user_ids)


def run_fast_mode(settings, user_ids: List[int], duration: Optional[int] = None):
    """Run fast real-time trading"""
    logger.info("=" * 60)
    logger.info("⚡ FAST MODE: Real-time pump.fun-style trading")
    logger.info(f"   Poll interval: {settings.price_poll_interval_seconds}s")
    logger.info(f"   Decision interval: {settings.decision_interval_seconds}s")
    logger.info(f"   Stop loss: {settings.stop_loss_percent * 100}%")
    logger.info(f"   Take profit: {settings.take_profit_percent * 100}%")
    logger.info("=" * 60)
    
    pipeline = FastTradePipeline(settings)
    
    if duration:
        # Run for specific duration (sync mode)
        logger.info(f"Running for {duration} seconds...")
        pipeline.run_sync(user_ids=user_ids, duration_seconds=duration)
    else:
        # Run indefinitely (async mode)
        logger.info("Running indefinitely (Ctrl+C to stop)...")
        asyncio.run(pipeline.run(user_ids=user_ids))


def main() -> None:
    args = parse_args()
    settings = get_settings()
    
    # Override settings from args
    if args.dry_run:
        settings.dry_run = True
    
    user_ids = parse_user_ids(args.user_ids) or settings.user_ids
    
    if not user_ids:
        logger.error("No user IDs specified! Use --user-ids or set USER_IDS env var.")
        return
    
    logger.info(f"Trade agent starting for users: {user_ids}")
    logger.info(f"Dry run: {settings.dry_run}")
    
    try:
        if args.mode == "fast":
            run_fast_mode(settings, user_ids, args.duration)
        else:
            run_standard_mode(settings, user_ids)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Agent interrupted by user")
    except Exception as e:
        logger.exception(f"Agent error: {e}")
        raise
    
    logger.info("Trade agent finished")


if __name__ == "__main__":
    main()

