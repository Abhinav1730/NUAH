#!/usr/bin/env python3
"""
Scheduler for rules-agent

Runs the rules evaluation pipeline on a fast schedule for meme coin trading.
Optimized for pump.fun-style rapid market movements.

Usage:
    python scheduler.py --interval-minutes 5 --initial-delay-minutes 2
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
logger = logging.getLogger("rules-agent-scheduler")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Schedule rules-agent runs (pump.fun optimized)."
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=int(os.getenv("RULES_INTERVAL_MINUTES", "5")),  # Changed: 40 -> 5 for pump.fun
        help="Minutes between runs (default: 5 for pump.fun).",
    )
    parser.add_argument(
        "--initial-delay-minutes",
        type=int,
        default=int(os.getenv("RULES_INITIAL_DELAY_MINUTES", "2")),  # Changed: 4 -> 2
        help="Delay before first run (default: 2).",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run once and exit instead of continuous scheduling.",
    )
    return parser.parse_args()


def run_rules_pipeline() -> bool:
    """Run the rules evaluation pipeline."""
    try:
        from src.config import get_settings
        from src.pipeline import RulesAgentPipeline
        
        settings = get_settings()
        pipeline = RulesAgentPipeline(settings)
        pipeline.run()
        logger.info("Rules evaluation completed")
        return True
    except ImportError as e:
        logger.error("Import error: %s", e)
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        return False
    except Exception as e:
        logger.exception("Rules pipeline failed: %s", e)
        return False


def run_scheduler(interval_minutes: int, initial_delay_minutes: int, run_once: bool = False) -> None:
    """Run the scheduler loop."""
    
    if initial_delay_minutes > 0 and not run_once:
        logger.info("Waiting %d minute(s) before first run...", initial_delay_minutes)
        time.sleep(initial_delay_minutes * 60)
    
    logger.info(
        "Rules-agent scheduler started (interval=%d min).",
        interval_minutes,
    )
    
    run_count = 0
    while True:
        run_count += 1
        start = time.time()
        
        logger.info("=" * 50)
        logger.info("Run #%d started at %s", run_count, datetime.now(timezone.utc).isoformat())
        logger.info("=" * 50)
        
        success = run_rules_pipeline()
        
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
    print("📋 RULES-AGENT SCHEDULER")
    print("=" * 50)
    print(f"Interval: {args.interval_minutes} minutes")
    print(f"Initial delay: {args.initial_delay_minutes} minutes")
    print(f"Run once: {args.run_once}")
    print("=" * 50)
    print("")
    
    try:
        run_scheduler(
            args.interval_minutes,
            args.initial_delay_minutes,
            args.run_once,
        )
    except KeyboardInterrupt:
        logger.info("\n🛑 Scheduler stopped by user")


if __name__ == "__main__":
    main()

