from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from ..models.rule_evaluator import TradeDecision


class AuditLogger:
    """
    Persists executed (or skipped) trades to SQLite database for downstream analytics.
    """

    def __init__(self, sqlite_path: Path):
        """
        Initialize the audit logger with SQLite database path.
        
        Args:
            sqlite_path: Path to the SQLite database file
        """
        self.sqlite_path = Path(sqlite_path)
        self._ensure_table_exists()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection to the SQLite database."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table_exists(self) -> None:
        """Ensure the trade_executions table exists."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    token_mint TEXT,
                    action TEXT NOT NULL,
                    amount TEXT,
                    price TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    pnl TEXT,
                    slippage TEXT,
                    risk_score REAL,
                    confidence REAL,
                    reason TEXT,
                    status TEXT DEFAULT 'completed',
                    tx_hash TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes if they don't exist
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_executions_user_id 
                ON trade_executions(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_executions_timestamp 
                ON trade_executions(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_executions_token 
                ON trade_executions(token_mint)
            """)
            conn.commit()

    def log(
        self,
        decision: TradeDecision,
        metadata: Dict[str, str],
        status: str = "completed",
        tx_hash: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Log a trade execution to the database.
        
        Args:
            decision: The trade decision made by the pipeline
            metadata: Additional metadata about the trade
            status: Status of the execution (completed, failed, simulated, skipped)
            tx_hash: Blockchain transaction hash if executed
            error_message: Error message if failed
        """
        trade_id = metadata.get("trade_id", f"TRADE-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        timestamp = metadata.get("timestamp", datetime.now(timezone.utc).isoformat())
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO trade_executions (
                    trade_id, user_id, token_mint, action, amount, price,
                    timestamp, pnl, slippage, risk_score, confidence, reason,
                    status, tx_hash, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                decision.user_id,
                decision.token_mint,
                decision.action,
                str(decision.amount) if decision.amount else None,
                metadata.get("price"),
                timestamp,
                metadata.get("pnl"),
                metadata.get("slippage"),
                metadata.get("risk_score"),
                decision.confidence,
                decision.reason,
                status,
                tx_hash,
                error_message,
            ))
            conn.commit()

    def get_recent_trades(self, user_id: int, limit: int = 100) -> list:
        """
        Get recent trades for a user.
        
        Args:
            user_id: The user ID to get trades for
            limit: Maximum number of trades to return
            
        Returns:
            List of trade records as dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM trade_executions
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_trades_by_token(self, token_mint: str, limit: int = 100) -> list:
        """
        Get recent trades for a specific token.
        
        Args:
            token_mint: The token mint address
            limit: Maximum number of trades to return
            
        Returns:
            List of trade records as dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM trade_executions
                WHERE token_mint = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (token_mint, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_trade_stats(self, user_id: int) -> Dict:
        """
        Get trade statistics for a user.
        
        Args:
            user_id: The user ID to get stats for
            
        Returns:
            Dictionary with trade statistics
        """
        with self._get_connection() as conn:
            # Total trades
            total = conn.execute("""
                SELECT COUNT(*) as count FROM trade_executions WHERE user_id = ?
            """, (user_id,)).fetchone()["count"]
            
            # Trades by action
            actions = conn.execute("""
                SELECT action, COUNT(*) as count 
                FROM trade_executions 
                WHERE user_id = ?
                GROUP BY action
            """, (user_id,)).fetchall()
            
            # Trades today
            today = conn.execute("""
                SELECT COUNT(*) as count 
                FROM trade_executions 
                WHERE user_id = ? AND DATE(timestamp) = DATE('now')
            """, (user_id,)).fetchone()["count"]
            
            # Average confidence
            avg_confidence = conn.execute("""
                SELECT AVG(confidence) as avg 
                FROM trade_executions 
                WHERE user_id = ?
            """, (user_id,)).fetchone()["avg"]
            
            return {
                "total_trades": total,
                "trades_today": today,
                "by_action": {row["action"]: row["count"] for row in actions},
                "avg_confidence": round(avg_confidence, 3) if avg_confidence else 0,
            }
