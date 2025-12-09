"""
Backtester
==========
Replays historical price data to evaluate agent performance over time.
"""

import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Generator
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config, DATA_DIR, REPORTS_DIR
from generators.price_simulator import PriceSimulator, CoinPriceHistory, PricePoint

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open trading position"""
    user_id: int
    token_mint: str
    entry_price: float
    amount: float
    entry_time: datetime
    direction: str = "long"  # long or short
    
    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L"""
        if self.direction == "long":
            return (current_price - self.entry_price) / self.entry_price * self.amount
        else:
            return (self.entry_price - current_price) / self.entry_price * self.amount
    
    def unrealized_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized P&L percentage"""
        if self.direction == "long":
            return (current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - current_price) / self.entry_price


@dataclass
class BacktestTrade:
    """Record of a completed trade"""
    user_id: int
    token_mint: str
    action: str
    entry_price: float
    exit_price: float
    amount: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percent: float
    hold_duration: timedelta
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "token_mint": self.token_mint,
            "action": self.action,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "amount": self.amount,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "hold_duration_hours": self.hold_duration.total_seconds() / 3600
        }


@dataclass
class PortfolioSnapshot:
    """Portfolio state at a point in time"""
    timestamp: datetime
    cash_balance: float
    positions: List[Position]
    total_value: float
    unrealized_pnl: float
    realized_pnl: float


class Backtester:
    """
    Replays historical price data and simulates trading decisions.
    
    Features:
    - Time-series replay with configurable intervals
    - Position tracking and P&L calculation
    - Portfolio value tracking over time
    - Drawdown and risk metrics
    """
    
    def __init__(self, price_simulator: PriceSimulator = None):
        self.price_simulator = price_simulator or PriceSimulator()
        self.trades: List[BacktestTrade] = []
        self.portfolio_history: List[PortfolioSnapshot] = []
        
        # Per-user state
        self.positions: Dict[int, List[Position]] = defaultdict(list)
        self.cash: Dict[int, float] = {}
        self.realized_pnl: Dict[int, float] = defaultdict(float)
    
    def initialize_portfolios(self, users: List[Dict[str, Any]]):
        """Initialize portfolios for backtesting users"""
        for user in users:
            user_id = user.get("user_id", user.get("index"))
            initial_balance = user.get("initial_balance_nuah", 1000.0)
            self.cash[user_id] = initial_balance
            self.positions[user_id] = []
            self.realized_pnl[user_id] = 0.0
        
        logger.info(f"Initialized portfolios for {len(self.cash)} users")
    
    def get_price_at_time(self, token_mint: str, timestamp: datetime) -> Optional[float]:
        """Get price for a token at a specific time"""
        history = self.price_simulator.coin_histories.get(token_mint)
        if not history:
            return None
        
        for point in history.price_points:
            if point.timestamp >= timestamp:
                return point.price
        
        if history.price_points:
            return history.price_points[-1].price
        return None
    
    def time_iterator(
        self, 
        start_time: datetime = None,
        end_time: datetime = None,
        interval_minutes: int = 5
    ) -> Generator[datetime, None, None]:
        """Generate timestamps for backtesting"""
        if not self.price_simulator.coin_histories:
            return
        
        # Get time range from price data
        all_times = []
        for history in self.price_simulator.coin_histories.values():
            for point in history.price_points:
                all_times.append(point.timestamp)
        
        if not all_times:
            return
        
        start_time = start_time or min(all_times)
        end_time = end_time or max(all_times)
        
        current = start_time
        while current <= end_time:
            yield current
            current += timedelta(minutes=interval_minutes)
    
    def simulate_decision(
        self, 
        user_id: int, 
        timestamp: datetime,
        market_data: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate an agent decision at a point in time.
        
        This is a simplified decision model - in real testing, 
        you'd call the actual agent or a decision model.
        """
        import random
        
        # Get user's current positions
        user_positions = self.positions[user_id]
        user_cash = self.cash[user_id]
        
        # Simple momentum-based strategy
        signals = self.price_simulator.identify_signals(lookback_hours=2)
        
        bullish = [s for s in signals if s["signal"] == "BULLISH" and s["strength"] > 0.3]
        bearish = [s for s in signals if s["signal"] == "BEARISH" and s["strength"] > 0.3]
        
        # Check if we should buy
        if bullish and user_cash > 100 and random.random() < 0.3:
            signal = random.choice(bullish)
            return {
                "action": "buy",
                "token_mint": signal["denom"],
                "amount": min(user_cash * 0.2, 500),
                "confidence": signal["strength"],
                "reason": f"Bullish signal: {signal['symbol']}"
            }
        
        # Check if we should sell
        if bearish and user_positions:
            # Find position in bearish token
            for pos in user_positions:
                for signal in bearish:
                    if pos.token_mint == signal["denom"]:
                        return {
                            "action": "sell",
                            "token_mint": pos.token_mint,
                            "amount": pos.amount,
                            "confidence": signal["strength"],
                            "reason": f"Bearish signal: {signal['symbol']}"
                        }
        
        # Check stop-loss / take-profit for existing positions
        for pos in user_positions:
            current_price = market_data.get(pos.token_mint)
            if not current_price:
                continue
            
            pnl_pct = pos.unrealized_pnl_percent(current_price)
            
            # Stop loss at -10%
            if pnl_pct < -0.10:
                return {
                    "action": "sell",
                    "token_mint": pos.token_mint,
                    "amount": pos.amount,
                    "confidence": 0.9,
                    "reason": "Stop loss triggered"
                }
            
            # Take profit at +25%
            if pnl_pct > 0.25:
                return {
                    "action": "sell",
                    "token_mint": pos.token_mint,
                    "amount": pos.amount,
                    "confidence": 0.8,
                    "reason": "Take profit triggered"
                }
        
        return None  # Hold
    
    def execute_trade(
        self,
        user_id: int,
        decision: Dict[str, Any],
        timestamp: datetime,
        market_data: Dict[str, float]
    ) -> Optional[BacktestTrade]:
        """Execute a trade decision"""
        action = decision["action"]
        token_mint = decision["token_mint"]
        amount = decision["amount"]
        
        price = market_data.get(token_mint)
        if not price:
            return None
        
        if action == "buy":
            # Check if we have enough cash
            if self.cash[user_id] < amount:
                return None
            
            # Execute buy
            self.cash[user_id] -= amount
            
            # Add position
            position = Position(
                user_id=user_id,
                token_mint=token_mint,
                entry_price=price,
                amount=amount,
                entry_time=timestamp,
                direction="long"
            )
            self.positions[user_id].append(position)
            
            logger.debug(f"User {user_id} bought {token_mint} @ {price:.6f}")
            return None  # No completed trade yet
            
        elif action == "sell":
            # Find position to sell
            position_to_close = None
            for pos in self.positions[user_id]:
                if pos.token_mint == token_mint:
                    position_to_close = pos
                    break
            
            if not position_to_close:
                return None
            
            # Calculate P&L
            pnl = position_to_close.unrealized_pnl(price)
            pnl_percent = position_to_close.unrealized_pnl_percent(price)
            
            # Execute sell
            self.cash[user_id] += position_to_close.amount + pnl
            self.realized_pnl[user_id] += pnl
            
            # Remove position
            self.positions[user_id].remove(position_to_close)
            
            # Create trade record
            trade = BacktestTrade(
                user_id=user_id,
                token_mint=token_mint,
                action="close_long",
                entry_price=position_to_close.entry_price,
                exit_price=price,
                amount=position_to_close.amount,
                entry_time=position_to_close.entry_time,
                exit_time=timestamp,
                pnl=pnl,
                pnl_percent=pnl_percent,
                hold_duration=timestamp - position_to_close.entry_time
            )
            self.trades.append(trade)
            
            logger.debug(f"User {user_id} sold {token_mint} @ {price:.6f}, PnL: {pnl:.2f}")
            return trade
        
        return None
    
    def get_portfolio_value(self, user_id: int, market_data: Dict[str, float]) -> float:
        """Calculate total portfolio value"""
        total = self.cash[user_id]
        
        for pos in self.positions[user_id]:
            price = market_data.get(pos.token_mint, pos.entry_price)
            total += pos.amount + pos.unrealized_pnl(price)
        
        return total
    
    def run_backtest(
        self,
        users: List[Dict[str, Any]],
        start_time: datetime = None,
        end_time: datetime = None,
        interval_minutes: int = 15
    ) -> Dict[str, Any]:
        """
        Run the backtest simulation.
        
        Args:
            users: List of user data (should include agent users)
            start_time: Backtest start time
            end_time: Backtest end time
            interval_minutes: Decision interval
            
        Returns:
            Backtest results
        """
        # Filter to agent users only
        agent_user_ids = config.agent_test.agent_user_ids
        agent_users = [u for u in users if u.get("index") in agent_user_ids]
        
        if not agent_users:
            logger.warning("No agent users found!")
            return {}
        
        logger.info(f"Running backtest for {len(agent_users)} users...")
        
        # Initialize
        self.initialize_portfolios(agent_users)
        
        # Get all tokens
        all_tokens = list(self.price_simulator.coin_histories.keys())
        
        # Run simulation
        step = 0
        for timestamp in self.time_iterator(start_time, end_time, interval_minutes):
            # Get market data at this time
            market_data = {}
            for token in all_tokens:
                price = self.get_price_at_time(token, timestamp)
                if price:
                    market_data[token] = price
            
            # Process each user
            for user in agent_users:
                user_id = user.get("user_id", user.get("index"))
                
                # Get decision
                decision = self.simulate_decision(user_id, timestamp, market_data)
                
                if decision:
                    # Execute trade
                    self.execute_trade(user_id, decision, timestamp, market_data)
                
                # Record portfolio snapshot periodically
                if step % 12 == 0:  # Every hour (at 5-min intervals)
                    unrealized = sum(
                        pos.unrealized_pnl(market_data.get(pos.token_mint, pos.entry_price))
                        for pos in self.positions[user_id]
                    )
                    
                    snapshot = PortfolioSnapshot(
                        timestamp=timestamp,
                        cash_balance=self.cash[user_id],
                        positions=list(self.positions[user_id]),
                        total_value=self.get_portfolio_value(user_id, market_data),
                        unrealized_pnl=unrealized,
                        realized_pnl=self.realized_pnl[user_id]
                    )
                    self.portfolio_history.append(snapshot)
            
            step += 1
            
            if step % 100 == 0:
                logger.info(f"Backtest step {step}: {timestamp}")
        
        # Generate results
        return self.generate_results(agent_users)
    
    def generate_results(self, users: List[Dict]) -> Dict[str, Any]:
        """Generate backtest results summary"""
        results = {
            "total_trades": len(self.trades),
            "users": {},
            "aggregate": {}
        }
        
        # Per-user results
        for user in users:
            user_id = user.get("user_id", user.get("index"))
            user_trades = [t for t in self.trades if t.user_id == user_id]
            
            initial_balance = user.get("initial_balance_nuah", 1000.0)
            final_balance = self.cash[user_id] + sum(
                pos.amount for pos in self.positions[user_id]
            )
            
            total_pnl = self.realized_pnl[user_id]
            win_trades = [t for t in user_trades if t.pnl > 0]
            loss_trades = [t for t in user_trades if t.pnl < 0]
            
            results["users"][user_id] = {
                "initial_balance": initial_balance,
                "final_balance": round(final_balance, 2),
                "total_pnl": round(total_pnl, 2),
                "return_percent": round((final_balance - initial_balance) / initial_balance * 100, 2),
                "total_trades": len(user_trades),
                "winning_trades": len(win_trades),
                "losing_trades": len(loss_trades),
                "win_rate": len(win_trades) / len(user_trades) if user_trades else 0,
                "avg_win": sum(t.pnl for t in win_trades) / len(win_trades) if win_trades else 0,
                "avg_loss": sum(t.pnl for t in loss_trades) / len(loss_trades) if loss_trades else 0,
                "open_positions": len(self.positions[user_id])
            }
        
        # Aggregate results
        all_pnl = sum(r["total_pnl"] for r in results["users"].values())
        all_trades = sum(r["total_trades"] for r in results["users"].values())
        all_wins = sum(r["winning_trades"] for r in results["users"].values())
        
        results["aggregate"] = {
            "total_pnl": round(all_pnl, 2),
            "total_trades": all_trades,
            "win_rate": all_wins / all_trades if all_trades else 0,
            "avg_pnl_per_user": round(all_pnl / len(users), 2) if users else 0
        }
        
        # Save results
        results_file = REPORTS_DIR / f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to {results_file}")
        
        # Save trades
        trades_file = REPORTS_DIR / f"backtest_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(trades_file, 'w') as f:
            json.dump([t.to_dict() for t in self.trades], f, indent=2)
        
        return results
    
    def print_results(self, results: Dict[str, Any]):
        """Print backtest results"""
        print("\n" + "="*70)
        print("📊 BACKTEST RESULTS")
        print("="*70)
        
        print(f"\n📈 Aggregate Performance:")
        agg = results.get("aggregate", {})
        print(f"   Total P&L: ${agg.get('total_pnl', 0):.2f}")
        print(f"   Total Trades: {agg.get('total_trades', 0)}")
        print(f"   Win Rate: {agg.get('win_rate', 0)*100:.1f}%")
        print(f"   Avg P&L/User: ${agg.get('avg_pnl_per_user', 0):.2f}")
        
        print(f"\n👥 Per-User Results:")
        for user_id, user_results in results.get("users", {}).items():
            print(f"\n   User {user_id}:")
            print(f"      Initial: ${user_results['initial_balance']:.2f} → Final: ${user_results['final_balance']:.2f}")
            print(f"      Return: {user_results['return_percent']:.1f}%")
            print(f"      Trades: {user_results['total_trades']} (W: {user_results['winning_trades']}, L: {user_results['losing_trades']})")
            print(f"      Win Rate: {user_results['win_rate']*100:.1f}%")
        
        print("\n" + "="*70)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Load test data
    users_file = DATA_DIR / "generated_users.json"
    
    users = []
    if users_file.exists():
        with open(users_file, 'r') as f:
            users = json.load(f)
    
    if not users:
        print("Please generate test data first.")
        sys.exit(1)
    
    # Initialize price simulator with data
    simulator = PriceSimulator()
    simulator.load_from_file()
    
    if not simulator.coin_histories:
        print("Please run price simulation first.")
        sys.exit(1)
    
    # Run backtest
    backtester = Backtester(simulator)
    results = backtester.run_backtest(users, interval_minutes=15)
    
    # Print results
    backtester.print_results(results)

