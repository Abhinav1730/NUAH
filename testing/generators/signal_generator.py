"""
Signal Generator
================
Generates news_signals, trend_signals, and rule_evaluations CSVs
for testing the trade-agent with realistic agent outputs.
"""

import csv
import json
import logging
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config, DATA_DIR

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Generates mock signals that mimic output from news-agent, trend-agent, and rules-agent.
    
    This allows testing the trade-agent without running the full analysis pipeline.
    """
    
    def __init__(self):
        self.data_dir = DATA_DIR
    
    def generate_news_signals(
        self,
        coins: List[Dict],
        num_signals: int = None
    ) -> List[Dict]:
        """
        Generate mock news signals for testing.
        
        Args:
            coins: List of coin data
            num_signals: Number of signals to generate (default: 30% of coins)
            
        Returns:
            List of news signal dictionaries
        """
        num_signals = num_signals or max(10, int(len(coins) * 0.3))
        
        catalysts = ["pump_detected", "fomo_wave", "whale_entry", "community_hype", "none"]
        urgencies = ["critical", "high", "medium", "low"]
        
        signals = []
        selected_coins = random.sample(coins, min(num_signals, len(coins)))
        
        for idx, coin in enumerate(selected_coins, start=1):
            # Determine sentiment based on coin's volatility
            vol_type = coin.get("volatility_profile", {}).get("type", "moderate")
            
            if vol_type == "extreme":
                sentiment = random.uniform(0.3, 0.95)  # More likely positive
                catalyst = random.choice(["pump_detected", "fomo_wave", "whale_entry"])
                urgency = random.choice(["critical", "high"])
            elif vol_type == "stable":
                sentiment = random.uniform(-0.3, 0.5)
                catalyst = random.choice(["community_hype", "none"])
                urgency = random.choice(["medium", "low"])
            else:
                sentiment = random.uniform(-0.5, 0.8)
                catalyst = random.choice(catalysts)
                urgency = random.choice(urgencies)
            
            signal = {
                "signal_id": f"NEWS-{idx:04d}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "token_mint": coin["denom"],
                "headline": f"Analysis for {coin['symbol']}",
                "sentiment_score": round(sentiment, 3),
                "confidence": round(random.uniform(0.5, 0.95), 3),
                "catalyst": catalyst,
                "urgency": urgency,
                "source": "test_generator",
                "summary": f"Generated signal for {coin['symbol']} - {catalyst}"
            }
            signals.append(signal)
        
        # Save to CSV
        self._save_news_signals(signals)
        logger.info(f"Generated {len(signals)} news signals")
        
        return signals
    
    def generate_trend_signals(
        self,
        coins: List[Dict],
        price_histories: Dict = None
    ) -> List[Dict]:
        """
        Generate mock trend signals for testing.
        
        Args:
            coins: List of coin data
            price_histories: Optional price history data for realistic signals
            
        Returns:
            List of trend signal dictionaries
        """
        stages = ["early", "mid", "late", "graduated"]
        volatility_flags = ["high", "moderate", "low"]
        liquidity_flags = ["thin", "healthy", "deep"]
        risk_levels = ["low", "medium", "high", "extreme"]
        
        signals = []
        
        for idx, coin in enumerate(coins, start=1):
            vol_type = coin.get("volatility_profile", {}).get("type", "moderate")
            
            # Determine bonding curve stage
            if random.random() < 0.4:
                stage = "early"
            elif random.random() < 0.7:
                stage = "mid"
            elif random.random() < 0.9:
                stage = "late"
            else:
                stage = "graduated"
            
            # Calculate trend score based on volatility type
            if vol_type == "extreme":
                trend_score = random.uniform(0.3, 0.9)
                rug_risk = random.uniform(0.3, 0.8)
                volatility = "high"
            elif vol_type == "stable":
                trend_score = random.uniform(-0.2, 0.4)
                rug_risk = random.uniform(0.05, 0.3)
                volatility = "low"
            else:
                trend_score = random.uniform(-0.3, 0.6)
                rug_risk = random.uniform(0.1, 0.5)
                volatility = "moderate"
            
            # Adjust rug risk for early stage tokens
            if stage == "early":
                rug_risk = min(rug_risk * 1.5, 0.9)
            
            signal = {
                "signal_id": f"TREND-{idx:04d}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "token_mint": coin["denom"],
                "trend_score": round(trend_score, 3),
                "stage": stage,
                "volatility_flag": volatility,
                "liquidity_flag": random.choice(liquidity_flags),
                "risk_level": self._risk_level_from_score(rug_risk),
                "rug_risk": round(rug_risk, 3),
                "confidence": round(random.uniform(0.5, 0.9), 3),
                "summary": f"{coin['symbol']} is in {stage} stage with {volatility} volatility"
            }
            signals.append(signal)
        
        # Save to CSV
        self._save_trend_signals(signals)
        logger.info(f"Generated {len(signals)} trend signals")
        
        return signals
    
    def generate_rule_evaluations(
        self,
        users: List[Dict],
        coins: List[Dict],
        agent_user_ids: List[int] = None
    ) -> List[Dict]:
        """
        Generate mock rule evaluations for testing.
        
        Args:
            users: List of user data
            coins: List of coin data
            agent_user_ids: List of user IDs the agent trades for
            
        Returns:
            List of rule evaluation dictionaries
        """
        agent_user_ids = agent_user_ids or config.users.agent_user_ids
        
        evaluations = []
        idx = 0
        
        for user in users:
            user_index = user.get("index", user.get("user_id", 0))
            
            # Only generate for agent users
            if user_index not in agent_user_ids:
                continue
            
            user_id = user.get("user_id", user_index)
            prefs = user.get("preferences", {})
            risk_profile = prefs.get("risk_profile", "balanced")
            
            # Determine limits based on risk profile
            if risk_profile == "aggressive":
                max_trades = 20
                max_position = 2000
            elif risk_profile == "conservative":
                max_trades = 5
                max_position = 500
            else:
                max_trades = 10
                max_position = 1000
            
            # Generate evaluations for a subset of coins
            user_coins = random.sample(coins, min(30, len(coins)))
            
            for coin in user_coins:
                idx += 1
                
                # Determine if allowed based on rug risk
                rug_risk = random.uniform(0.1, 0.7)
                allowed = rug_risk < 0.7  # Block high rug risk
                
                # Adjust position for risk
                adjusted_position = max_position
                if rug_risk > 0.4:
                    adjusted_position = max_position * (1 - rug_risk)
                
                evaluation = {
                    "evaluation_id": f"RULE-{user_id}-{idx:04d}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "user_id": user_id,
                    "token_mint": coin["denom"],
                    "allowed": 1 if allowed else 0,
                    "max_daily_trades": max_trades,
                    "max_position_ndollar": round(adjusted_position, 2),
                    "rug_risk_assessment": self._risk_level_from_score(rug_risk),
                    "reason": "allowed" if allowed else f"blocked: rug_risk={rug_risk:.2f}",
                    "confidence": round(random.uniform(0.6, 0.9), 3),
                    "emergency_exit_enabled": 1 if rug_risk > 0.3 else 0
                }
                evaluations.append(evaluation)
        
        # Save to CSV
        self._save_rule_evaluations(evaluations)
        logger.info(f"Generated {len(evaluations)} rule evaluations")
        
        return evaluations
    
    def generate_all_signals(
        self,
        coins: List[Dict],
        users: List[Dict],
        price_histories: Dict = None
    ) -> Dict[str, List[Dict]]:
        """
        Generate all signal types at once.
        
        Args:
            coins: List of coin data
            users: List of user data
            price_histories: Optional price history data
            
        Returns:
            Dictionary with all signal types
        """
        logger.info("Generating all agent signals...")
        
        return {
            "news_signals": self.generate_news_signals(coins),
            "trend_signals": self.generate_trend_signals(coins, price_histories),
            "rule_evaluations": self.generate_rule_evaluations(users, coins)
        }
    
    def _risk_level_from_score(self, score: float) -> str:
        """Convert numeric risk score to level string."""
        if score < 0.2:
            return "low"
        elif score < 0.5:
            return "medium"
        elif score < 0.7:
            return "high"
        else:
            return "extreme"
    
    def _save_news_signals(self, signals: List[Dict]) -> None:
        """Save news signals to CSV."""
        path = self.data_dir / "news_signals.csv"
        
        fields = [
            "signal_id", "timestamp", "token_mint", "headline",
            "sentiment_score", "confidence", "catalyst", "urgency",
            "source", "summary"
        ]
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for signal in signals:
                row = {k: signal.get(k, "") for k in fields}
                writer.writerow(row)
        
        logger.info(f"Saved news signals to {path}")
    
    def _save_trend_signals(self, signals: List[Dict]) -> None:
        """Save trend signals to CSV."""
        path = self.data_dir / "trend_signals.csv"
        
        fields = [
            "signal_id", "timestamp", "token_mint", "trend_score",
            "stage", "volatility_flag", "liquidity_flag", "risk_level",
            "rug_risk", "confidence", "summary"
        ]
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for signal in signals:
                row = {k: signal.get(k, "") for k in fields}
                writer.writerow(row)
        
        logger.info(f"Saved trend signals to {path}")
    
    def _save_rule_evaluations(self, evaluations: List[Dict]) -> None:
        """Save rule evaluations to CSV."""
        path = self.data_dir / "rule_evaluations.csv"
        
        fields = [
            "evaluation_id", "timestamp", "user_id", "token_mint",
            "allowed", "max_daily_trades", "max_position_ndollar",
            "rug_risk_assessment", "reason", "confidence", "emergency_exit_enabled"
        ]
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for evaluation in evaluations:
                row = {k: evaluation.get(k, "") for k in fields}
                writer.writerow(row)
        
        logger.info(f"Saved rule evaluations to {path}")


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
    else:
        # Generate sample coins
        coins = [
            {"denom": f"factory/test/MEME{i}", "symbol": f"MEME{i}", 
             "volatility_profile": {"type": random.choice(["stable", "moderate", "extreme"])}}
            for i in range(20)
        ]
    
    if users_file.exists():
        with open(users_file, 'r') as f:
            users = json.load(f)
    else:
        # Generate sample users
        users = [
            {"index": i, "user_id": i, "preferences": {"risk_profile": "balanced"}}
            for i in range(1, 6)
        ]
    
    # Generate signals
    generator = SignalGenerator()
    all_signals = generator.generate_all_signals(coins, users)
    
    print(f"\n✅ Generated signals:")
    print(f"   News signals: {len(all_signals['news_signals'])}")
    print(f"   Trend signals: {len(all_signals['trend_signals'])}")
    print(f"   Rule evaluations: {len(all_signals['rule_evaluations'])}")

