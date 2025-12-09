#!/usr/bin/env python3
"""
Live Simulation
===============
Runs a continuous live simulation for testing the trading system end-to-end.

This script:
1. Generates test data and seeds into database
2. Continuously updates prices (simulating real market)
3. Runs the fast pipeline against live-updating prices
4. Tracks and displays real-time performance

Usage:
    python live_simulation.py                    # Run for 1 hour
    python live_simulation.py --hours 24        # Run for 24 hours
    python live_simulation.py --realtime         # Real-time updates (5 sec)
"""

import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config, DATA_DIR, REPORTS_DIR, PROJECT_ROOT, ensure_directories
from generators.coin_generator import CoinGenerator
from generators.user_generator import UserGenerator
from generators.price_simulator import PriceSimulator, PricePattern
from generators.signal_generator import SignalGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class LiveSimulation:
    """
    Runs a continuous live simulation with updating prices.
    
    Features:
    - Real-time price updates to SQLite
    - Periodic signal regeneration
    - Trade tracking and performance monitoring
    - Live dashboard updates
    """
    
    def __init__(self):
        self.running = False
        self.price_simulator = PriceSimulator()
        self.signal_generator = SignalGenerator()
        
        # Paths
        self.sqlite_path = PROJECT_ROOT / "fetch-data-agent" / "data" / "user_data.db"
        
        # Stats
        self.stats = {
            "start_time": None,
            "price_updates": 0,
            "signal_updates": 0,
            "patterns_triggered": {},
            "current_prices": {},
            "trades_observed": 0
        }
        
        # Threading
        self._stop_event = threading.Event()
        
        ensure_directories()
    
    def setup_database(self) -> None:
        """Ensure database tables exist."""
        conn = sqlite3.connect(self.sqlite_path)
        
        # Create time_series table for live price updates
        conn.execute("""
            CREATE TABLE IF NOT EXISTS time_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_mint TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                momentum REAL,
                volatility REAL,
                pattern TEXT,
                UNIQUE(token_mint, timestamp)
            )
        """)
        
        # Create token_strategy_catalog table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_strategy_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_mint TEXT UNIQUE NOT NULL,
                name TEXT,
                symbol TEXT,
                bonding_curve_phase TEXT,
                risk_score REAL,
                liquidity_score REAL,
                volatility_score REAL,
                whale_concentration REAL,
                last_updated TIMESTAMP
            )
        """)
        
        # Create index for fast lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_time_series_token_time 
            ON time_series(token_mint, timestamp)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database tables ready")
    
    def load_or_generate_data(
        self,
        num_coins: int = 100,
        num_users: int = 1000
    ) -> None:
        """Load existing data or generate new data."""
        coins_file = DATA_DIR / "generated_coins.json"
        users_file = DATA_DIR / "generated_users.json"
        
        # Load or generate coins
        if coins_file.exists():
            with open(coins_file, 'r') as f:
                self.coins = json.load(f)
            logger.info(f"Loaded {len(self.coins)} existing coins")
        else:
            generator = CoinGenerator()
            self.coins = generator.generate_coins(
                count=num_coins,
                creator_address="nuah1simulation",
                save_to_file=True
            )
            logger.info(f"Generated {len(self.coins)} new coins")
        
        # Load or generate users
        if users_file.exists():
            with open(users_file, 'r') as f:
                self.users = json.load(f)
            logger.info(f"Loaded {len(self.users)} existing users")
        else:
            generator = UserGenerator()
            self.users, _ = generator.generate_users(
                count=num_users,
                agent_user_ids=config.users.agent_user_ids,
                save_to_file=True
            )
            logger.info(f"Generated {len(self.users)} new users")
        
        # Initialize price histories
        if not self.price_simulator.coin_histories:
            self.price_simulator.load_from_file()
        
        if not self.price_simulator.coin_histories:
            logger.info("Generating initial price histories...")
            self.price_simulator.simulate_all_coins(
                self.coins,
                duration_hours=1,
                save_to_file=True
            )
    
    def update_prices(self) -> None:
        """Generate and update prices for all coins."""
        timestamp = datetime.now(timezone.utc)
        
        conn = sqlite3.connect(self.sqlite_path)
        
        for coin in self.coins:
            denom = coin["denom"]
            
            # Get current history or create new
            history = self.price_simulator.coin_histories.get(denom)
            if not history:
                continue
            
            # Generate next price point
            current_price = history.current_price
            
            # Select pattern based on randomness
            pattern = self.price_simulator.select_pattern(coin.get("volatility_profile"))
            
            # Generate price change
            import random
            pattern_config = config.price_sim.patterns[pattern.value]
            gain_range = (pattern_config["gain_min"], pattern_config["gain_max"])
            
            # Smaller changes for continuous updates
            change_factor = random.uniform(gain_range[0], gain_range[1]) * 0.1
            new_price = current_price * (1 + change_factor)
            new_price = max(new_price, current_price * 0.0001)  # Floor
            
            # Calculate derived metrics
            momentum = change_factor
            volatility = abs(change_factor) * 2
            volume = random.uniform(1000, 100000)
            
            if pattern in [PricePattern.MEGA_PUMP, PricePattern.RUG_PULL]:
                volume *= 10
            
            # Update price history
            from generators.price_simulator import PricePoint
            point = PricePoint(
                timestamp=timestamp,
                price=new_price,
                volume=volume,
                pattern=pattern.value,
                price_change_pct=change_factor * 100
            )
            history.price_points.append(point)
            
            # Keep only last 1000 points
            if len(history.price_points) > 1000:
                history.price_points = history.price_points[-1000:]
            
            # Insert into database
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO time_series 
                    (token_mint, timestamp, open, high, low, close, volume, momentum, volatility, pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    denom,
                    timestamp.isoformat(),
                    current_price,
                    max(current_price, new_price),
                    min(current_price, new_price),
                    new_price,
                    volume,
                    momentum,
                    volatility,
                    pattern.value
                ))
            except sqlite3.Error as e:
                logger.warning(f"Failed to insert price for {denom}: {e}")
            
            # Update stats
            self.stats["current_prices"][denom] = new_price
            
            # Track pattern triggers
            if pattern.value not in ["sideways", "organic_growth"]:
                self.stats["patterns_triggered"][pattern.value] = (
                    self.stats["patterns_triggered"].get(pattern.value, 0) + 1
                )
        
        conn.commit()
        conn.close()
        
        self.stats["price_updates"] += 1
    
    def update_signals(self) -> None:
        """Regenerate agent signals based on current prices."""
        logger.info("🔄 Updating agent signals...")
        
        self.signal_generator.generate_all_signals(
            self.coins,
            self.users,
            self.price_simulator.coin_histories
        )
        
        self.stats["signal_updates"] += 1
    
    def check_trades(self) -> int:
        """Check for new trades in the database."""
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM trade_executions
            WHERE DATE(timestamp) = DATE('now', 'localtime')
        """)
        count = cursor.fetchone()[0]
        conn.close()
        
        new_trades = count - self.stats.get("trades_observed", 0)
        self.stats["trades_observed"] = count
        
        return new_trades
    
    def print_status(self) -> None:
        """Print current simulation status."""
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(self.stats["start_time"])).seconds
        
        print("\r" + " "*80, end="")  # Clear line
        print(
            f"\r⏱️ {elapsed}s | "
            f"📊 Prices: {self.stats['price_updates']} | "
            f"📈 Signals: {self.stats['signal_updates']} | "
            f"💰 Trades: {self.stats['trades_observed']} | "
            f"🔥 Patterns: {sum(self.stats['patterns_triggered'].values())}",
            end="",
            flush=True
        )
    
    def run(
        self,
        duration_hours: float = 1.0,
        price_interval_seconds: int = 60,
        signal_interval_seconds: int = 300,
        realtime: bool = False
    ) -> Dict[str, Any]:
        """
        Run the live simulation.
        
        Args:
            duration_hours: How long to run
            price_interval_seconds: Seconds between price updates
            signal_interval_seconds: Seconds between signal regeneration
            realtime: If True, use 5-second intervals for pump.fun realism
            
        Returns:
            Simulation results
        """
        if realtime:
            price_interval_seconds = 5
            signal_interval_seconds = 60
        
        self.running = True
        self.stats["start_time"] = datetime.now(timezone.utc).isoformat()
        
        end_time = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        
        logger.info("="*60)
        logger.info("🚀 LIVE SIMULATION STARTED")
        logger.info(f"   Duration: {duration_hours}h")
        logger.info(f"   Price interval: {price_interval_seconds}s")
        logger.info(f"   Signal interval: {signal_interval_seconds}s")
        logger.info(f"   Coins: {len(self.coins)}")
        logger.info("="*60)
        print()
        
        last_price_update = 0
        last_signal_update = 0
        
        try:
            while self.running and datetime.now(timezone.utc) < end_time:
                if self._stop_event.is_set():
                    break
                
                current_time = time.time()
                
                # Update prices
                if current_time - last_price_update >= price_interval_seconds:
                    self.update_prices()
                    last_price_update = current_time
                
                # Update signals
                if current_time - last_signal_update >= signal_interval_seconds:
                    self.update_signals()
                    last_signal_update = current_time
                
                # Check for trades
                self.check_trades()
                
                # Print status
                self.print_status()
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print()
            logger.info("⚠️ Simulation interrupted by user")
        
        self.running = False
        self.stats["end_time"] = datetime.now(timezone.utc).isoformat()
        
        print()
        return self.stats
    
    def stop(self) -> None:
        """Stop the simulation."""
        self.running = False
        self._stop_event.set()
    
    def print_summary(self) -> None:
        """Print final simulation summary."""
        print("\n" + "="*60)
        print("📊 LIVE SIMULATION SUMMARY")
        print("="*60)
        
        start = datetime.fromisoformat(self.stats["start_time"])
        end = datetime.fromisoformat(self.stats.get("end_time", datetime.now(timezone.utc).isoformat()))
        duration = (end - start).total_seconds()
        
        print(f"\n⏱️  Duration: {duration:.0f} seconds ({duration/60:.1f} minutes)")
        print(f"📊 Price updates: {self.stats['price_updates']}")
        print(f"📈 Signal updates: {self.stats['signal_updates']}")
        print(f"💰 Trades observed: {self.stats['trades_observed']}")
        
        if self.stats["patterns_triggered"]:
            print(f"\n🔥 Patterns Triggered:")
            for pattern, count in sorted(self.stats["patterns_triggered"].items(), 
                                        key=lambda x: x[1], reverse=True):
                print(f"   {pattern}: {count}")
        
        print("\n" + "="*60)
    
    def save_results(self) -> Path:
        """Save simulation results to file."""
        results_file = REPORTS_DIR / f"live_sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        results = {
            "simulation_type": "live",
            "stats": self.stats,
            "config": {
                "coins": len(self.coins),
                "users": len(self.users),
                "agent_users": config.users.agent_user_ids
            }
        }
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Results saved to {results_file}")
        return results_file


