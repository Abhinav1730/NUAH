#!/usr/bin/env python3
"""
NUAH Trading Agent Simulation Runner
=====================================
Main orchestrator for running the complete testing simulation.

This script:
1. Generates 100 dummy coins with pump.fun-style characteristics
2. Creates 1000 test users with wallets
3. Simulates price movements over 24 hours
4. Runs the trading agent for 5 designated users
5. Evaluates performance and generates reports

Usage:
    python run_simulation.py                    # Full simulation
    python run_simulation.py --generate-only    # Only generate test data
    python run_simulation.py --test-only        # Only run tests (data must exist)
    python run_simulation.py --backtest         # Run backtest simulation
"""

import argparse
import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config, DATA_DIR, REPORTS_DIR, ensure_directories
from database.connection import db
from database.seed_postgres import PostgresSeeder
from generators.coin_generator import CoinGenerator
from generators.user_generator import UserGenerator, PortfolioGenerator
from generators.price_simulator import PriceSimulator
from agent_test.test_harness import AgentTestHarness
from agent_test.backtester import Backtester
from agent_test.metrics import PerformanceMetrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / f"simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)


class SimulationRunner:
    """
    Orchestrates the complete trading agent testing simulation.
    """
    
    def __init__(self, use_database: bool = True):
        """
        Initialize simulation runner.
        
        Args:
            use_database: Whether to use PostgreSQL (True) or file-only mode (False)
        """
        self.use_database = use_database
        self.seeder = PostgresSeeder() if use_database else None
        
        self.coin_generator = CoinGenerator(self.seeder)
        self.user_generator = UserGenerator(self.seeder)
        self.portfolio_generator = PortfolioGenerator(self.seeder)
        self.price_simulator = PriceSimulator()
        
        self.coins = []
        self.users = []
        self.wallets = []
        
        ensure_directories()
    
    def check_database(self) -> bool:
        """Check if database is accessible"""
        if not self.use_database:
            return True
        
        try:
            if db.health_check():
                logger.info("✅ Database connection successful")
                return True
            else:
                logger.error("❌ Database health check failed")
                return False
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            return False
    
    def generate_coins(self, count: int = 100) -> list:
        """Generate dummy coins"""
        logger.info(f"🪙 Generating {count} dummy coins...")
        
        # Create a test creator address
        creator_address = "nuah1testcreator0000000000000000000000000000"
        
        self.coins = self.coin_generator.generate_coins(
            count=count,
            creator_address=creator_address,
            save_to_db=self.use_database,
            save_to_file=True
        )
        
        logger.info(f"✅ Generated {len(self.coins)} coins")
        return self.coins
    
    def generate_users(self, count: int = 1000) -> tuple:
        """Generate test users"""
        logger.info(f"👥 Generating {count} test users...")
        
        self.users, self.wallets = self.user_generator.generate_users(
            count=count,
            agent_user_ids=config.users.agent_user_ids,
            save_to_db=self.use_database,
            save_to_file=True
        )
        
        logger.info(f"✅ Generated {len(self.users)} users with {len(self.wallets)} wallets")
        return self.users, self.wallets
    
    def assign_portfolios(self) -> list:
        """Assign coin holdings to users"""
        if not self.users or not self.coins:
            logger.warning("Users or coins not generated yet!")
            return []
        
        logger.info("💼 Assigning portfolios to users...")
        
        balances = self.portfolio_generator.assign_coins_to_users(
            users=self.users,
            coins=self.coins,
            save_to_db=self.use_database
        )
        
        logger.info(f"✅ Created {len(balances)} balance entries")
        return balances
    
    def simulate_prices(self, duration_hours: int = 24) -> dict:
        """Simulate price movements"""
        if not self.coins:
            logger.warning("Coins not generated yet!")
            return {}
        
        logger.info(f"📈 Simulating {duration_hours}h of price movements...")
        
        histories = self.price_simulator.simulate_all_coins(
            coins=self.coins,
            duration_hours=duration_hours,
            interval_minutes=config.price_sim.time_interval_minutes,
            save_to_file=True
        )
        
        logger.info(f"✅ Generated price data for {len(histories)} coins")
        return histories
    
    def run_agent_tests(self, simulate_only: bool = False) -> dict:
        """Run agent tests"""
        logger.info("🤖 Running agent tests...")
        
        harness = AgentTestHarness()
        harness.price_simulator = self.price_simulator
        
        # Prepare test data (CSVs for agent)
        harness.prepare_test_data(self.coins, self.users)
        
        # Get decisions
        if simulate_only:
            decisions = harness.simulate_agent_decisions(self.users, self.coins)
        else:
            # Try to run actual agent, fall back to simulation
            try:
                decisions = harness.run_agent(dry_run=True)
            except Exception as e:
                logger.warning(f"Could not run actual agent: {e}")
                logger.info("Falling back to simulated decisions...")
                decisions = harness.simulate_agent_decisions(self.users, self.coins)
        
        # Evaluate decisions
        results = harness.evaluate_decisions()
        
        # Generate report
        report = harness.generate_report()
        harness.print_summary()
        
        return report
    
    def run_backtest(self, interval_minutes: int = 15) -> dict:
        """Run backtest simulation"""
        logger.info("⏮️ Running backtest simulation...")
        
        # Ensure price data is loaded
        if not self.price_simulator.coin_histories:
            self.price_simulator.load_from_file()
        
        if not self.price_simulator.coin_histories:
            logger.error("No price data available for backtest!")
            return {}
        
        backtester = Backtester(self.price_simulator)
        results = backtester.run_backtest(
            users=self.users,
            interval_minutes=interval_minutes
        )
        
        backtester.print_results(results)
        
        # Calculate detailed metrics
        if backtester.trades:
            trades_dicts = [t.to_dict() for t in backtester.trades]
            initial_balance = sum(
                u.get("initial_balance_nuah", 1000) 
                for u in self.users 
                if u.get("index") in config.agent_test.agent_user_ids
            )
            
            metrics = PerformanceMetrics.calculate(
                trades=trades_dicts,
                initial_balance=initial_balance
            )
            metrics.print_report()
        
        return results
    
    def load_existing_data(self) -> bool:
        """Load previously generated data from files"""
        logger.info("📂 Loading existing test data...")
        
        # Load coins
        self.coins = self.coin_generator.load_from_file()
        if self.coins:
            logger.info(f"   Loaded {len(self.coins)} coins")
        
        # Load users
        self.users, self.wallets = self.user_generator.load_from_file()
        if self.users:
            logger.info(f"   Loaded {len(self.users)} users")
        
        # Load price data
        self.price_simulator.load_from_file()
        if self.price_simulator.coin_histories:
            logger.info(f"   Loaded price data for {len(self.price_simulator.coin_histories)} coins")
        
        return bool(self.coins and self.users)
    
    def run_full_simulation(
        self,
        num_coins: int = 100,
        num_users: int = 1000,
        price_duration_hours: int = 24,
        run_backtest: bool = True,
        simulate_agent: bool = True
    ) -> dict:
        """
        Run the complete simulation pipeline.
        
        Args:
            num_coins: Number of dummy coins to generate
            num_users: Number of test users to generate
            price_duration_hours: Hours of price data to simulate
            run_backtest: Whether to run backtest after generation
            simulate_agent: Whether to use simulated or real agent
            
        Returns:
            Complete simulation results
        """
        logger.info("="*70)
        logger.info("🚀 STARTING FULL SIMULATION")
        logger.info("="*70)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "num_coins": num_coins,
                "num_users": num_users,
                "price_duration_hours": price_duration_hours,
                "agent_users": config.agent_test.agent_user_ids
            }
        }
        
        # Phase 1: Check database
        if self.use_database:
            if not self.check_database():
                logger.warning("Database not available, switching to file-only mode")
                self.use_database = False
        
        # Phase 2: Generate coins
        self.generate_coins(num_coins)
        results["coins_generated"] = len(self.coins)
        
        # Phase 3: Generate users
        self.generate_users(num_users)
        results["users_generated"] = len(self.users)
        
        # Phase 4: Assign portfolios
        balances = self.assign_portfolios()
        results["balances_created"] = len(balances)
        
        # Phase 5: Simulate prices
        self.simulate_prices(price_duration_hours)
        results["price_simulation"] = {
            "duration_hours": price_duration_hours,
            "coins_simulated": len(self.price_simulator.coin_histories)
        }
        
        # Phase 6: Run agent tests
        agent_results = self.run_agent_tests(simulate_only=simulate_agent)
        results["agent_test"] = agent_results
        
        # Phase 7: Run backtest
        if run_backtest:
            backtest_results = self.run_backtest()
            results["backtest"] = backtest_results
        
        # Save results
        results_file = REPORTS_DIR / f"simulation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info("="*70)
        logger.info("✅ SIMULATION COMPLETE")
        logger.info(f"   Results saved to: {results_file}")
        logger.info("="*70)
        
        return results
    
    def print_summary(self):
        """Print simulation state summary"""
        print("\n" + "="*60)
        print("📊 SIMULATION STATE SUMMARY")
        print("="*60)
        
        print(f"\n🪙 Coins: {len(self.coins)}")
        if self.coins:
            print(f"   Sample: {', '.join(c['symbol'] for c in self.coins[:5])}...")
        
        print(f"\n👥 Users: {len(self.users)}")
        agent_users = [u for u in self.users if u.get("is_agent_user")]
        print(f"   Agent users: {len(agent_users)}")
        
        print(f"\n📈 Price Data: {len(self.price_simulator.coin_histories)} coins")
        if self.price_simulator.coin_histories:
            sample = list(self.price_simulator.coin_histories.values())[0]
            print(f"   Data points per coin: ~{len(sample.price_points)}")
        
        print(f"\n💾 Database mode: {'PostgreSQL' if self.use_database else 'File-only'}")
        print("\n" + "="*60)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="NUAH Trading Agent Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_simulation.py                     # Full simulation
  python run_simulation.py --generate-only     # Only generate data
  python run_simulation.py --test-only         # Only run tests
  python run_simulation.py --backtest          # Run backtest
  python run_simulation.py --coins 50 --users 500  # Custom counts
        """
    )
    
    parser.add_argument("--generate-only", action="store_true",
                       help="Only generate test data, don't run tests")
    parser.add_argument("--test-only", action="store_true",
                       help="Only run tests using existing data")
    parser.add_argument("--backtest", action="store_true",
                       help="Run backtest simulation")
    parser.add_argument("--coins", type=int, default=100,
                       help="Number of coins to generate (default: 100)")
    parser.add_argument("--users", type=int, default=1000,
                       help="Number of users to generate (default: 1000)")
    parser.add_argument("--hours", type=int, default=24,
                       help="Hours of price data to simulate (default: 24)")
    parser.add_argument("--no-database", action="store_true",
                       help="Don't use PostgreSQL, file-only mode")
    parser.add_argument("--real-agent", action="store_true",
                       help="Try to run the real trade-agent instead of simulation")
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = SimulationRunner(use_database=not args.no_database)
    
    try:
        if args.test_only:
            # Load existing data and run tests
            if not runner.load_existing_data():
                logger.error("No existing test data found! Run without --test-only first.")
                sys.exit(1)
            
            runner.run_agent_tests(simulate_only=not args.real_agent)
            
            if args.backtest:
                runner.run_backtest()
                
        elif args.generate_only:
            # Only generate data
            runner.generate_coins(args.coins)
            runner.generate_users(args.users)
            runner.assign_portfolios()
            runner.simulate_prices(args.hours)
            runner.print_summary()
            
        elif args.backtest:
            # Load and run backtest
            if not runner.load_existing_data():
                logger.info("No existing data, generating new data...")
                runner.generate_coins(args.coins)
                runner.generate_users(args.users)
                runner.assign_portfolios()
                runner.simulate_prices(args.hours)
            
            runner.run_backtest()
            
        else:
            # Full simulation
            runner.run_full_simulation(
                num_coins=args.coins,
                num_users=args.users,
                price_duration_hours=args.hours,
                run_backtest=True,
                simulate_agent=not args.real_agent
            )
            
    except KeyboardInterrupt:
        logger.info("\n⚠️ Simulation interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"❌ Simulation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

