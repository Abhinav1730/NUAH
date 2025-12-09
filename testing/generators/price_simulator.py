"""
Price Simulator
===============
Simulates realistic pump.fun-style price movements for testing the trading agent.
"""

import logging
import random
import math
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config, DATA_DIR

logger = logging.getLogger(__name__)


class PricePattern(Enum):
    """Price movement pattern types"""
    MICRO_PUMP = "micro_pump"
    MID_PUMP = "mid_pump"
    MEGA_PUMP = "mega_pump"
    ORGANIC_GROWTH = "organic_growth"
    SIDEWAYS = "sideways"
    DUMP = "dump"
    RUG_PULL = "rug_pull"
    DEAD_CAT_BOUNCE = "dead_cat_bounce"  # Pumps then dumps harder
    FOMO_SPIKE = "fomo_spike"  # Very fast pump


@dataclass
class PricePoint:
    """Single price data point"""
    timestamp: datetime
    price: float
    volume: float
    pattern: str
    price_change_pct: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "volume": self.volume,
            "pattern": self.pattern,
            "price_change_pct": self.price_change_pct
        }


@dataclass
class CoinPriceHistory:
    """Complete price history for a coin"""
    denom: str
    symbol: str
    initial_price: float
    price_points: List[PricePoint] = field(default_factory=list)
    patterns_applied: List[str] = field(default_factory=list)
    
    @property
    def current_price(self) -> float:
        if self.price_points:
            return self.price_points[-1].price
        return self.initial_price
    
    @property
    def price_change_24h(self) -> float:
        if len(self.price_points) < 2:
            return 0.0
        return (self.price_points[-1].price - self.price_points[0].price) / self.price_points[0].price
    
    def to_dict(self) -> dict:
        return {
            "denom": self.denom,
            "symbol": self.symbol,
            "initial_price": self.initial_price,
            "current_price": self.current_price,
            "price_change_24h": self.price_change_24h,
            "patterns_applied": self.patterns_applied,
            "price_points": [p.to_dict() for p in self.price_points]
        }


