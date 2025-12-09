"""
Performance Metrics
===================
Calculates and reports performance metrics for the trading agent.
"""

import logging
import math
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import REPORTS_DIR

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics for trading strategy evaluation.
    
    Metrics included:
    - Total P&L and return
    - Win rate and profit factor
    - Sharpe ratio (risk-adjusted return)
    - Maximum drawdown
    - Trade statistics
    """
    
    # Basic metrics
    total_pnl: float = 0.0
    total_return_percent: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # P&L metrics
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    
    # Time metrics
    avg_holding_period_hours: float = 0.0
    avg_trades_per_day: float = 0.0
    
    # Consistency metrics
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    
    @classmethod
    def calculate(
        cls,
        trades: List[Dict[str, Any]],
        initial_balance: float,
        portfolio_values: List[float] = None,
        risk_free_rate: float = 0.02
    ) -> "PerformanceMetrics":
        """
        Calculate all performance metrics from trade data.
        
        Args:
            trades: List of trade dictionaries with pnl, entry_time, exit_time
            initial_balance: Starting portfolio value
            portfolio_values: Time series of portfolio values for drawdown calculation
            risk_free_rate: Annual risk-free rate for Sharpe calculation
            
        Returns:
            PerformanceMetrics instance
        """
        metrics = cls()
        
        if not trades:
            return metrics
        
        # Basic trade statistics
        metrics.total_trades = len(trades)
        
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) < 0]
        
        metrics.winning_trades = len(wins)
        metrics.losing_trades = len(losses)
        metrics.win_rate = len(wins) / len(trades) if trades else 0
        
        # P&L calculations
        metrics.gross_profit = sum(t.get("pnl", 0) for t in wins)
        metrics.gross_loss = abs(sum(t.get("pnl", 0) for t in losses))
        
        metrics.total_pnl = metrics.gross_profit - metrics.gross_loss
        metrics.total_return_percent = (metrics.total_pnl / initial_balance * 100) if initial_balance > 0 else 0
        
        # Average metrics
        if wins:
            metrics.avg_win = metrics.gross_profit / len(wins)
            metrics.largest_win = max(t.get("pnl", 0) for t in wins)
        
        if losses:
            metrics.avg_loss = metrics.gross_loss / len(losses)
            metrics.largest_loss = min(t.get("pnl", 0) for t in losses)
        
        # Profit factor
        if metrics.gross_loss > 0:
            metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
        elif metrics.gross_profit > 0:
            metrics.profit_factor = float('inf')
        
        # Time-based metrics
        hold_times = []
        for t in trades:
            if "hold_duration_hours" in t:
                hold_times.append(t["hold_duration_hours"])
            elif "entry_time" in t and "exit_time" in t:
                try:
                    entry = datetime.fromisoformat(str(t["entry_time"]).replace("Z", "+00:00"))
                    exit_t = datetime.fromisoformat(str(t["exit_time"]).replace("Z", "+00:00"))
                    hold_times.append((exit_t - entry).total_seconds() / 3600)
                except:
                    pass
        
        if hold_times:
            metrics.avg_holding_period_hours = sum(hold_times) / len(hold_times)
        
        # Calculate Sharpe ratio
        if len(trades) > 1:
            returns = [t.get("pnl_percent", t.get("pnl", 0) / initial_balance) for t in trades]
            avg_return = sum(returns) / len(returns)
            
            # Standard deviation
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = math.sqrt(variance) if variance > 0 else 0
            
            # Annualize (assuming daily trading)
            if std_dev > 0:
                metrics.sharpe_ratio = (avg_return * 252 - risk_free_rate) / (std_dev * math.sqrt(252))
            
            # Sortino ratio (downside deviation only)
            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
                downside_dev = math.sqrt(downside_variance)
                if downside_dev > 0:
                    metrics.sortino_ratio = (avg_return * 252 - risk_free_rate) / (downside_dev * math.sqrt(252))
        
        # Maximum drawdown
        if portfolio_values and len(portfolio_values) > 1:
            metrics.max_drawdown, metrics.max_drawdown_percent = cls._calculate_max_drawdown(portfolio_values)
        else:
            # Estimate from trades
            equity_curve = [initial_balance]
            for t in trades:
                equity_curve.append(equity_curve[-1] + t.get("pnl", 0))
            metrics.max_drawdown, metrics.max_drawdown_percent = cls._calculate_max_drawdown(equity_curve)
        
        # Consecutive wins/losses
        metrics.consecutive_wins, metrics.consecutive_losses = cls._calculate_consecutive_streaks(trades)
        
        return metrics
    
    @staticmethod
    def _calculate_max_drawdown(values: List[float]) -> tuple:
        """Calculate maximum drawdown from a series of values"""
        if not values or len(values) < 2:
            return 0.0, 0.0
        
        peak = values[0]
        max_dd = 0
        max_dd_pct = 0
        
        for value in values:
            if value > peak:
                peak = value
            
            drawdown = peak - value
            drawdown_pct = drawdown / peak if peak > 0 else 0
            
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_pct = drawdown_pct
        
        return max_dd, max_dd_pct * 100
    
    @staticmethod
    def _calculate_consecutive_streaks(trades: List[Dict]) -> tuple:
        """Calculate max consecutive wins and losses"""
        if not trades:
            return 0, 0
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for t in trades:
            pnl = t.get("pnl", 0)
            
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0
        
        return max_wins, max_losses
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_pnl": round(self.total_pnl, 2),
            "total_return_percent": round(self.total_return_percent, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate * 100, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "profit_factor": round(self.profit_factor, 2) if self.profit_factor != float('inf') else "∞",
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_percent": round(self.max_drawdown_percent, 2),
            "avg_holding_period_hours": round(self.avg_holding_period_hours, 2),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses
        }
    
    def grade(self) -> str:
        """
        Grade the overall performance.
        
        Returns:
            Grade string (A+ to F)
        """
        score = 0
        
        # Win rate contribution (0-25 points)
        score += min(25, self.win_rate * 50)
        
        # Profit factor contribution (0-25 points)
        if self.profit_factor > 2:
            score += 25
        elif self.profit_factor > 1.5:
            score += 20
        elif self.profit_factor > 1.2:
            score += 15
        elif self.profit_factor > 1:
            score += 10
        elif self.profit_factor > 0.8:
            score += 5
        
        # Sharpe ratio contribution (0-25 points)
        if self.sharpe_ratio > 2:
            score += 25
        elif self.sharpe_ratio > 1.5:
            score += 20
        elif self.sharpe_ratio > 1:
            score += 15
        elif self.sharpe_ratio > 0.5:
            score += 10
        elif self.sharpe_ratio > 0:
            score += 5
        
        # Drawdown contribution (0-25 points) - lower is better
        if self.max_drawdown_percent < 5:
            score += 25
        elif self.max_drawdown_percent < 10:
            score += 20
        elif self.max_drawdown_percent < 20:
            score += 15
        elif self.max_drawdown_percent < 30:
            score += 10
        elif self.max_drawdown_percent < 50:
            score += 5
        
        # Convert to grade
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 50:
            return "C-"
        elif score >= 45:
            return "D+"
        elif score >= 40:
            return "D"
        elif score >= 35:
            return "D-"
        else:
            return "F"
    
    def print_report(self):
        """Print a formatted performance report"""
        grade = self.grade()
        
        print("\n" + "="*70)
        print(f"📊 PERFORMANCE METRICS REPORT")
        print(f"   Overall Grade: {grade}")
        print("="*70)
        
        print("\n💰 Profitability:")
        print(f"   Total P&L:         ${self.total_pnl:,.2f}")
        print(f"   Total Return:      {self.total_return_percent:,.2f}%")
        print(f"   Gross Profit:      ${self.gross_profit:,.2f}")
        print(f"   Gross Loss:        ${self.gross_loss:,.2f}")
        
        pf_str = f"{self.profit_factor:.2f}" if self.profit_factor != float('inf') else "∞"
        print(f"   Profit Factor:     {pf_str}")
        
        print("\n📈 Trade Statistics:")
        print(f"   Total Trades:      {self.total_trades}")
        print(f"   Winning Trades:    {self.winning_trades}")
        print(f"   Losing Trades:     {self.losing_trades}")
        print(f"   Win Rate:          {self.win_rate*100:.1f}%")
        print(f"   Avg Win:           ${self.avg_win:.2f}")
        print(f"   Avg Loss:          ${self.avg_loss:.2f}")
        print(f"   Largest Win:       ${self.largest_win:.2f}")
        print(f"   Largest Loss:      ${self.largest_loss:.2f}")
        
        print("\n⚡ Risk Metrics:")
        print(f"   Sharpe Ratio:      {self.sharpe_ratio:.3f}")
        print(f"   Sortino Ratio:     {self.sortino_ratio:.3f}")
        print(f"   Max Drawdown:      ${self.max_drawdown:.2f} ({self.max_drawdown_percent:.1f}%)")
        
        print("\n⏱️  Time & Consistency:")
        print(f"   Avg Hold Time:     {self.avg_holding_period_hours:.1f} hours")
        print(f"   Max Win Streak:    {self.consecutive_wins}")
        print(f"   Max Loss Streak:   {self.consecutive_losses}")
        
        print("\n" + "="*70)
        
        # Performance interpretation
        print("\n📝 Interpretation:")
        if self.sharpe_ratio > 1:
            print("   ✅ Risk-adjusted returns are good (Sharpe > 1)")
        else:
            print("   ⚠️  Risk-adjusted returns need improvement")
        
        if self.win_rate > 0.5:
            print("   ✅ Win rate is above 50%")
        else:
            print("   ⚠️  Win rate below 50% - need better entry signals")
        
        if self.profit_factor > 1.5:
            print("   ✅ Profit factor is healthy")
        else:
            print("   ⚠️  Profit factor needs improvement")
        
        if self.max_drawdown_percent < 20:
            print("   ✅ Drawdown is within acceptable range")
        else:
            print("   ⚠️  Drawdown is concerning - consider risk management")


def compare_strategies(
    strategies: Dict[str, PerformanceMetrics]
) -> str:
    """
    Compare multiple strategies and generate a comparison report.
    
    Args:
        strategies: Dict mapping strategy name to PerformanceMetrics
        
    Returns:
        Comparison report string
    """
    if not strategies:
        return "No strategies to compare."
    
    report = []
    report.append("\n" + "="*80)
    report.append("📊 STRATEGY COMPARISON")
    report.append("="*80)
    
    # Header
    header = f"{'Strategy':<20} {'Total P&L':>12} {'Return %':>10} {'Win Rate':>10} {'Sharpe':>8} {'Max DD':>10} {'Grade':>6}"
    report.append(header)
    report.append("-"*80)
    
    # Rows
    for name, metrics in strategies.items():
        row = f"{name:<20} ${metrics.total_pnl:>10,.2f} {metrics.total_return_percent:>9.1f}% {metrics.win_rate*100:>9.1f}% {metrics.sharpe_ratio:>7.2f} {metrics.max_drawdown_percent:>9.1f}% {metrics.grade():>6}"
        report.append(row)
    
    report.append("="*80)
    
    # Best performer
    best_pnl = max(strategies.items(), key=lambda x: x[1].total_pnl)
    best_sharpe = max(strategies.items(), key=lambda x: x[1].sharpe_ratio)
    
    report.append(f"\n🏆 Best by P&L: {best_pnl[0]} (${best_pnl[1].total_pnl:,.2f})")
    report.append(f"🏆 Best by Sharpe: {best_sharpe[0]} ({best_sharpe[1].sharpe_ratio:.2f})")
    
    return "\n".join(report)


if __name__ == "__main__":
    # Example usage
    sample_trades = [
        {"pnl": 50, "pnl_percent": 0.05, "hold_duration_hours": 2},
        {"pnl": -20, "pnl_percent": -0.02, "hold_duration_hours": 1},
        {"pnl": 80, "pnl_percent": 0.08, "hold_duration_hours": 4},
        {"pnl": -30, "pnl_percent": -0.03, "hold_duration_hours": 0.5},
        {"pnl": 100, "pnl_percent": 0.10, "hold_duration_hours": 6},
        {"pnl": -25, "pnl_percent": -0.025, "hold_duration_hours": 1},
        {"pnl": 60, "pnl_percent": 0.06, "hold_duration_hours": 3},
        {"pnl": 40, "pnl_percent": 0.04, "hold_duration_hours": 2},
        {"pnl": -15, "pnl_percent": -0.015, "hold_duration_hours": 0.5},
        {"pnl": 90, "pnl_percent": 0.09, "hold_duration_hours": 5},
    ]
    
    metrics = PerformanceMetrics.calculate(sample_trades, initial_balance=1000)
    metrics.print_report()

