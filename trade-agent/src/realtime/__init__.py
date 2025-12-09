"""
Real-Time Trading Module
========================
Fast-path components for pump.fun-style trading.

Components:
- PriceMonitor: Real-time price tracking
- PatternDetector: Pump/dump/rug pattern detection
- RiskGuard: Automated stop-loss and take-profit
- EmergencyExit: Fast-path emergency exits
"""

from .price_monitor import PriceMonitor, PriceUpdate
from .pattern_detector import PatternDetector, PatternSignal, PatternType
from .risk_guard import RiskGuard, Position, StopLossConfig
from .emergency_exit import EmergencyExit

__all__ = [
    "PriceMonitor",
    "PriceUpdate", 
    "PatternDetector",
    "PatternSignal",
    "PatternType",
    "RiskGuard",
    "Position",
    "StopLossConfig",
    "EmergencyExit",
]