class PriceSimulator:
    """
    Simulates realistic cryptocurrency price movements with pump.fun-style patterns.
    
    Features:
    - Multiple price patterns (pumps, dumps, sideways, organic growth)
    - Configurable volatility and duration
    - Time-series data generation for backtesting
    - Realistic volume simulation
    """
    
    def __init__(self):
        self.config = config.price_sim
        self.coin_histories: Dict[str, CoinPriceHistory] = {}
    
    def select_pattern(self, coin_volatility: Dict[str, Any] = None) -> PricePattern:
        """
        Select a price pattern based on probabilities and coin characteristics.
        
        Args:
            coin_volatility: Coin's volatility profile
            
        Returns:
            Selected PricePattern
        """
        patterns = self.config.patterns
        
        # Adjust probabilities based on coin volatility
        weights = []
        pattern_names = []
        
        for pattern_name, pattern_config in patterns.items():
            prob = pattern_config["probability"]
            
            # Adjust for coin volatility
            if coin_volatility:
                vol_type = coin_volatility.get("type", "moderate")
                if vol_type == "stable":
                    # Stable coins more likely to be sideways, less likely to pump/dump
                    if pattern_name in ["sideways", "organic_growth"]:
                        prob *= 1.5
                    elif pattern_name in ["mega_pump", "rug_pull"]:
                        prob *= 0.3
                elif vol_type == "extreme":
                    # Extreme coins more likely to pump or dump hard
                    if pattern_name in ["mega_pump", "dump", "rug_pull"]:
                        prob *= 2.0
                    elif pattern_name == "sideways":
                        prob *= 0.5
            
            weights.append(prob)
            pattern_names.append(pattern_name)
        
        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]
        
        selected = random.choices(pattern_names, weights=weights, k=1)[0]
        return PricePattern(selected)
    
    def generate_pattern_prices(
        self,
        pattern: PricePattern,
        start_price: float,
        start_time: datetime,
        interval_minutes: int = 5
    ) -> Tuple[List[PricePoint], datetime]:
        """
        Generate price points for a specific pattern.
        
        Args:
            pattern: The price pattern to simulate
            start_price: Starting price
            start_time: Starting timestamp
            interval_minutes: Time between price points
            
        Returns:
            Tuple of (list of PricePoints, end_time)
        """
        pattern_config = self.config.patterns[pattern.value]
        
        # Get pattern parameters
        gain_min = pattern_config["gain_min"]
        gain_max = pattern_config["gain_max"]
        duration_hours = pattern_config["duration_hours"]
        
        # Calculate number of price points
        num_points = max(1, int(duration_hours * 60 / interval_minutes))
        
        # Generate target gain
        target_gain = random.uniform(gain_min, gain_max)
        target_price = start_price * (1 + target_gain)
        
        price_points = []
        current_time = start_time
        current_price = start_price
        
        for i in range(num_points):
            # Progress through the pattern (0 to 1)
            progress = (i + 1) / num_points
            
            # Calculate expected price at this point based on pattern shape
            if pattern in [PricePattern.MICRO_PUMP, PricePattern.MID_PUMP, PricePattern.MEGA_PUMP]:
                # Pump: exponential growth with momentum
                expected_price = start_price * (1 + target_gain * self._pump_curve(progress))
            elif pattern == PricePattern.FOMO_SPIKE:
                # FOMO spike: extremely fast pump (parabolic)
                expected_price = start_price * (1 + target_gain * self._fomo_curve(progress))
            elif pattern == PricePattern.ORGANIC_GROWTH:
                # Organic: smooth linear growth
                expected_price = start_price * (1 + target_gain * progress)
            elif pattern == PricePattern.SIDEWAYS:
                # Sideways: oscillation around starting price
                expected_price = start_price * (1 + target_gain * math.sin(progress * math.pi * 4))
            elif pattern == PricePattern.DUMP:
                # Dump: exponential decay
                expected_price = start_price * (1 + target_gain * self._dump_curve(progress))
            elif pattern == PricePattern.RUG_PULL:
                # Rug pull: sudden crash
                expected_price = start_price * (1 + target_gain * self._rug_curve(progress))
            elif pattern == PricePattern.DEAD_CAT_BOUNCE:
                # Dead cat bounce: pump then dump harder
                expected_price = start_price * (1 + self._dead_cat_curve(progress, target_gain))
            else:
                expected_price = start_price
            
            # Add noise/volatility
            noise = random.gauss(0, self.config.base_volatility)
            actual_price = expected_price * (1 + noise)
            actual_price = max(actual_price, start_price * 0.0001)  # Floor price
            
            # Calculate price change
            price_change = (actual_price - current_price) / current_price if current_price > 0 else 0
            
            # Generate volume (higher during fast movements - pump.fun style!)
            base_volume = random.uniform(1000, 50000)
            if pattern in [PricePattern.MEGA_PUMP, PricePattern.RUG_PULL, PricePattern.FOMO_SPIKE]:
                # Massive volume during big moves
                volume = base_volume * random.uniform(5, 20)
            elif pattern in [PricePattern.MID_PUMP, PricePattern.DUMP, PricePattern.DEAD_CAT_BOUNCE]:
                # High volume
                volume = base_volume * random.uniform(2, 8)
            elif pattern == PricePattern.MICRO_PUMP:
                # Moderate-high volume
                volume = base_volume * random.uniform(1.5, 4)
            else:
                volume = base_volume
            
            price_point = PricePoint(
                timestamp=current_time,
                price=round(actual_price, 8),
                volume=round(volume, 2),
                pattern=pattern.value,
                price_change_pct=round(price_change * 100, 2)
            )
            price_points.append(price_point)
            
            current_price = actual_price
            current_time += timedelta(minutes=interval_minutes)
        
        return price_points, current_time
    
    def _pump_curve(self, progress: float) -> float:
        """Pump curve: slow start, exponential growth, slight pullback"""
        if progress < 0.2:
            # Accumulation phase
            return progress * 0.5
        elif progress < 0.8:
            # Main pump phase
            return 0.1 + (progress - 0.2) * 1.5 ** ((progress - 0.2) * 5)
        else:
            # Slight pullback
            return 0.9 + (progress - 0.8) * 0.5
    
    def _dump_curve(self, progress: float) -> float:
        """Dump curve: sudden drop, partial recovery"""
        if progress < 0.3:
            # Main dump
            return progress * 3
        else:
            # Dead cat bounce / continued decline
            return 0.9 + (progress - 0.3) * 0.3
    
    def _rug_curve(self, progress: float) -> float:
        """Rug pull curve: everything happens at once"""
        if progress < 0.1:
            # Almost instant crash
            return progress * 9
        else:
            # Near zero, small oscillations
            return 0.95 + random.uniform(-0.03, 0.03)
    
    def _fomo_curve(self, progress: float) -> float:
        """FOMO spike: parabolic pump"""
        # Very fast rise, then slight pullback
        if progress < 0.7:
            # Parabolic rise
            return (progress / 0.7) ** 2
        else:
            # Small pullback at the top
            return 1.0 - (progress - 0.7) * 0.3
    
    def _dead_cat_curve(self, progress: float, target_gain: float) -> float:
        """Dead cat bounce: pump then dump harder"""
        # First half: pump up 30-50%
        if progress < 0.4:
            pump_gain = 0.4  # Temporary 40% gain
            return pump_gain * (progress / 0.4)
        elif progress < 0.5:
            # Brief plateau at top
            return 0.4 + random.uniform(-0.02, 0.02)
        else:
            # Dump phase: crash below starting price
            dump_progress = (progress - 0.5) / 0.5
            return 0.4 - (0.4 - target_gain) * dump_progress
    
    def simulate_coin(
        self,
        coin: Dict[str, Any],
        duration_hours: int = None,
        interval_minutes: int = None,
        start_time: datetime = None
    ) -> CoinPriceHistory:
        """
        Simulate price history for a single coin.
        
        Args:
            coin: Coin data dictionary
            duration_hours: Total simulation duration
            interval_minutes: Time between price points
            start_time: Starting timestamp
            
        Returns:
            CoinPriceHistory with simulated data
        """
        duration_hours = duration_hours or self.config.simulation_duration_hours
        interval_minutes = interval_minutes or self.config.time_interval_minutes
        start_time = start_time or datetime.now(timezone.utc) - timedelta(hours=duration_hours)
        
        denom = coin["denom"]
        symbol = coin["symbol"]
        initial_price = coin.get("initial_price", 0.001)
        volatility = coin.get("volatility_profile", {"type": "moderate"})
        
        history = CoinPriceHistory(
            denom=denom,
            symbol=symbol,
            initial_price=initial_price
        )
        
        current_time = start_time
        current_price = initial_price
        end_time = start_time + timedelta(hours=duration_hours)
        
        while current_time < end_time:
            # Select a pattern for this segment
            pattern = self.select_pattern(volatility)
            history.patterns_applied.append(pattern.value)
            
            # Generate price points for this pattern
            points, new_time = self.generate_pattern_prices(
                pattern=pattern,
                start_price=current_price,
                start_time=current_time,
                interval_minutes=interval_minutes
            )
            
            history.price_points.extend(points)
            current_time = new_time
            
            if points:
                current_price = points[-1].price
        
        self.coin_histories[denom] = history
        return history
    
    def simulate_all_coins(
        self,
        coins: List[Dict[str, Any]],
        duration_hours: int = None,
        interval_minutes: int = None,
        save_to_file: bool = True
    ) -> Dict[str, CoinPriceHistory]:
        """
        Simulate price history for all coins.
        
        Args:
            coins: List of coin data
            duration_hours: Simulation duration
            interval_minutes: Time between points
            save_to_file: Whether to save results
            
        Returns:
            Dictionary of coin histories
        """
        logger.info(f"Simulating prices for {len(coins)} coins over {duration_hours or self.config.simulation_duration_hours}h...")
        
        start_time = datetime.now(timezone.utc) - timedelta(hours=duration_hours or self.config.simulation_duration_hours)
        
        for i, coin in enumerate(coins):
            self.simulate_coin(
                coin=coin,
                duration_hours=duration_hours,
                interval_minutes=interval_minutes,
                start_time=start_time
            )
            
            if (i + 1) % 25 == 0:
                logger.info(f"Simulated {i + 1}/{len(coins)} coins")
        
        if save_to_file:
            self._save_to_file()
        
        logger.info(f"✅ Simulated price data for {len(self.coin_histories)} coins")
        return self.coin_histories
    
    def _save_to_file(self):
        """Save simulation results to files"""
        # Save full histories
        histories_file = DATA_DIR / "price_histories.json"
        data = {denom: history.to_dict() for denom, history in self.coin_histories.items()}
        with open(histories_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved price histories to {histories_file}")
        
        # Save time series CSV for easy analysis
        self._save_time_series_csv()
    
    def _save_time_series_csv(self):
        """Save time series data as CSV for agent consumption"""
        csv_file = DATA_DIR / "time_series.csv"
        
        rows = []
        for denom, history in self.coin_histories.items():
            for point in history.price_points:
                rows.append({
                    "timestamp": point.timestamp.isoformat(),
                    "denom": denom,
                    "symbol": history.symbol,
                    "price": point.price,
                    "volume": point.volume,
                    "pattern": point.pattern,
                    "price_change_pct": point.price_change_pct
                })
        
        # Sort by timestamp
        rows.sort(key=lambda x: x["timestamp"])
        
        # Write CSV
        import csv
        with open(csv_file, 'w', newline='') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        
        logger.info(f"Saved time series CSV to {csv_file} ({len(rows)} rows)")
    
    def load_from_file(self) -> Dict[str, CoinPriceHistory]:
        """Load previously simulated price data"""
        histories_file = DATA_DIR / "price_histories.json"
        
        if histories_file.exists():
            with open(histories_file, 'r') as f:
                data = json.load(f)
            
            for denom, hist_data in data.items():
                history = CoinPriceHistory(
                    denom=hist_data["denom"],
                    symbol=hist_data["symbol"],
                    initial_price=hist_data["initial_price"],
                    patterns_applied=hist_data.get("patterns_applied", [])
                )
                
                for pp in hist_data.get("price_points", []):
                    history.price_points.append(PricePoint(
                        timestamp=datetime.fromisoformat(pp["timestamp"]),
                        price=pp["price"],
                        volume=pp["volume"],
                        pattern=pp["pattern"],
                        price_change_pct=pp.get("price_change_pct", 0)
                    ))
                
                self.coin_histories[denom] = history
        
        return self.coin_histories
    
    def get_price_at_time(self, denom: str, timestamp: datetime) -> Optional[float]:
        """Get price for a coin at a specific time"""
        history = self.coin_histories.get(denom)
        if not history or not history.price_points:
            return None
        
        # Find closest price point
        for i, point in enumerate(history.price_points):
            if point.timestamp >= timestamp:
                return point.price
        
        return history.price_points[-1].price
    
    def get_market_snapshot(self, timestamp: datetime = None) -> List[Dict[str, Any]]:
        """
        Get market snapshot at a specific time.
        
        Args:
            timestamp: Time for snapshot (default: latest)
            
        Returns:
            List of market data entries
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        
        snapshot = []
        for denom, history in self.coin_histories.items():
            price = self.get_price_at_time(denom, timestamp)
            if price:
                snapshot.append({
                    "denom": denom,
                    "symbol": history.symbol,
                    "price": price,
                    "price_change_24h": history.price_change_24h,
                    "volume_24h": sum(p.volume for p in history.price_points[-288:]),  # Last 24h
                    "timestamp": timestamp.isoformat()
                })
        
        return snapshot
    
    def identify_signals(self, lookback_hours: int = 4) -> List[Dict[str, Any]]:
        """
        Identify trading signals based on recent price action.
        
        Args:
            lookback_hours: Hours to look back for patterns
            
        Returns:
            List of signal dictionaries
        """
        signals = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        for denom, history in self.coin_histories.items():
            recent_points = [p for p in history.price_points if p.timestamp >= cutoff]
            
            if len(recent_points) < 2:
                continue
            
            # Calculate metrics
            start_price = recent_points[0].price
            end_price = recent_points[-1].price
            change = (end_price - start_price) / start_price
            
            # Check for pump signal
            if change > 0.1:  # >10% gain
                signals.append({
                    "denom": denom,
                    "symbol": history.symbol,
                    "signal": "BULLISH",
                    "strength": min(change / 0.5, 1.0),  # Normalize to 0-1
                    "price_change": change,
                    "pattern": recent_points[-1].pattern,
                    "timestamp": recent_points[-1].timestamp.isoformat()
                })
            # Check for dump signal
            elif change < -0.1:  # >10% loss
                signals.append({
                    "denom": denom,
                    "symbol": history.symbol,
                    "signal": "BEARISH",
                    "strength": min(abs(change) / 0.5, 1.0),
                    "price_change": change,
                    "pattern": recent_points[-1].pattern,
                    "timestamp": recent_points[-1].timestamp.isoformat()
                })
        
        return signals


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Load coins
    coins_file = DATA_DIR / "generated_coins.json"
    if coins_file.exists():
        with open(coins_file, 'r') as f:
            coins = json.load(f)
    else:
        # Generate sample coins for testing
        coins = [
            {"denom": f"factory/test/MEME{i}", "symbol": f"MEME{i}", "initial_price": 0.001, "volatility_profile": {"type": "volatile"}}
            for i in range(10)
        ]
    
    # Simulate prices
    simulator = PriceSimulator()
    histories = simulator.simulate_all_coins(coins[:10], duration_hours=24, save_to_file=True)
    
    # Print summary
    print("\n📈 Price Simulation Summary:")
    for denom, history in list(histories.items())[:5]:
        print(f"  • {history.symbol}:")
        print(f"    Initial: ${history.initial_price:.6f} → Current: ${history.current_price:.6f}")
        print(f"    24h Change: {history.price_change_24h * 100:.2f}%")
        print(f"    Patterns: {', '.join(set(history.patterns_applied))}")

