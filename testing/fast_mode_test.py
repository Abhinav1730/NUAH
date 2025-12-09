#!/usr/bin/env python3
"""
Fast Mode Test
==============
Tests the fast trading pipeline specifically for meme coin trading.

This script:
1. Generates test data (coins, users, prices)
2. Generates agent signals (news, trend, rules)
3. Runs the fast pipeline in test mode
4. Evaluates performance and generates report

Usage:
    python fast_mode_test.py                    # Full test
    python fast_mode_test.py --duration 300    # 5-minute test
    python fast_mode_test.py --dry-run         # Dry run mode
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config, DATA_DIR, REPORTS_DIR, PROJECT_ROOT, ensure_directories
from generators.coin_generator import CoinGenerator
from generators.user_generator import UserGenerator
from generators.price_simulator import PriceSimulator
from generators.signal_generator import SignalGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class FastModeTest:
    """
    Test harness specifically for the fast trading pipeline.
    
    Tests:
    - Price monitoring
    - Pattern detection  
    - Risk guard (stop-loss, take-profit)
    - Emergency exits
    - Agent signal integration
    """
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.coin_generator = CoinGenerator()
        self.user_generator = UserGenerator()
        self.price_simulator = PriceSimulator()
        self.signal_generator = SignalGenerator()
        
        self.coins = []
        self.users = []
        self.results = {
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0,
            "coins_tested": 0,
            "users_tested": 0,
            "signals_generated": {},
            "trades_made": 0,
            "patterns_detected": {},
            "pnl_total": 0.0,
            "errors": []
        }
        
        ensure_directories()
    
    def setup_test_data(
        self,
        num_coins: int = 50,
        num_users: int = 100,
        price_hours: int = 4
    ) -> None:
        """
        Generate all test data needed for fast mode testing.
        
        Args:
            num_coins: Number of test coins
            num_users: Number of test users
            price_hours: Hours of price history to simulate
        """
        logger.info("="*60)
        logger.info("SETTING UP TEST DATA")
        logger.info("="*60)
        
        # Generate coins
        logger.info(f"Generating {num_coins} test coins...")
        self.coins = self.coin_generator.generate_coins(
            count=num_coins,
            creator_address="nuah1testcreator",
            save_to_db=False,
            save_to_file=True
        )
        self.results["coins_tested"] = len(self.coins)
        
        # Generate users
        logger.info(f"Generating {num_users} test users...")
        self.users, _ = self.user_generator.generate_users(
            count=num_users,
            agent_user_ids=config.users.agent_user_ids,
            save_to_db=False,
            save_to_file=True
        )
        self.results["users_tested"] = len([
            u for u in self.users 
            if u.get("index") in config.users.agent_user_ids
        ])
        
        # Generate price history
        logger.info(f"Simulating {price_hours}h of price data...")
        self.price_simulator.simulate_all_coins(
            self.coins,
            duration_hours=price_hours,
            save_to_file=True
        )
        
        # Generate agent signals
        logger.info("Generating agent signals...")
        signals = self.signal_generator.generate_all_signals(
            self.coins,
            self.users,
            self.price_simulator.coin_histories
        )
        self.results["signals_generated"] = {
            "news": len(signals["news_signals"]),
            "trend": len(signals["trend_signals"]),
            "rules": len(signals["rule_evaluations"])
        }
        
        logger.info("✅ Test data setup complete")
    
    def run_fast_pipeline(
        self,
        duration_seconds: int = 60,
        user_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Run the fast trading pipeline for testing.
        
        Args:
            duration_seconds: How long to run the test
            user_ids: List of user IDs to test
            
        Returns:
            Test results dictionary
        """
        user_ids = user_ids or config.users.agent_user_ids
        
        logger.info("="*60)
        logger.info("RUNNING FAST PIPELINE TEST")
        logger.info(f"Duration: {duration_seconds}s")
        logger.info(f"Users: {user_ids}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("="*60)
        
        self.results["start_time"] = datetime.now(timezone.utc).isoformat()
        
        # Set up environment
        env = os.environ.copy()
        env["DRY_RUN"] = "true" if self.dry_run else "false"
        env["SQLITE_PATH"] = str(PROJECT_ROOT / "fetch-data-agent" / "data" / "user_data.db")
        env["DATA_DIR"] = str(DATA_DIR)
        env["PRICE_POLL_INTERVAL_SECONDS"] = "5"
        env["DECISION_INTERVAL_SECONDS"] = "15"
        
        trade_agent_dir = PROJECT_ROOT / "trade-agent"
        
        try:
            # Check if fast pipeline exists
            fast_pipeline_path = trade_agent_dir / "src" / "pipeline" / "fast_pipeline.py"
            if not fast_pipeline_path.exists():
                logger.error(f"Fast pipeline not found at {fast_pipeline_path}")
                self.results["errors"].append("Fast pipeline not found")
                return self.results
            
            # Run the fast pipeline
            cmd = [
                sys.executable,
                str(trade_agent_dir / "main.py"),
                "--user-ids", ",".join(map(str, user_ids)),
            ]
            
            if self.dry_run:
                cmd.append("--dry-run")
            
            logger.info(f"Starting fast pipeline: {' '.join(cmd)}")
            
            # Run with timeout
            process = subprocess.Popen(
                cmd,
                cwd=str(trade_agent_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Let it run for specified duration
            start_time = time.time()
            output_lines = []
            
            while time.time() - start_time < duration_seconds:
                # Check if process is still running
                if process.poll() is not None:
                    break
                
                # Read output
                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        output_lines.append(line.strip())
                        logger.debug(line.strip())
                
                time.sleep(0.5)
            
            # Stop the process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            # Parse results from output
            self._parse_pipeline_output(output_lines)
            
        except Exception as e:
            logger.exception(f"Fast pipeline test failed: {e}")
            self.results["errors"].append(str(e))
        
        self.results["end_time"] = datetime.now(timezone.utc).isoformat()
        self.results["duration_seconds"] = duration_seconds
        
        return self.results
    
    def run_simulated_test(
        self,
        duration_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Run a simulated test without the actual pipeline.
        
        This tests the signal generation and pattern detection logic
        without needing the full trade-agent to run.
        
        Args:
            duration_seconds: Simulation duration
            
        Returns:
            Test results dictionary
        """
        logger.info("="*60)
        logger.info("RUNNING SIMULATED FAST MODE TEST")
        logger.info("="*60)
        
        self.results["start_time"] = datetime.now(timezone.utc).isoformat()
        
        # Load price data
        if not self.price_simulator.coin_histories:
            self.price_simulator.load_from_file()
        
        # Simulate pattern detection
        signals = self.price_simulator.identify_signals(lookback_hours=1)
        
        # Count patterns
        patterns = {}
        for signal in signals:
            pattern = signal.get("pattern", "unknown")
            patterns[pattern] = patterns.get(pattern, 0) + 1
        
        self.results["patterns_detected"] = patterns
        
        # Simulate trades based on signals
        bullish = [s for s in signals if s["signal"] == "BULLISH"]
        bearish = [s for s in signals if s["signal"] == "BEARISH"]
        
        simulated_trades = []
        pnl_total = 0.0
        
        for signal in bullish[:5]:  # Take top 5 bullish signals
            # Simulate a buy
            entry_price = self.price_simulator.get_price_at_time(
                signal["denom"],
                datetime.now(timezone.utc)
            ) or 0.001
            
            # Simulate price movement
            import random
            exit_price = entry_price * (1 + random.uniform(-0.1, 0.3))
            pnl = (exit_price - entry_price) / entry_price * 100
            pnl_total += pnl
            
            simulated_trades.append({
                "token": signal["denom"],
                "action": "buy",
                "entry": entry_price,
                "exit": exit_price,
                "pnl_percent": round(pnl, 2)
            })
        
        self.results["trades_made"] = len(simulated_trades)
        self.results["pnl_total"] = round(pnl_total, 2)
        self.results["simulated_trades"] = simulated_trades
        self.results["end_time"] = datetime.now(timezone.utc).isoformat()
        self.results["duration_seconds"] = duration_seconds
        
        return self.results
    
    def _parse_pipeline_output(self, output_lines: List[str]) -> None:
        """Parse pipeline output for metrics."""
        import re
        
        for line in output_lines:
            # Look for pattern detections
            if "pattern" in line.lower():
                match = re.search(r'pattern[:\s]+(\w+)', line, re.IGNORECASE)
                if match:
                    pattern = match.group(1)
                    self.results["patterns_detected"][pattern] = (
                        self.results["patterns_detected"].get(pattern, 0) + 1
                    )
            
            # Look for trade executions
            if "execute" in line.lower() or "trade" in line.lower():
                self.results["trades_made"] += 1
            
            # Look for P&L
            pnl_match = re.search(r'pnl[:\s]+([-\d.]+)', line, re.IGNORECASE)
            if pnl_match:
                try:
                    self.results["pnl_total"] += float(pnl_match.group(1))
                except ValueError:
                    pass
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        report = {
            "test_type": "fast_mode",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "dry_run": self.dry_run,
                "agent_users": config.users.agent_user_ids
            },
            "results": self.results
        }
        
        # Save report
        report_file = REPORTS_DIR / f"fast_mode_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Report saved to {report_file}")
        return report
    
    def print_summary(self) -> None:
        """Print test summary."""
        print("\n" + "="*60)
        print("🚀 FAST MODE TEST RESULTS")
        print("="*60)
        
        print(f"\n⏱️  Duration: {self.results['duration_seconds']}s")
        print(f"🪙 Coins tested: {self.results['coins_tested']}")
        print(f"👤 Users tested: {self.results['users_tested']}")
        
        print(f"\n📊 Signals Generated:")
        for sig_type, count in self.results.get("signals_generated", {}).items():
            print(f"   {sig_type}: {count}")
        
        print(f"\n🔍 Patterns Detected:")
        for pattern, count in self.results.get("patterns_detected", {}).items():
            print(f"   {pattern}: {count}")
        
        print(f"\n💰 Trading Results:")
        print(f"   Trades made: {self.results['trades_made']}")
        print(f"   Total P&L: {self.results['pnl_total']:.2f}%")
        
        if self.results.get("simulated_trades"):
            print(f"\n📈 Simulated Trades:")
            for trade in self.results["simulated_trades"][:5]:
                pnl_emoji = "🟢" if trade["pnl_percent"] > 0 else "🔴"
                print(f"   {pnl_emoji} {trade['action'].upper()} {trade['token'].split('/')[-1]}: {trade['pnl_percent']:+.2f}%")
        
        if self.results["errors"]:
            print(f"\n❌ Errors:")
            for error in self.results["errors"]:
                print(f"   {error}")
        
        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Fast Mode Test for NUAH Trading Agent"
    )
    
    parser.add_argument("--duration", type=int, default=60,
                       help="Test duration in seconds (default: 60)")
    parser.add_argument("--coins", type=int, default=50,
                       help="Number of test coins (default: 50)")
    parser.add_argument("--users", type=int, default=100,
                       help="Number of test users (default: 100)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Run in dry-run mode (default: True)")
    parser.add_argument("--live", action="store_true",
                       help="Run with live pipeline (not just simulation)")
    parser.add_argument("--skip-setup", action="store_true",
                       help="Skip data generation, use existing data")
    
    args = parser.parse_args()
    
    # Initialize test
    test = FastModeTest(dry_run=args.dry_run)
    
    try:
        # Setup test data
        if not args.skip_setup:
            test.setup_test_data(
                num_coins=args.coins,
                num_users=args.users,
                price_hours=4
            )
        else:
            # Load existing data
            coins_file = DATA_DIR / "generated_coins.json"
            users_file = DATA_DIR / "generated_users.json"
            
            if coins_file.exists():
                with open(coins_file, 'r') as f:
                    test.coins = json.load(f)
                test.results["coins_tested"] = len(test.coins)
            
            if users_file.exists():
                with open(users_file, 'r') as f:
                    test.users = json.load(f)
            
            test.price_simulator.load_from_file()
        
        # Run test
        if args.live:
            test.run_fast_pipeline(duration_seconds=args.duration)
        else:
            test.run_simulated_test(duration_seconds=args.duration)
        
        # Generate report
        test.generate_report()
        test.print_summary()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

