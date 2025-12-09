"""
Risk Guard
==========
Automated stop-loss and take-profit management.

For pump.fun trading, fast automated exits are critical:
- Stop Loss: Auto-exit when price drops X% from entry
- Trailing Stop: Lock in profits as price rises
- Take Profit: Auto-exit at profit targets
- Emergency Stop: Bypass normal flow for rug pulls
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

from .price_monitor import PriceUpdate
from .pattern_detector import PatternSignal, PatternType

logger = logging.getLogger(__name__)


class ExitReason(Enum):
    """Reason for position exit"""
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    EMERGENCY = "emergency"
    PATTERN_SIGNAL = "pattern_signal"
    MANUAL = "manual"


@dataclass
class StopLossConfig:
    """Configuration for stop-loss behavior"""
    # Basic stop loss
    stop_loss_percent: float = 0.10      # Exit if down 10%
    
    # Trailing stop
    trailing_stop_enabled: bool = True
    trailing_stop_percent: float = 0.08   # Trail by 8%
    trailing_activation: float = 0.05     # Activate after 5% profit
    
    # Take profit
    take_profit_percent: float = 0.25     # Exit at 25% profit
    partial_take_profit: bool = True      # Take partial profits
    partial_take_at: List[float] = field(default_factory=lambda: [0.15, 0.30, 0.50])
    partial_take_amount: float = 0.25     # Take 25% at each level
    
    # Emergency
    emergency_threshold: float = -0.30    # -30% = emergency exit
    rug_threshold: float = -0.50          # -50% = definite rug


@dataclass
class Position:
    """Represents an open position"""
    user_id: int
    token_mint: str
    entry_price: float
    amount: float
    entry_time: datetime
    
    # Tracking
    highest_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_percent: float = 0.0
    
    # Stop levels
    stop_loss_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    
    # Partial takes executed
    partial_takes_done: List[float] = field(default_factory=list)
    
    def __post_init__(self):
        self.highest_price = self.entry_price
        self.current_price = self.entry_price
    
    def update_price(self, new_price: float):
        """Update position with new price"""
        self.current_price = new_price
        
        # Track highest price for trailing stop
        if new_price > self.highest_price:
            self.highest_price = new_price
        
        # Calculate P&L
        self.unrealized_pnl = (new_price - self.entry_price) * self.amount / self.entry_price
        self.unrealized_pnl_percent = (new_price - self.entry_price) / self.entry_price
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "token_mint": self.token_mint,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "amount": self.amount,
            "entry_time": self.entry_time.isoformat(),
            "highest_price": self.highest_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_percent": self.unrealized_pnl_percent,
            "stop_loss_price": self.stop_loss_price,
            "trailing_stop_price": self.trailing_stop_price,
            "take_profit_price": self.take_profit_price,
        }


@dataclass
class ExitSignal:
    """Signal to exit a position"""
    position: Position
    reason: ExitReason
    exit_price: float
    exit_amount: float  # Can be partial
    urgency: float  # 0-1, higher = faster
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_mint": self.position.token_mint,
            "user_id": self.position.user_id,
            "reason": self.reason.value,
            "exit_price": self.exit_price,
            "exit_amount": self.exit_amount,
            "entry_price": self.position.entry_price,
            "pnl_percent": (self.exit_price - self.position.entry_price) / self.position.entry_price,
            "urgency": self.urgency,
            "timestamp": self.timestamp.isoformat(),
        }


# Type for exit callback
ExitCallback = Callable[[ExitSignal], None]


class RiskGuard:
    """
    Automated risk management for positions.
    
    Monitors all open positions and triggers exits based on:
    - Stop loss hits
    - Trailing stop hits
    - Take profit targets
    - Pattern-based signals (rug pull detection)
    """
    
    def __init__(self, config: StopLossConfig = None):
        self.config = config or StopLossConfig()
        self.positions: Dict[str, Position] = {}  # token_mint -> Position
        self.exit_callbacks: List[ExitCallback] = []
        self.exit_history: List[ExitSignal] = []
    
    def on_exit(self, callback: ExitCallback):
        """Register callback for exit signals"""
        self.exit_callbacks.append(callback)
    
    def add_position(
        self,
        user_id: int,
        token_mint: str,
        entry_price: float,
        amount: float,
        custom_stop_loss: float = None,
        custom_take_profit: float = None,
    ) -> Position:
        """
        Add a new position to monitor.
        
        Args:
            user_id: User ID
            token_mint: Token identifier
            entry_price: Entry price
            amount: Position size
            custom_stop_loss: Override default stop loss
            custom_take_profit: Override default take profit
        """
        position = Position(
            user_id=user_id,
            token_mint=token_mint,
            entry_price=entry_price,
            amount=amount,
            entry_time=datetime.now(timezone.utc),
        )
        
        # Set stop levels
        sl_pct = custom_stop_loss or self.config.stop_loss_percent
        tp_pct = custom_take_profit or self.config.take_profit_percent
        
        position.stop_loss_price = entry_price * (1 - sl_pct)
        position.take_profit_price = entry_price * (1 + tp_pct)
        
        self.positions[token_mint] = position
        
        logger.info(
            f"📍 Position added: {token_mint} @ {entry_price:.8f}, "
            f"SL={position.stop_loss_price:.8f}, TP={position.take_profit_price:.8f}"
        )
        
        return position
    
    def remove_position(self, token_mint: str):
        """Remove a position from monitoring"""
        if token_mint in self.positions:
            del self.positions[token_mint]
            logger.info(f"Position removed: {token_mint}")
    
    def get_position(self, token_mint: str) -> Optional[Position]:
        """Get a position by token"""
        return self.positions.get(token_mint)
    
    def check_price_update(self, update: PriceUpdate) -> Optional[ExitSignal]:
        """
        Check a price update against positions.
        
        Returns:
            ExitSignal if exit is triggered, None otherwise
        """
        token = update.token_mint
        if token not in self.positions:
            return None
        
        position = self.positions[token]
        position.update_price(update.price)
        
        # Check for exits in priority order
        
        # 1. Emergency exit (price crashed)
        if update.price_change_1m <= self.config.emergency_threshold:
            return self._trigger_exit(
                position,
                ExitReason.EMERGENCY,
                position.amount,
                urgency=1.0
            )
        
        # 2. Stop loss
        if position.stop_loss_price and update.price <= position.stop_loss_price:
            return self._trigger_exit(
                position,
                ExitReason.STOP_LOSS,
                position.amount,
                urgency=0.9
            )
        
        # 3. Trailing stop
        if self.config.trailing_stop_enabled:
            trailing_exit = self._check_trailing_stop(position, update.price)
            if trailing_exit:
                return trailing_exit
        
        # 4. Take profit
        if position.take_profit_price and update.price >= position.take_profit_price:
            return self._trigger_exit(
                position,
                ExitReason.TAKE_PROFIT,
                position.amount,
                urgency=0.7
            )
        
        # 5. Partial take profits
        if self.config.partial_take_profit:
            partial_exit = self._check_partial_take(position, update.price)
            if partial_exit:
                return partial_exit
        
        return None
    
    def check_pattern_signal(self, signal: PatternSignal) -> Optional[ExitSignal]:
        """
        Check a pattern signal for exit triggers.
        
        Args:
            signal: Pattern detection signal
            
        Returns:
            ExitSignal if pattern warrants exit
        """
        token = signal.token_mint
        if token not in self.positions:
            return None
        
        position = self.positions[token]
        
        # Rug pull = immediate exit
        if signal.pattern == PatternType.RUG_PULL:
            logger.critical(f"🚨 RUG PULL DETECTED: {token} - EMERGENCY EXIT!")
            return self._trigger_exit(
                position,
                ExitReason.EMERGENCY,
                position.amount,
                urgency=1.0
            )
        
        # Dump = exit
        if signal.pattern == PatternType.DUMP:
            logger.warning(f"⚠️ DUMP detected: {token} - exiting position")
            return self._trigger_exit(
                position,
                ExitReason.PATTERN_SIGNAL,
                position.amount,
                urgency=0.9
            )
        
        # Dead cat bounce = exit if in profit or small loss
        if signal.pattern == PatternType.DEAD_CAT_BOUNCE:
            if position.unrealized_pnl_percent > -0.10:
                logger.warning(f"Dead cat bounce: {token} - exiting")
                return self._trigger_exit(
                    position,
                    ExitReason.PATTERN_SIGNAL,
                    position.amount,
                    urgency=0.8
                )
        
        # FOMO spike while holding = take profits
        if signal.pattern == PatternType.FOMO_SPIKE:
            if position.unrealized_pnl_percent > 0.20:
                logger.info(f"FOMO spike: {token} - taking profits")
                return self._trigger_exit(
                    position,
                    ExitReason.TAKE_PROFIT,
                    position.amount * 0.5,  # Take 50%
                    urgency=0.7
                )
        
        return None
    
    def _check_trailing_stop(self, position: Position, current_price: float) -> Optional[ExitSignal]:
        """Check and update trailing stop"""
        pnl_pct = position.unrealized_pnl_percent
        
        # Only activate trailing stop after reaching activation threshold
        if pnl_pct < self.config.trailing_activation:
            return None
        
        # Calculate trailing stop price
        trail_pct = self.config.trailing_stop_percent
        new_trailing = position.highest_price * (1 - trail_pct)
        
        # Update trailing stop if higher
        if position.trailing_stop_price is None or new_trailing > position.trailing_stop_price:
            position.trailing_stop_price = new_trailing
            logger.debug(
                f"Trailing stop updated: {position.token_mint} = {new_trailing:.8f}"
            )
        
        # Check if trailing stop hit
        if position.trailing_stop_price and current_price <= position.trailing_stop_price:
            return self._trigger_exit(
                position,
                ExitReason.TRAILING_STOP,
                position.amount,
                urgency=0.85
            )
        
        return None
    
    def _check_partial_take(self, position: Position, current_price: float) -> Optional[ExitSignal]:
        """Check for partial take profit levels"""
        pnl_pct = position.unrealized_pnl_percent
        
        for level in self.config.partial_take_at:
            if level not in position.partial_takes_done and pnl_pct >= level:
                position.partial_takes_done.append(level)
                
                take_amount = position.amount * self.config.partial_take_amount
                
                logger.info(
                    f"Partial take profit: {position.token_mint} at {level*100:.0f}% "
                    f"(taking {self.config.partial_take_amount*100:.0f}%)"
                )
                
                return self._trigger_exit(
                    position,
                    ExitReason.TAKE_PROFIT,
                    take_amount,
                    urgency=0.6
                )
        
        return None
    
    def _trigger_exit(
        self,
        position: Position,
        reason: ExitReason,
        amount: float,
        urgency: float
    ) -> ExitSignal:
        """Create and dispatch an exit signal"""
        signal = ExitSignal(
            position=position,
            reason=reason,
            exit_price=position.current_price,
            exit_amount=amount,
            urgency=urgency,
            timestamp=datetime.now(timezone.utc),
        )
        
        # Log
        pnl_pct = (signal.exit_price - position.entry_price) / position.entry_price * 100
        logger.warning(
            f"🚪 EXIT SIGNAL: {position.token_mint} | reason={reason.value} | "
            f"PnL={pnl_pct:+.1f}% | urgency={urgency:.2f}"
        )
        
        # Store in history
        self.exit_history.append(signal)
        
        # If full exit, remove position
        if amount >= position.amount:
            self.remove_position(position.token_mint)
        else:
            # Partial exit - reduce position
            position.amount -= amount
        
        # Trigger callbacks
        for callback in self.exit_callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Exit callback error: {e}")
        
        return signal
    
    def update_all(self, price_updates: List[PriceUpdate]) -> List[ExitSignal]:
        """
        Update all positions with new prices and check for exits.
        
        Args:
            price_updates: List of price updates
            
        Returns:
            List of exit signals triggered
        """
        exits = []
        
        for update in price_updates:
            exit_signal = self.check_price_update(update)
            if exit_signal:
                exits.append(exit_signal)
        
        return exits
    
    def get_portfolio_status(self) -> Dict[str, Any]:
        """Get current portfolio status"""
        total_value = 0.0
        total_pnl = 0.0
        
        positions_list = []
        for pos in self.positions.values():
            positions_list.append(pos.to_dict())
            total_value += pos.amount + pos.unrealized_pnl
            total_pnl += pos.unrealized_pnl
        
        return {
            "total_positions": len(self.positions),
            "total_value": total_value,
            "total_unrealized_pnl": total_pnl,
            "positions": positions_list,
        }

