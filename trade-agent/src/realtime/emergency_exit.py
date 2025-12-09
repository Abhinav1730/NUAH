"""
Emergency Exit Handler
======================
Fast-path execution for critical exits.

Bypasses the normal LangGraph pipeline for immediate action.
Used when:
- Rug pull detected
- Catastrophic price drop
- Critical risk threshold breached

Speed is critical - this should execute in < 1 second.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
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

from .risk_guard import ExitSignal, ExitReason, Position

logger = logging.getLogger(__name__)


@dataclass
class EmergencyExitResult:
    """Result of an emergency exit execution"""
    success: bool
    token_mint: str
    user_id: int
    reason: ExitReason
    amount_sold: float
    execution_time_ms: float
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "token_mint": self.token_mint,
            "user_id": self.user_id,
            "reason": self.reason.value,
            "amount_sold": self.amount_sold,
            "execution_time_ms": self.execution_time_ms,
            "tx_hash": self.tx_hash,
            "error": self.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class EmergencyExit:
    """
    Fast-path emergency exit execution.
    
    This bypasses the normal pipeline and executes sells immediately.
    Designed for maximum speed in critical situations.
    """
    
    def __init__(
        self,
        api_base_url: str = "http://localhost:8080",
        api_token: Optional[str] = None,
        dry_run: bool = True,
        max_slippage: float = 0.10,  # Accept up to 10% slippage in emergencies
    ):
        self.api_base_url = api_base_url
        self.api_token = api_token
        self.dry_run = dry_run
        self.max_slippage = max_slippage
        
        self._client: Optional[NuahChainClient] = None
        if NuahChainClient and api_token:
            self._client = NuahChainClient(
                base_url=api_base_url,
                api_token=api_token,
                timeout=5,  # Short timeout for speed
                max_retries=1,  # Don't retry - speed is critical
            )
        
        self.exit_history: List[EmergencyExitResult] = []
    
    def execute_exit(self, signal: ExitSignal) -> EmergencyExitResult:
        """
        Execute an emergency exit synchronously.
        
        Args:
            signal: Exit signal from RiskGuard
            
        Returns:
            EmergencyExitResult with execution details
        """
        start_time = time.time()
        
        token = signal.position.token_mint
        user_id = signal.position.user_id
        amount = signal.exit_amount
        
        logger.critical(
            f"🚨 EMERGENCY EXIT EXECUTING: {token} | "
            f"user={user_id} | amount={amount} | reason={signal.reason.value}"
        )
        
        try:
            if self.dry_run:
                # Simulate execution
                result = self._simulate_exit(signal)
            else:
                # Real execution
                result = self._execute_real_exit(signal)
            
            execution_time = (time.time() - start_time) * 1000
            
            exit_result = EmergencyExitResult(
                success=result.get("success", False),
                token_mint=token,
                user_id=user_id,
                reason=signal.reason,
                amount_sold=amount,
                execution_time_ms=execution_time,
                tx_hash=result.get("tx_hash"),
                error=result.get("error"),
            )
            
            self.exit_history.append(exit_result)
            
            if exit_result.success:
                logger.warning(
                    f"✅ Emergency exit SUCCESS: {token} | "
                    f"time={execution_time:.0f}ms | tx={exit_result.tx_hash}"
                )
            else:
                logger.error(
                    f"❌ Emergency exit FAILED: {token} | "
                    f"error={exit_result.error}"
                )
            
            return exit_result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            logger.exception(f"Emergency exit exception: {e}")
            
            return EmergencyExitResult(
                success=False,
                token_mint=token,
                user_id=user_id,
                reason=signal.reason,
                amount_sold=0,
                execution_time_ms=execution_time,
                error=str(e),
            )
    
    def _simulate_exit(self, signal: ExitSignal) -> Dict[str, Any]:
        """Simulate an exit for dry-run mode"""
        # Simulate network delay
        time.sleep(0.05)  # 50ms simulated latency
        
        logger.info(
            f"[DRY RUN] Would sell {signal.exit_amount} of {signal.position.token_mint}"
        )
        
        return {
            "success": True,
            "tx_hash": f"DRY-RUN-{int(time.time())}",
        }
    
    def _execute_real_exit(self, signal: ExitSignal) -> Dict[str, Any]:
        """Execute a real exit via API"""
        if not self._client:
            return {
                "success": False,
                "error": "No API client configured",
            }
        
        token = signal.position.token_mint
        amount = signal.exit_amount
        
        # Convert amount to micro-units
        token_amount = str(int(amount * 1_000_000))
        
        # Calculate minimum acceptable output (with slippage tolerance)
        expected_output = amount  # Simplified - would need price calculation
        min_output = str(int(expected_output * (1 - self.max_slippage) * 1_000_000))
        
        try:
            response = self._client.sell_token(
                denom=token,
                token_amount=token_amount,
                min_payment_out=min_output,
            )
            
            if response:
                return {
                    "success": response.get("status") in ["PENDING", "SUCCESS"],
                    "tx_hash": response.get("tx_hash"),
                    "error": response.get("error"),
                }
            else:
                return {
                    "success": False,
                    "error": "No response from API",
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def execute_exit_async(self, signal: ExitSignal) -> EmergencyExitResult:
        """
        Execute an emergency exit asynchronously.
        
        For use in async contexts like the price monitor.
        """
        # Run sync execution in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute_exit, signal)
    
    def execute_batch(self, signals: List[ExitSignal]) -> List[EmergencyExitResult]:
        """
        Execute multiple emergency exits in priority order.
        
        Args:
            signals: List of exit signals
            
        Returns:
            List of execution results
        """
        # Sort by urgency (highest first)
        sorted_signals = sorted(signals, key=lambda s: s.urgency, reverse=True)
        
        results = []
        for signal in sorted_signals:
            result = self.execute_exit(signal)
            results.append(result)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get emergency exit statistics"""
        if not self.exit_history:
            return {
                "total_exits": 0,
                "successful_exits": 0,
                "failed_exits": 0,
                "avg_execution_time_ms": 0,
            }
        
        successful = [e for e in self.exit_history if e.success]
        failed = [e for e in self.exit_history if not e.success]
        avg_time = sum(e.execution_time_ms for e in self.exit_history) / len(self.exit_history)
        
        return {
            "total_exits": len(self.exit_history),
            "successful_exits": len(successful),
            "failed_exits": len(failed),
            "success_rate": len(successful) / len(self.exit_history),
            "avg_execution_time_ms": avg_time,
            "by_reason": self._count_by_reason(),
        }
    
    def _count_by_reason(self) -> Dict[str, int]:
        """Count exits by reason"""
        counts: Dict[str, int] = {}
        for exit in self.exit_history:
            reason = exit.reason.value
            counts[reason] = counts.get(reason, 0) + 1
        return counts


