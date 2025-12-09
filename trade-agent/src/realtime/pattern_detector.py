"""
Pattern Detector
================
Detects pump.fun-style price patterns in real-time.

Patterns detected:
- PUMP: Rapid price increase (potential buy opportunity or exit signal)
- DUMP: Rapid price decrease (sell immediately)
- RUG_PULL: Catastrophic drop (emergency exit)
- FOMO_SPIKE: Parabolic rise (very risky, likely reversal incoming)
- DEAD_CAT_BOUNCE: False recovery (don't buy the dip)
- ACCUMULATION: Slow steady rise (good entry)
- DISTRIBUTION: Slow decline (exit)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any

from .price_monitor import PriceUpdate, TokenPriceHistory

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Types of price patterns"""
    UNKNOWN = "unknown"
    ACCUMULATION = "accumulation"      # Slow steady rise - good entry
    DISTRIBUTION = "distribution"       # Slow decline - exit
    MICRO_PUMP = "micro_pump"          # +10-30% in minutes
    MID_PUMP = "mid_pump"              # +30-100% in minutes
    MEGA_PUMP = "mega_pump"            # +100%+ - very risky
    FOMO_SPIKE = "fomo_spike"          # Parabolic, likely to crash
    DUMP = "dump"                      # -20-50% rapid drop
    RUG_PULL = "rug_pull"              # -80%+ catastrophic
    DEAD_CAT_BOUNCE = "dead_cat_bounce"  # False recovery
    SIDEWAYS = "sideways"              # No clear direction


