"""
Agent Test Harness
==================
Tests the trading agent's decision-making against simulated market data.
"""

import logging
import json
import subprocess
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config, DATA_DIR, PROJECT_ROOT, REPORTS_DIR
from generators.price_simulator import PriceSimulator

logger = logging.getLogger(__name__)


@dataclass
class TradeDecision:
    """Represents a trade decision from the agent"""
    user_id: int
    action: str  # buy, sell, hold
    token_mint: Optional[str]
    amount: Optional[float]
    confidence: float
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "action": self.action,
            "token_mint": self.token_mint,
            "amount": self.amount,
            "confidence": self.confidence,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class TradeResult:
    """Result of a trade execution"""
    decision: TradeDecision
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    status: str = "pending"  # pending, executed, skipped, failed
    
    def to_dict(self) -> dict:
        return {
            "decision": self.decision.to_dict(),
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "status": self.status
        }


class AgentTestHarness:
    """
    Test harness for evaluating the trading agent's performance.
    
    Features:
    - Runs agent against simulated market data
    - Captures and analyzes trade decisions
    - Calculates performance metrics
    - Generates detailed reports
    """
    
    def __init__(self):
        self.config = config.agent_test
        self.price_simulator = PriceSimulator()
        self.decisions: List[TradeDecision] = []
        self.results: List[TradeResult] = []
        self.agent_users = self.config.agent_user_ids
    
    def prepare_test_data(self, coins: List[Dict], users: List[Dict]):
        """
        Prepare test data for the agent.
        
        This populates the SQLite database and CSVs that the trade-agent reads.
        """
        logger.info("Preparing test data for agent...")
        
        # Simulate prices
        self.price_simulator.simulate_all_coins(coins, save_to_file=True)
        
        # Generate trend signals based on price data
        self._generate_trend_signals()
        
        # Generate rule evaluations
        self._generate_rule_evaluations(users)
        
        # Generate user preferences
        self._generate_user_preferences(users)
        
        logger.info("Test data preparation complete")
    
    def _generate_trend_signals(self):
        """Generate trend signals CSV from price simulation"""
        signals = self.price_simulator.identify_signals(lookback_hours=4)
        
        csv_file = DATA_DIR / "trend_signals.csv"
        
        import csv
        with open(csv_file, 'w', newline='') as f:
            fieldnames = ["token_mint", "trend", "confidence", "timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for signal in signals:
                writer.writerow({
                    "token_mint": signal["denom"],
                    "trend": "bullish" if signal["signal"] == "BULLISH" else "bearish",
                    "confidence": round(signal["strength"], 3),
                    "timestamp": signal["timestamp"]
                })
        
        logger.info(f"Generated {len(signals)} trend signals")
    
    def _generate_rule_evaluations(self, users: List[Dict]):
        """Generate rule evaluations CSV for agent users"""
        csv_file = DATA_DIR / "rule_evaluations.csv"
        
        import csv
        with open(csv_file, 'w', newline='') as f:
            fieldnames = ["user_id", "token_mint", "allowed", "max_position_ndollar", 
                         "max_daily_trades", "reason", "confidence"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Load coins
            coins_file = DATA_DIR / "generated_coins.json"
            coins = []
            if coins_file.exists():
                with open(coins_file, 'r') as cf:
                    coins = json.load(cf)
            
            for user in users:
                if user.get("index") not in self.agent_users:
                    continue
                
                user_id = user.get("user_id", user.get("index"))
                prefs = user.get("preferences", {})
                
                # Allow trading all coins for agent users
                for coin in coins[:20]:  # Limit to 20 coins per user for testing
                    writer.writerow({
                        "user_id": user_id,
                        "token_mint": coin["denom"],
                        "allowed": 1,
                        "max_position_ndollar": prefs.get("max_position_ndollar", 500),
                        "max_daily_trades": prefs.get("max_trades_per_day", 5),
                        "reason": "testing_allowed",
                        "confidence": 0.8
                    })
        
        logger.info("Generated rule evaluations")
    
    def _generate_user_preferences(self, users: List[Dict]):
        """Generate user preferences CSV"""
        csv_file = DATA_DIR / "user_preferences.csv"
        
        import csv
        with open(csv_file, 'w', newline='') as f:
            fieldnames = ["user_id", "max_position_ndollar", "max_trades_per_day", "risk_level"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for user in users:
                if user.get("index") not in self.agent_users:
                    continue
                
                user_id = user.get("user_id", user.get("index"))
                prefs = user.get("preferences", {})
                
                writer.writerow({
                    "user_id": user_id,
                    "max_position_ndollar": prefs.get("max_position_ndollar", 500),
                    "max_trades_per_day": prefs.get("max_trades_per_day", 5),
                    "risk_level": prefs.get("risk_level", "medium")
                })
        
        logger.info("Generated user preferences")
    
    def run_agent(self, user_ids: List[int] = None, dry_run: bool = True) -> List[TradeDecision]:
        """
        Run the trade-agent for specified users.
        
        Args:
            user_ids: List of user IDs to run agent for
            dry_run: Whether to run in dry-run mode
            
        Returns:
            List of trade decisions
        """
        user_ids = user_ids or self.agent_users
        
        logger.info(f"Running trade-agent for users: {user_ids}")
        
        # Set up environment for agent
        env = os.environ.copy()
        env["DRY_RUN"] = "true" if dry_run else "false"
        env["SQLITE_PATH"] = str(PROJECT_ROOT / "fetch-data-agent" / "data" / "user_data.db")
        env["SNAPSHOT_DIR"] = str(PROJECT_ROOT / "fetch-data-agent" / "data")
        env["DATA_DIR"] = str(DATA_DIR)
        
        trade_agent_dir = PROJECT_ROOT / "trade-agent"
        
        # Run trade agent
        decisions = []
        
        for user_id in user_ids:
            try:
                # Run agent for single user
                cmd = [
                    sys.executable, 
                    str(trade_agent_dir / "main.py"),
                    "--user-ids", str(user_id)
                ]
                
                result = subprocess.run(
                    cmd,
                    cwd=str(trade_agent_dir),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    # Parse decision from output
                    decision = self._parse_agent_output(user_id, result.stdout)
                    if decision:
                        decisions.append(decision)
                        self.decisions.append(decision)
                else:
                    logger.warning(f"Agent failed for user {user_id}: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.error(f"Agent timeout for user {user_id}")
            except Exception as e:
                logger.error(f"Error running agent for user {user_id}: {e}")
        
        logger.info(f"Collected {len(decisions)} decisions")
        return decisions
    
    def _parse_agent_output(self, user_id: int, output: str) -> Optional[TradeDecision]:
        """Parse trade decision from agent output"""
        try:
            # Look for decision pattern in output
            # Format: User X decision: action token=Y amount=Z conf=W reason=R
            import re
            
            pattern = r"User (\d+) decision: (\w+) token=(\S+) amount=(\S+) conf=(\d+\.\d+) reason=(.+)"
            match = re.search(pattern, output)
            
            if match:
                return TradeDecision(
                    user_id=int(match.group(1)),
                    action=match.group(2),
                    token_mint=match.group(3) if match.group(3) != "None" else None,
                    amount=float(match.group(4)) if match.group(4) != "None" else None,
                    confidence=float(match.group(5)),
                    reason=match.group(6)
                )
            
            # Try alternative patterns
            if "hold" in output.lower():
                return TradeDecision(
                    user_id=user_id,
                    action="hold",
                    token_mint=None,
                    amount=None,
                    confidence=0.5,
                    reason="No action taken"
                )
                
        except Exception as e:
            logger.error(f"Failed to parse agent output: {e}")
        
        return None
    
    def simulate_agent_decisions(self, users: List[Dict], coins: List[Dict]) -> List[TradeDecision]:
        """
        Simulate agent decisions without running the actual agent.
        Useful for testing the test harness itself.
        
        Args:
            users: List of user data
            coins: List of coin data
            
        Returns:
            List of simulated decisions
        """
        import random
        
        logger.info("Simulating agent decisions...")
        
        decisions = []
        signals = self.price_simulator.identify_signals(lookback_hours=4)
        
        for user in users:
            if user.get("index") not in self.agent_users:
                continue
            
            user_id = user.get("user_id", user.get("index"))
            prefs = user.get("preferences", {})
            risk_level = prefs.get("risk_level", "medium")
            
            # Find bullish signals
            bullish_signals = [s for s in signals if s["signal"] == "BULLISH"]
            bearish_signals = [s for s in signals if s["signal"] == "BEARISH"]
            
            # Decide based on risk profile and signals
            if bullish_signals and random.random() < 0.6:
                # Buy signal
                signal = random.choice(bullish_signals)
                decision = TradeDecision(
                    user_id=user_id,
                    action="buy",
                    token_mint=signal["denom"],
                    amount=prefs.get("max_position_ndollar", 100) * signal["strength"],
                    confidence=0.5 + signal["strength"] * 0.4,
                    reason=f"Bullish signal on {signal['symbol']}"
                )
            elif bearish_signals and random.random() < 0.4:
                # Sell signal
                signal = random.choice(bearish_signals)
                decision = TradeDecision(
                    user_id=user_id,
                    action="sell",
                    token_mint=signal["denom"],
                    amount=prefs.get("max_position_ndollar", 100) * 0.5,
                    confidence=0.5 + signal["strength"] * 0.3,
                    reason=f"Bearish signal on {signal['symbol']}"
                )
            else:
                # Hold
                decision = TradeDecision(
                    user_id=user_id,
                    action="hold",
                    token_mint=None,
                    amount=None,
                    confidence=0.6,
                    reason="No clear signals"
                )
            
            decisions.append(decision)
            self.decisions.append(decision)
        
        logger.info(f"Simulated {len(decisions)} decisions")
        return decisions
    
    def evaluate_decisions(self, future_prices: Dict[str, float] = None) -> List[TradeResult]:
        """
        Evaluate trade decisions against actual/simulated price movements.
        
        Args:
            future_prices: Optional dict of token -> future price for evaluation
            
        Returns:
            List of trade results
        """
        logger.info("Evaluating trade decisions...")
        
        results = []
        
        for decision in self.decisions:
            result = TradeResult(decision=decision)
            
            if decision.action == "hold":
                result.status = "skipped"
                results.append(result)
                continue
            
            if not decision.token_mint:
                result.status = "skipped"
                results.append(result)
                continue
            
            # Get entry price (current)
            history = self.price_simulator.coin_histories.get(decision.token_mint)
            if not history or not history.price_points:
                result.status = "failed"
                result.pnl = 0
                results.append(result)
                continue
            
            result.entry_price = history.current_price
            
            # Get exit price (future or simulated)
            if future_prices and decision.token_mint in future_prices:
                result.exit_price = future_prices[decision.token_mint]
            else:
                # Simulate future price based on trend
                import random
                change = random.uniform(-0.1, 0.2)
                result.exit_price = result.entry_price * (1 + change)
            
            # Calculate P&L
            if decision.action == "buy":
                # Profit if price goes up
                result.pnl_percent = (result.exit_price - result.entry_price) / result.entry_price
                result.pnl = (decision.amount or 0) * result.pnl_percent
            elif decision.action == "sell":
                # Profit if price goes down (we sold high)
                result.pnl_percent = (result.entry_price - result.exit_price) / result.entry_price
                result.pnl = (decision.amount or 0) * result.pnl_percent
            
            result.status = "executed"
            results.append(result)
            self.results.append(result)
        
        logger.info(f"Evaluated {len(results)} trades")
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report"""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_decisions": len(self.decisions),
            "total_results": len(self.results),
            "agent_users": self.agent_users,
            "decisions_by_action": {},
            "results_summary": {},
            "performance": {}
        }
        
        # Count decisions by action
        for decision in self.decisions:
            action = decision.action
            report["decisions_by_action"][action] = report["decisions_by_action"].get(action, 0) + 1
        
        # Summarize results
        executed = [r for r in self.results if r.status == "executed"]
        wins = [r for r in executed if r.pnl > 0]
        losses = [r for r in executed if r.pnl < 0]
        
        report["results_summary"] = {
            "executed": len(executed),
            "skipped": len([r for r in self.results if r.status == "skipped"]),
            "failed": len([r for r in self.results if r.status == "failed"]),
            "wins": len(wins),
            "losses": len(losses)
        }
        
        # Performance metrics
        if executed:
            total_pnl = sum(r.pnl for r in executed)
            avg_pnl = total_pnl / len(executed)
            win_rate = len(wins) / len(executed) if executed else 0
            
            report["performance"] = {
                "total_pnl": round(total_pnl, 4),
                "avg_pnl_per_trade": round(avg_pnl, 4),
                "win_rate": round(win_rate, 4),
                "best_trade": max((r.pnl for r in executed), default=0),
                "worst_trade": min((r.pnl for r in executed), default=0)
            }
        
        # Save report
        report_file = REPORTS_DIR / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {report_file}")
        
        return report
    
    def print_summary(self):
        """Print a summary of test results"""
        report = self.generate_report()
        
        print("\n" + "="*60)
        print("🤖 AGENT TEST RESULTS")
        print("="*60)
        
        print(f"\n📊 Decisions Summary:")
        for action, count in report["decisions_by_action"].items():
            print(f"   {action.upper()}: {count}")
        
        print(f"\n📈 Results Summary:")
        for status, count in report["results_summary"].items():
            print(f"   {status}: {count}")
        
        if report["performance"]:
            print(f"\n💰 Performance:")
            print(f"   Total P&L: ${report['performance']['total_pnl']:.2f}")
            print(f"   Avg P&L/Trade: ${report['performance']['avg_pnl_per_trade']:.2f}")
            print(f"   Win Rate: {report['performance']['win_rate']*100:.1f}%")
            print(f"   Best Trade: ${report['performance']['best_trade']:.2f}")
            print(f"   Worst Trade: ${report['performance']['worst_trade']:.2f}")
        
        print("\n" + "="*60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Load test data
    coins_file = DATA_DIR / "generated_coins.json"
    users_file = DATA_DIR / "generated_users.json"
    
    coins = []
    users = []
    
    if coins_file.exists():
        with open(coins_file, 'r') as f:
            coins = json.load(f)
    
    if users_file.exists():
        with open(users_file, 'r') as f:
            users = json.load(f)
    
    if not coins or not users:
        print("Please generate test data first using the generators.")
        sys.exit(1)
    
    # Run test harness
    harness = AgentTestHarness()
    harness.prepare_test_data(coins, users)
    
    # Simulate decisions (or run actual agent)
    decisions = harness.simulate_agent_decisions(users, coins)
    
    # Evaluate
    results = harness.evaluate_decisions()
    
    # Print summary
    harness.print_summary()