class EmergencyExitQueue:
    """
    Queue-based emergency exit processor.
    
    Processes exits in a dedicated thread/loop for maximum responsiveness.
    """
    
    def __init__(self, exit_handler: EmergencyExit):
        self.handler = exit_handler
        self.queue: List[ExitSignal] = []
        self._running = False
    
    def add(self, signal: ExitSignal):
        """Add an exit signal to the queue"""
        self.queue.append(signal)
        
        # Sort by urgency
        self.queue.sort(key=lambda s: s.urgency, reverse=True)
        
        logger.info(f"Exit queued: {signal.position.token_mint} (queue size: {len(self.queue)})")
    
    def process_queue(self) -> List[EmergencyExitResult]:
        """Process all queued exits"""
        results = []
        
        while self.queue:
            signal = self.queue.pop(0)
            result = self.handler.execute_exit(signal)
            results.append(result)
        
        return results
    
    async def run_loop(self, check_interval: float = 0.1):
        """
        Run continuous queue processor.
        
        Args:
            check_interval: Seconds between queue checks
        """
        self._running = True
        logger.info("Emergency exit queue processor started")
        
        while self._running:
            if self.queue:
                signal = self.queue.pop(0)
                await self.handler.execute_exit_async(signal)
            else:
                await asyncio.sleep(check_interval)
    
    def stop(self):
        """Stop the queue processor"""
        self._running = False

