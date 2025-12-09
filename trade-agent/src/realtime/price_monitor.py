"""
Real-Time Price Monitor
=======================
Tracks prices with sub-minute granularity for fast pattern detection.

On pump.fun, prices can change 100%+ in minutes. This monitor:
- Polls prices every 5-15 seconds
- Maintains rolling price history
- Calculates real-time momentum and volatility
- Triggers alerts on significant moves
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set
from pathlib import Path
import sys

# Add shared path
_shared_path = Path(__file__).parent.parent.parent.parent / "shared"
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))

try:
    from nuahchain_client import NuahChainClient
except ImportError:
    NuahChainClient = None

logger = logging.getLogger(__name__)


@dataclass
class PriceUpdate:
    """Single price data point"""
    token_mint: str
    price: float
    volume: float
    timestamp: datetime
    price_change_1m: float = 0.0  # 1-minute change
    price_change_5m: float = 0.0  # 5-minute change
    volume_spike: float = 1.0     # Volume vs average (1.0 = normal)
    momentum: float = 0.0         # Rate of change
    
    def to_dict(self) -> dict:
        return {
            "token_mint": self.token_mint,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "price_change_1m": self.price_change_1m,
            "price_change_5m": self.price_change_5m,
            "volume_spike": self.volume_spike,
            "momentum": self.momentum,
        }


@dataclass
class TokenPriceHistory:
    """Rolling price history for a token"""
    token_mint: str
    max_history: int = 60  # Keep last 60 data points (5 min at 5s intervals)
    
    prices: deque = field(default_factory=lambda: deque(maxlen=60))
    volumes: deque = field(default_factory=lambda: deque(maxlen=60))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=60))
    
    def add(self, price: float, volume: float, timestamp: datetime):
        """Add a new price point"""
        self.prices.append(price)
        self.volumes.append(volume)
        self.timestamps.append(timestamp)
    
    @property
    def current_price(self) -> float:
        return self.prices[-1] if self.prices else 0.0
    
    @property
    def price_1m_ago(self) -> float:
        """Price approximately 1 minute ago (12 data points at 5s intervals)"""
        if len(self.prices) >= 12:
            return self.prices[-12]
        return self.prices[0] if self.prices else 0.0
    
    @property
    def price_5m_ago(self) -> float:
        """Price approximately 5 minutes ago"""
        if len(self.prices) >= 60:
            return self.prices[-60]
        return self.prices[0] if self.prices else 0.0
    
    @property
    def price_change_1m(self) -> float:
        """Percentage change in last 1 minute"""
        old_price = self.price_1m_ago
        if old_price <= 0:
            return 0.0
        return (self.current_price - old_price) / old_price
    
    @property
    def price_change_5m(self) -> float:
        """Percentage change in last 5 minutes"""
        old_price = self.price_5m_ago
        if old_price <= 0:
            return 0.0
        return (self.current_price - old_price) / old_price
    
    @property
    def avg_volume(self) -> float:
        """Average volume over history"""
        if not self.volumes:
            return 0.0
        return sum(self.volumes) / len(self.volumes)
    
    @property
    def current_volume(self) -> float:
        return self.volumes[-1] if self.volumes else 0.0
    
    @property
    def volume_spike(self) -> float:
        """Current volume vs average (>1 means higher than normal)"""
        avg = self.avg_volume
        if avg <= 0:
            return 1.0
        return self.current_volume / avg
    
    @property
    def momentum(self) -> float:
        """
        Rate of price change (derivative).
        Positive = accelerating up, Negative = accelerating down
        """
        if len(self.prices) < 3:
            return 0.0
        
        # Calculate velocity (first derivative)
        recent_changes = []
        for i in range(-3, 0):
            if len(self.prices) > abs(i):
                prev = self.prices[i - 1] if abs(i - 1) < len(self.prices) else self.prices[0]
                curr = self.prices[i]
                if prev > 0:
                    recent_changes.append((curr - prev) / prev)
        
        if not recent_changes:
            return 0.0
        
        # Average recent velocity
        return sum(recent_changes) / len(recent_changes)
    
    @property
    def volatility(self) -> float:
        """Standard deviation of recent price changes"""
        if len(self.prices) < 5:
            return 0.0
        
        changes = []
        for i in range(1, min(20, len(self.prices))):
            if self.prices[i - 1] > 0:
                change = (self.prices[i] - self.prices[i - 1]) / self.prices[i - 1]
                changes.append(change)
        
        if not changes:
            return 0.0
        
        mean = sum(changes) / len(changes)
        variance = sum((c - mean) ** 2 for c in changes) / len(changes)
        return variance ** 0.5


# Type alias for price update callbacks
PriceCallback = Callable[[PriceUpdate], None]


class PriceMonitor:
    """
    Real-time price monitoring service.
    
    Features:
    - Polls prices every N seconds (default: 5)
    - Maintains rolling history per token
    - Calculates momentum and volume spikes
    - Triggers callbacks on significant moves
    """
    
    def __init__(
        self,
        api_base_url: str = "http://localhost:8080",
        api_token: Optional[str] = None,
        poll_interval_seconds: float = 5.0,
        alert_threshold_1m: float = 0.05,  # 5% move in 1 min triggers alert
        alert_threshold_5m: float = 0.15,  # 15% move in 5 min triggers alert
        volume_spike_threshold: float = 3.0,  # 3x normal volume triggers alert
    ):
        self.api_base_url = api_base_url
        self.api_token = api_token
        self.poll_interval = poll_interval_seconds
        self.alert_threshold_1m = alert_threshold_1m
        self.alert_threshold_5m = alert_threshold_5m
        self.volume_spike_threshold = volume_spike_threshold
        
        # State
        self.histories: Dict[str, TokenPriceHistory] = {}
        self.watched_tokens: Set[str] = set()
        self.callbacks: List[PriceCallback] = []
        self._running = False
        self._client: Optional[NuahChainClient] = None
        
        # Initialize client
        if NuahChainClient:
            self._client = NuahChainClient(
                base_url=api_base_url,
                api_token=api_token,
                timeout=10
            )
    
    def watch(self, token_mint: str):
        """Add a token to the watch list"""
        self.watched_tokens.add(token_mint)
        if token_mint not in self.histories:
            self.histories[token_mint] = TokenPriceHistory(token_mint=token_mint)
        logger.info(f"Now watching token: {token_mint}")
    
    def unwatch(self, token_mint: str):
        """Remove a token from the watch list"""
        self.watched_tokens.discard(token_mint)
        logger.info(f"Stopped watching token: {token_mint}")
    
    def watch_all(self, token_mints: List[str]):
        """Watch multiple tokens"""
        for token in token_mints:
            self.watch(token)
    
    def on_price_update(self, callback: PriceCallback):
        """Register a callback for price updates"""
        self.callbacks.append(callback)
    
    def get_latest(self, token_mint: str) -> Optional[PriceUpdate]:
        """Get latest price update for a token"""
        history = self.histories.get(token_mint)
        if not history or not history.prices:
            return None
        
        return PriceUpdate(
            token_mint=token_mint,
            price=history.current_price,
            volume=history.current_volume,
            timestamp=history.timestamps[-1] if history.timestamps else datetime.now(timezone.utc),
            price_change_1m=history.price_change_1m,
            price_change_5m=history.price_change_5m,
            volume_spike=history.volume_spike,
            momentum=history.momentum,
        )
    
    def get_all_latest(self) -> List[PriceUpdate]:
        """Get latest updates for all watched tokens"""
        updates = []
        for token in self.watched_tokens:
            update = self.get_latest(token)
            if update:
                updates.append(update)
        return updates
    
    async def _fetch_prices(self) -> Dict[str, Dict]:
        """Fetch current prices from API"""
        if not self._client:
            return {}
        
        try:
            # Get marketplace data
            tokens = self._client.get_marketplace_tokens(limit=200)
            
            prices = {}
            for token in tokens:
                denom = token.get("denom") or token.get("token_mint")
                if denom:
                    prices[denom] = {
                        "price": float(token.get("price_ndollar") or token.get("price") or 0),
                        "volume": float(token.get("volume_24h") or token.get("volume") or 0),
                    }
            return prices
            
        except Exception as e:
            logger.error(f"Failed to fetch prices: {e}")
            return {}
    
    def _process_price(self, token_mint: str, price: float, volume: float) -> Optional[PriceUpdate]:
        """Process a new price point and check for alerts"""
        now = datetime.now(timezone.utc)
        
        # Get or create history
        if token_mint not in self.histories:
            self.histories[token_mint] = TokenPriceHistory(token_mint=token_mint)
        
        history = self.histories[token_mint]
        history.add(price, volume, now)
        
        # Create update
        update = PriceUpdate(
            token_mint=token_mint,
            price=price,
            volume=volume,
            timestamp=now,
            price_change_1m=history.price_change_1m,
            price_change_5m=history.price_change_5m,
            volume_spike=history.volume_spike,
            momentum=history.momentum,
        )
        
        # Check if this is an alert-worthy update
        is_alert = (
            abs(update.price_change_1m) >= self.alert_threshold_1m or
            abs(update.price_change_5m) >= self.alert_threshold_5m or
            update.volume_spike >= self.volume_spike_threshold
        )
        
        if is_alert:
            logger.warning(
                f"🚨 ALERT {token_mint}: 1m={update.price_change_1m*100:.1f}%, "
                f"5m={update.price_change_5m*100:.1f}%, vol_spike={update.volume_spike:.1f}x"
            )
        
        return update
    
    async def _poll_loop(self):
        """Main polling loop"""
        logger.info(f"Price monitor started (interval: {self.poll_interval}s)")
        
        while self._running:
            start = time.time()
            
            try:
                # Fetch all prices
                prices = await self._fetch_prices()
                
                # Process watched tokens
                for token_mint in self.watched_tokens:
                    if token_mint in prices:
                        data = prices[token_mint]
                        update = self._process_price(
                            token_mint,
                            data["price"],
                            data["volume"]
                        )
                        
                        if update:
                            # Trigger callbacks
                            for callback in self.callbacks:
                                try:
                                    callback(update)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")
                
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
            
            # Sleep for remaining interval
            elapsed = time.time() - start
            sleep_time = max(0, self.poll_interval - elapsed)
            await asyncio.sleep(sleep_time)
    
    async def start(self):
        """Start the price monitor"""
        if self._running:
            return
        
        self._running = True
        await self._poll_loop()
    
    def stop(self):
        """Stop the price monitor"""
        self._running = False
        logger.info("Price monitor stopped")
    
    def run_sync(self, duration_seconds: float = None):
        """Run synchronously for a specified duration (for testing)"""
        async def _run():
            self._running = True
            start = time.time()
            
            while self._running:
                if duration_seconds and (time.time() - start) >= duration_seconds:
                    break
                
                prices = await self._fetch_prices()
                
                for token_mint in self.watched_tokens:
                    if token_mint in prices:
                        data = prices[token_mint]
                        update = self._process_price(
                            token_mint,
                            data["price"],
                            data["volume"]
                        )
                        
                        if update:
                            for callback in self.callbacks:
                                try:
                                    callback(update)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")
                
                await asyncio.sleep(self.poll_interval)
        
        asyncio.run(_run())


# Synchronous wrapper for non-async contexts
class SyncPriceMonitor:
    """Synchronous wrapper for PriceMonitor"""
    
    def __init__(self, **kwargs):
        self.monitor = PriceMonitor(**kwargs)
    
    def fetch_once(self) -> List[PriceUpdate]:
        """Fetch prices once and return updates"""
        async def _fetch():
            prices = await self.monitor._fetch_prices()
            updates = []
            
            for token_mint in self.monitor.watched_tokens:
                if token_mint in prices:
                    data = prices[token_mint]
                    update = self.monitor._process_price(
                        token_mint,
                        data["price"],
                        data["volume"]
                    )
                    if update:
                        updates.append(update)
            
            return updates
        
        return asyncio.run(_fetch())
    
    def watch(self, token_mint: str):
        self.monitor.watch(token_mint)
    
    def watch_all(self, tokens: List[str]):
        self.monitor.watch_all(tokens)
    
    def get_latest(self, token_mint: str) -> Optional[PriceUpdate]:
        return self.monitor.get_latest(token_mint)
    
    def get_all_latest(self) -> List[PriceUpdate]:
        return self.monitor.get_all_latest()