class SignalStrength(Enum):
    """Signal urgency level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"  # Act immediately


@dataclass
class PatternSignal:
    """Detected pattern signal"""
    token_mint: str
    pattern: PatternType
    strength: SignalStrength
    confidence: float  # 0.0 to 1.0
    action: str  # "buy", "sell", "hold", "emergency_exit"
    timestamp: datetime
    
    # Price data at detection
    current_price: float
    price_change_1m: float
    price_change_5m: float
    volume_spike: float
    momentum: float
    
    # Risk assessment
    risk_level: str  # "low", "medium", "high", "extreme"
    stop_loss_suggested: Optional[float] = None
    take_profit_suggested: Optional[float] = None
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_mint": self.token_mint,
            "pattern": self.pattern.value,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "price_change_1m": self.price_change_1m,
            "price_change_5m": self.price_change_5m,
            "volume_spike": self.volume_spike,
            "momentum": self.momentum,
            "risk_level": self.risk_level,
            "stop_loss_suggested": self.stop_loss_suggested,
            "take_profit_suggested": self.take_profit_suggested,
            "reason": self.reason,
        }


class PatternDetector:
    """
    Real-time pattern detection for pump.fun-style trading.
    
    Thresholds are calibrated for fast meme coin movements:
    - 5% in 1 min = micro pump
    - 15% in 1 min = mid pump  
    - 30%+ in 1 min = mega pump / FOMO spike
    - -15% in 1 min = dump
    - -50%+ in 1 min = rug pull
    """
    
    def __init__(
        self,
        # Pump thresholds (1-minute changes)
        micro_pump_threshold: float = 0.05,    # 5%
        mid_pump_threshold: float = 0.15,      # 15%
        mega_pump_threshold: float = 0.30,     # 30%
        fomo_threshold: float = 0.50,          # 50% = likely FOMO spike
        
        # Dump thresholds
        dump_threshold: float = -0.15,         # -15%
        rug_threshold: float = -0.50,          # -50%
        
        # 5-minute thresholds (for confirmation)
        pump_5m_threshold: float = 0.25,       # 25% in 5 min
        dump_5m_threshold: float = -0.30,      # -30% in 5 min
        
        # Volume spike threshold
        volume_spike_threshold: float = 3.0,   # 3x normal
        high_volume_threshold: float = 5.0,    # 5x normal
        
        # Momentum thresholds
        strong_momentum: float = 0.02,         # Strong positive momentum
        weak_momentum: float = -0.01,          # Weakening
    ):
        self.micro_pump_threshold = micro_pump_threshold
        self.mid_pump_threshold = mid_pump_threshold
        self.mega_pump_threshold = mega_pump_threshold
        self.fomo_threshold = fomo_threshold
        self.dump_threshold = dump_threshold
        self.rug_threshold = rug_threshold
        self.pump_5m_threshold = pump_5m_threshold
        self.dump_5m_threshold = dump_5m_threshold
        self.volume_spike_threshold = volume_spike_threshold
        self.high_volume_threshold = high_volume_threshold
        self.strong_momentum = strong_momentum
        self.weak_momentum = weak_momentum
        
        # Recent patterns for dead cat bounce detection
        self._recent_patterns: Dict[str, List[PatternType]] = {}
    
    def detect(self, update: PriceUpdate) -> PatternSignal:
        """
        Detect pattern from a price update.
        
        Args:
            update: Current price update
            
        Returns:
            PatternSignal with detected pattern and action
        """
        token = update.token_mint
        change_1m = update.price_change_1m
        change_5m = update.price_change_5m
        vol_spike = update.volume_spike
        momentum = update.momentum
        
        # Initialize pattern tracking
        if token not in self._recent_patterns:
            self._recent_patterns[token] = []
        
        # Detect pattern
        pattern, strength, confidence, action, risk, reason = self._classify_pattern(
            change_1m, change_5m, vol_spike, momentum, 
            self._recent_patterns[token]
        )
        
        # Calculate suggested stop-loss and take-profit
        stop_loss, take_profit = self._calculate_levels(
            update.price, pattern, change_1m
        )
        
        # Update pattern history
        self._recent_patterns[token].append(pattern)
        if len(self._recent_patterns[token]) > 10:
            self._recent_patterns[token].pop(0)
        
        signal = PatternSignal(
            token_mint=token,
            pattern=pattern,
            strength=strength,
            confidence=confidence,
            action=action,
            timestamp=update.timestamp,
            current_price=update.price,
            price_change_1m=change_1m,
            price_change_5m=change_5m,
            volume_spike=vol_spike,
            momentum=momentum,
            risk_level=risk,
            stop_loss_suggested=stop_loss,
            take_profit_suggested=take_profit,
            reason=reason,
        )
        
        # Log significant patterns
        if pattern not in [PatternType.UNKNOWN, PatternType.SIDEWAYS]:
            logger.info(
                f"📊 Pattern detected: {token} = {pattern.value} "
                f"(action={action}, confidence={confidence:.2f})"
            )
        
        return signal
    
    def _classify_pattern(
        self,
        change_1m: float,
        change_5m: float,
        vol_spike: float,
        momentum: float,
        recent_patterns: List[PatternType]
    ) -> tuple:
        """
        Classify the pattern based on metrics.
        
        Returns:
            (pattern, strength, confidence, action, risk_level, reason)
        """
        
        # ========================
        # EMERGENCY: RUG PULL
        # ========================
        if change_1m <= self.rug_threshold:
            return (
                PatternType.RUG_PULL,
                SignalStrength.CRITICAL,
                0.95,
                "emergency_exit",
                "extreme",
                f"CRITICAL: Price crashed {change_1m*100:.1f}% in 1 min - likely rug pull!"
            )
        
        # ========================
        # DUMP DETECTION
        # ========================
        if change_1m <= self.dump_threshold:
            # Check if this is after a pump (dead cat bounce setup)
            if PatternType.MEGA_PUMP in recent_patterns or PatternType.MID_PUMP in recent_patterns:
                return (
                    PatternType.DUMP,
                    SignalStrength.HIGH,
                    0.85,
                    "sell",
                    "high",
                    f"Dump detected after pump: {change_1m*100:.1f}% drop - profit taking/exit"
                )
            
            return (
                PatternType.DUMP,
                SignalStrength.HIGH,
                0.80,
                "sell",
                "high",
                f"Rapid dump: {change_1m*100:.1f}% in 1 min"
            )
        
        # ========================
        # FOMO SPIKE (Dangerous!)
        # ========================
        if change_1m >= self.fomo_threshold:
            return (
                PatternType.FOMO_SPIKE,
                SignalStrength.HIGH,
                0.75,
                "hold",  # Don't chase! Too risky
                "extreme",
                f"FOMO spike: {change_1m*100:.1f}% in 1 min - DO NOT CHASE, reversal likely!"
            )
        
        # ========================
        # MEGA PUMP
        # ========================
        if change_1m >= self.mega_pump_threshold:
            # High volume confirms the pump
            if vol_spike >= self.high_volume_threshold:
                return (
                    PatternType.MEGA_PUMP,
                    SignalStrength.HIGH,
                    0.80,
                    "sell" if momentum < 0 else "hold",
                    "high",
                    f"Mega pump: {change_1m*100:.1f}% with {vol_spike:.1f}x volume"
                )
            return (
                PatternType.MEGA_PUMP,
                SignalStrength.MEDIUM,
                0.70,
                "hold",
                "high",
                f"Mega pump: {change_1m*100:.1f}% - watching for reversal"
            )
        
        # ========================
        # MID PUMP
        # ========================
        if change_1m >= self.mid_pump_threshold:
            if momentum >= self.strong_momentum:
                return (
                    PatternType.MID_PUMP,
                    SignalStrength.MEDIUM,
                    0.75,
                    "buy" if change_5m < self.pump_5m_threshold else "hold",
                    "medium",
                    f"Mid pump: {change_1m*100:.1f}% with strong momentum"
                )
            return (
                PatternType.MID_PUMP,
                SignalStrength.LOW,
                0.65,
                "hold",
                "medium",
                f"Mid pump: {change_1m*100:.1f}% - momentum weakening"
            )
        
        # ========================
        # MICRO PUMP (Good entry?)
        # ========================
        if change_1m >= self.micro_pump_threshold:
            # Check for volume confirmation
            if vol_spike >= self.volume_spike_threshold:
                return (
                    PatternType.MICRO_PUMP,
                    SignalStrength.MEDIUM,
                    0.70,
                    "buy",
                    "low",
                    f"Micro pump: {change_1m*100:.1f}% with volume confirmation"
                )
            return (
                PatternType.MICRO_PUMP,
                SignalStrength.LOW,
                0.60,
                "buy",
                "low",
                f"Micro pump: {change_1m*100:.1f}% - low volume, cautious entry"
            )
        
        # ========================
        # DEAD CAT BOUNCE CHECK
        # ========================
        if change_1m > 0 and PatternType.DUMP in recent_patterns[-3:] if recent_patterns else False:
            if momentum <= self.weak_momentum:
                return (
                    PatternType.DEAD_CAT_BOUNCE,
                    SignalStrength.MEDIUM,
                    0.70,
                    "sell",
                    "high",
                    "Dead cat bounce - false recovery, don't buy the dip!"
                )
        
        # ========================
        # ACCUMULATION (Slow rise)
        # ========================
        if 0 < change_1m < self.micro_pump_threshold and change_5m > 0.05:
            if momentum > 0:
                return (
                    PatternType.ACCUMULATION,
                    SignalStrength.LOW,
                    0.60,
                    "buy",
                    "low",
                    f"Accumulation: slow steady rise ({change_5m*100:.1f}% in 5m)"
                )
        
        # ========================
        # DISTRIBUTION (Slow decline)
        # ========================
        if self.dump_threshold < change_1m < 0 and change_5m < -0.05:
            return (
                PatternType.DISTRIBUTION,
                SignalStrength.LOW,
                0.55,
                "sell",
                "medium",
                f"Distribution: slow decline ({change_5m*100:.1f}% in 5m)"
            )
        
        # ========================
        # SIDEWAYS / UNKNOWN
        # ========================
        if abs(change_1m) < 0.02 and abs(change_5m) < 0.05:
            return (
                PatternType.SIDEWAYS,
                SignalStrength.LOW,
                0.50,
                "hold",
                "low",
                "Sideways movement - no clear direction"
            )
        
        return (
            PatternType.UNKNOWN,
            SignalStrength.LOW,
            0.40,
            "hold",
            "medium",
            "No clear pattern detected"
        )
    
    def _calculate_levels(
        self,
        current_price: float,
        pattern: PatternType,
        change_1m: float
    ) -> tuple:
        """
        Calculate suggested stop-loss and take-profit levels.
        
        Returns:
            (stop_loss_price, take_profit_price)
        """
        if current_price <= 0:
            return None, None
        
        # Default levels
        stop_loss_pct = 0.10  # 10% stop loss
        take_profit_pct = 0.25  # 25% take profit
        
        # Adjust based on pattern
        if pattern == PatternType.RUG_PULL:
            # No stop loss - already in emergency
            return None, None
        
        elif pattern == PatternType.MEGA_PUMP:
            # Tight stop loss, aggressive take profit
            stop_loss_pct = 0.15
            take_profit_pct = 0.50
        
        elif pattern == PatternType.MID_PUMP:
            stop_loss_pct = 0.10
            take_profit_pct = 0.30
        
        elif pattern == PatternType.MICRO_PUMP:
            stop_loss_pct = 0.08
            take_profit_pct = 0.20
        
        elif pattern == PatternType.FOMO_SPIKE:
            # Very tight stop loss
            stop_loss_pct = 0.05
            take_profit_pct = 0.15
        
        elif pattern == PatternType.DUMP:
            # Already dumping, protect remaining
            stop_loss_pct = 0.05
            take_profit_pct = 0.10
        
        stop_loss = current_price * (1 - stop_loss_pct)
        take_profit = current_price * (1 + take_profit_pct)
        
        return round(stop_loss, 8), round(take_profit, 8)
    
    def get_urgency_score(self, signal: PatternSignal) -> float:
        """
        Calculate urgency score (0-1) for prioritizing actions.
        
        Higher score = act faster
        """
        base_score = 0.5
        
        # Pattern urgency
        pattern_scores = {
            PatternType.RUG_PULL: 1.0,
            PatternType.DUMP: 0.85,
            PatternType.FOMO_SPIKE: 0.75,
            PatternType.MEGA_PUMP: 0.70,
            PatternType.MID_PUMP: 0.60,
            PatternType.DEAD_CAT_BOUNCE: 0.65,
            PatternType.MICRO_PUMP: 0.50,
            PatternType.DISTRIBUTION: 0.45,
            PatternType.ACCUMULATION: 0.40,
            PatternType.SIDEWAYS: 0.20,
            PatternType.UNKNOWN: 0.30,
        }
        
        base_score = pattern_scores.get(signal.pattern, 0.5)
        
        # Adjust for magnitude
        magnitude = abs(signal.price_change_1m)
        if magnitude > 0.20:
            base_score += 0.15
        elif magnitude > 0.10:
            base_score += 0.10
        
        # Adjust for volume
        if signal.volume_spike > 5:
            base_score += 0.10
        elif signal.volume_spike > 3:
            base_score += 0.05
        
        return min(1.0, base_score)

