#!/usr/bin/env python3
"""
Scheduler for trend-agent

Runs the trend analysis pipeline on a fast schedule for meme coin trading.
Optimized for pump.fun-style rapid market movements.

Usage:
    python scheduler.py --interval-minutes 5 --initial-delay-minutes 1
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("trend-agent-scheduler")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Schedule trend-agent runs (pump.fun optimized)."
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=int(os.getenv("TREND_INTERVAL_MINUTES", "5")),  # Changed: 35 -> 5 for pump.fun
        help="Minutes between runs (default: 5 for pump.fun).",
    )
    parser.add_argument(
        "--initial-delay-minutes",
        type=int,
        default=int(os.getenv("TREND_INITIAL_DELAY_MINUTES", "1")),  # Changed: 3 -> 1
        help="Delay before first run (default: 1).",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run once and exit instead of continuous scheduling.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no writes).",
    )
    return parser.parse_args()


def run_trend_pipeline(dry_run: bool = False) -> bool:
    """Run the trend analysis pipeline."""
    try:
        from src.config import get_settings
        from src.pipeline import TrendAgentPipeline
        
        settings = get_settings()
        if dry_run:
            settings = settings.model_copy(update={"dry_run": True})
        
        pipeline = TrendAgentPipeline(settings)
        pipeline.run()
        logger.info("Trend analysis completed")
        return True
    except ImportError as e:
        logger.error("Import error: %s", e)
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        return False
    except Exception as e:
        logger.exception("Trend pipeline failed: %s", e)
        return False


def run_scheduler(interval_minutes: int, initial_delay_minutes: int, run_once: bool = False, dry_run: bool = False) -> None:
    """Run the scheduler loop."""
    
    if initial_delay_minutes > 0 and not run_once:
        logger.info("Waiting %d minute(s) before first run...", initial_delay_minutes)
        time.sleep(initial_delay_minutes * 60)
    
    logger.info(
        "Trend-agent scheduler started (interval=%d min, dry_run=%s).",
        interval_minutes,
        dry_run,
    )
    
    run_count = 0
    while True:
        run_count += 1
        start = time.time()
        
        logger.info("=" * 50)
        logger.info("Run #%d started at %s", run_count, datetime.now(timezone.utc).isoformat())
        logger.info("=" * 50)
        
        success = run_trend_pipeline(dry_run)
        
        if success:
            logger.info("✅ Run #%d completed successfully", run_count)
        else:
            logger.warning("⚠️ Run #%d completed with errors", run_count)
        
        if run_once:
            logger.info("Run-once mode; exiting.")
            break
        
        elapsed = time.time() - start
        sleep_seconds = max(0, interval_minutes * 60 - elapsed)
        
        if sleep_seconds > 0:
            logger.info("Sleeping %.1f minutes until next run...\n", sleep_seconds / 60)
            time.sleep(sleep_seconds)


def main() -> None:
    args = parse_args()
    
    print("")
    print("=" * 50)
    print("📈 TREND-AGENT SCHEDULER")
    print("=" * 50)
    print(f"Interval: {args.interval_minutes} minutes")
    print(f"Initial delay: {args.initial_delay_minutes} minutes")
    print(f"Run once: {args.run_once}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 50)
    print("")
    
    try:
        run_scheduler(
            args.interval_minutes,
            args.initial_delay_minutes,
            args.run_once,
            args.dry_run,
        )
    except KeyboardInterrupt:
        logger.info("\n🛑 Scheduler stopped by user")


if __name__ == "__main__":
    main()