def main():
    parser = argparse.ArgumentParser(
        description="Live Simulation for NUAH Trading System"
    )
    
    parser.add_argument("--hours", type=float, default=1.0,
                       help="Simulation duration in hours (default: 1)")
    parser.add_argument("--coins", type=int, default=100,
                       help="Number of coins (default: 100)")
    parser.add_argument("--users", type=int, default=1000,
                       help="Number of users (default: 1000)")
    parser.add_argument("--realtime", action="store_true",
                       help="Use 5-second price intervals for pump.fun realism")
    parser.add_argument("--price-interval", type=int, default=60,
                       help="Seconds between price updates (default: 60)")
    parser.add_argument("--signal-interval", type=int, default=300,
                       help="Seconds between signal updates (default: 300)")
    
    args = parser.parse_args()
    
    # Initialize simulation
    sim = LiveSimulation()
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n⚠️ Stopping simulation...")
        sim.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Setup
        sim.setup_database()
        sim.load_or_generate_data(num_coins=args.coins, num_users=args.users)
        
        # Run simulation
        sim.run(
            duration_hours=args.hours,
            price_interval_seconds=args.price_interval,
            signal_interval_seconds=args.signal_interval,
            realtime=args.realtime
        )
        
        # Results
        sim.print_summary()
        sim.save_results()
        
    except Exception as e:
        logger.exception(f"Simulation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

