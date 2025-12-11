"""
LLM Usage Logger - Tracks costs and usage across all agents.

This module provides a centralized way to log and track LLM API usage
including costs, token counts, and request/response summaries.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

logger = logging.getLogger(__name__)

# LLM Cost rates per million tokens (as of Dec 2024)
LLM_COST_RATES = {
    # DeepSeek via OpenRouter
    "deepseek/deepseek-chat": {
        "input": 0.14,   # $0.14 per million input tokens
        "output": 0.28,  # $0.28 per million output tokens
    },
    "deepseek/deepseek-coder": {
        "input": 0.14,
        "output": 0.28,
    },
    # Google Gemini
    "gemini-2.0-flash": {
        "input": 0.075,   # $0.075 per million tokens (or free tier)
        "output": 0.30,
    },
    "gemini-1.5-flash": {
        "input": 0.075,
        "output": 0.30,
    },
    "gemini-1.5-pro": {
        "input": 1.25,
        "output": 5.00,
    },
    # Default fallback rate
    "default": {
        "input": 0.50,
        "output": 1.00,
    },
}


@dataclass
class LLMUsageRecord:
    """Represents a single LLM API call record."""
    id: str
    timestamp: str
    agent: str  # news-agent, trend-agent, rules-agent, trade-agent
    model: str
    user_id: Optional[int]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    request_summary: str  # First 500 chars of request
    response_summary: str  # First 500 chars of response
    duration_ms: int  # Request duration in milliseconds
    success: bool
    error_message: Optional[str] = None


class LLMUsageLogger:
    """
    Centralized logger for LLM usage across all agents.
    Thread-safe SQLite-based storage with automatic cost calculation.
    """
    
    _instance: Optional["LLMUsageLogger"] = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Optional[str] = None):
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the logger with database path."""
        if self._initialized:
            return
            
        # Determine database path
        if db_path:
            self.db_path = db_path
        else:
            # Try environment variable, then default
            self.db_path = os.environ.get(
                "LLM_USAGE_DB_PATH",
                os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "data",
                    "llm_usage.db"
                )
            )
        
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        self._initialized = True
        logger.info(f"LLM Usage Logger initialized with database: {self.db_path}")
    
    def _init_database(self):
        """Create the llm_usage table if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_usage (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    model TEXT NOT NULL,
                    user_id INTEGER,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    request_summary TEXT,
                    response_summary TEXT,
                    duration_ms INTEGER,
                    success INTEGER NOT NULL,
                    error_message TEXT
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_usage_timestamp 
                ON llm_usage(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_usage_agent 
                ON llm_usage(agent)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_usage_model 
                ON llm_usage(model)
            """)
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate the cost of an LLM call based on token counts.
        
        Args:
            model: The model name (e.g., "deepseek/deepseek-chat")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        rates = LLM_COST_RATES.get(model, LLM_COST_RATES["default"])
        
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        
        return round(input_cost + output_cost, 8)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.
        Uses a simple heuristic: ~4 characters per token for English text.
        
        Args:
            text: The text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        # Rough estimation: 1 token ≈ 4 characters
        return max(1, len(text) // 4)
    
    def log_usage(
        self,
        agent: str,
        model: str,
        request_text: str,
        response_text: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        user_id: Optional[int] = None,
        duration_ms: int = 0,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> LLMUsageRecord:
        """
        Log an LLM API usage record.
        
        Args:
            agent: Agent name (news-agent, trend-agent, rules-agent, trade-agent)
            model: Model name (e.g., "deepseek/deepseek-chat", "gemini-2.0-flash")
            request_text: The full request/prompt text
            response_text: The full response text
            input_tokens: Actual input token count (if known), otherwise estimated
            output_tokens: Actual output token count (if known), otherwise estimated
            user_id: Optional user ID if the request is user-specific
            duration_ms: Request duration in milliseconds
            success: Whether the request was successful
            error_message: Error message if request failed
            
        Returns:
            The created LLMUsageRecord
        """
        # Estimate tokens if not provided
        if input_tokens is None:
            input_tokens = self.estimate_tokens(request_text)
        if output_tokens is None:
            output_tokens = self.estimate_tokens(response_text)
        
        # Calculate cost
        cost_usd = self.calculate_cost(model, input_tokens, output_tokens)
        
        # Create record
        record = LLMUsageRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent=agent,
            model=model,
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            request_summary=request_text[:500] if request_text else "",
            response_summary=response_text[:500] if response_text else "",
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        
        # Insert into database
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO llm_usage (
                        id, timestamp, agent, model, user_id,
                        input_tokens, output_tokens, cost_usd,
                        request_summary, response_summary,
                        duration_ms, success, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    record.timestamp,
                    record.agent,
                    record.model,
                    record.user_id,
                    record.input_tokens,
                    record.output_tokens,
                    record.cost_usd,
                    record.request_summary,
                    record.response_summary,
                    record.duration_ms,
                    1 if record.success else 0,
                    record.error_message
                ))
                conn.commit()
                
            logger.debug(
                f"Logged LLM usage: {agent}/{model} - "
                f"${cost_usd:.6f} ({input_tokens}in/{output_tokens}out tokens)"
            )
            
        except Exception as e:
            logger.error(f"Failed to log LLM usage: {e}")
        
        return record
    
    def get_daily_summary(self, date: Optional[str] = None) -> dict:
        """
        Get aggregated usage summary for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            Dictionary with summary statistics
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        with self._get_connection() as conn:
            # Total summary
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(cost_usd) as total_cost,
                    AVG(duration_ms) as avg_duration_ms,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests
                FROM llm_usage
                WHERE date(timestamp) = ?
            """, (date,))
            
            row = cursor.fetchone()
            
            # By agent breakdown
            agent_cursor = conn.execute("""
                SELECT 
                    agent,
                    COUNT(*) as requests,
                    SUM(cost_usd) as cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens
                FROM llm_usage
                WHERE date(timestamp) = ?
                GROUP BY agent
                ORDER BY cost DESC
            """, (date,))
            
            agents = [dict(r) for r in agent_cursor.fetchall()]
            
            # By model breakdown
            model_cursor = conn.execute("""
                SELECT 
                    model,
                    COUNT(*) as requests,
                    SUM(cost_usd) as cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens
                FROM llm_usage
                WHERE date(timestamp) = ?
                GROUP BY model
                ORDER BY cost DESC
            """, (date,))
            
            models = [dict(r) for r in model_cursor.fetchall()]
        
        return {
            "date": date,
            "total_requests": row["total_requests"] or 0,
            "total_input_tokens": row["total_input_tokens"] or 0,
            "total_output_tokens": row["total_output_tokens"] or 0,
            "total_cost_usd": round(row["total_cost"] or 0, 6),
            "avg_duration_ms": round(row["avg_duration_ms"] or 0, 2),
            "successful_requests": row["successful_requests"] or 0,
            "success_rate": round(
                (row["successful_requests"] or 0) / max(1, row["total_requests"] or 1) * 100, 
                1
            ),
            "by_agent": agents,
            "by_model": models
        }
    
    def get_recent_usage(self, limit: int = 100) -> list[dict]:
        """
        Get recent LLM usage records.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of usage records as dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT *
                FROM llm_usage
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_hourly_costs(self, date: Optional[str] = None) -> list[dict]:
        """
        Get hourly cost breakdown for charting.
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            List of hourly aggregates
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as requests,
                    SUM(cost_usd) as cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens
                FROM llm_usage
                WHERE date(timestamp) = ?
                GROUP BY strftime('%H', timestamp)
                ORDER BY hour
            """, (date,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_cost_timeline(self, days: int = 7) -> list[dict]:
        """
        Get daily cost breakdown for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of daily aggregates
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    date(timestamp) as date,
                    COUNT(*) as requests,
                    SUM(cost_usd) as cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens
                FROM llm_usage
                WHERE timestamp >= datetime('now', ?)
                GROUP BY date(timestamp)
                ORDER BY date
            """, (f"-{days} days",))
            
            return [dict(row) for row in cursor.fetchall()]


# Global instance for easy access
_logger_instance: Optional[LLMUsageLogger] = None


def get_llm_logger(db_path: Optional[str] = None) -> LLMUsageLogger:
    """
    Get the global LLM usage logger instance.
    
    Args:
        db_path: Optional path to the SQLite database
        
    Returns:
        LLMUsageLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = LLMUsageLogger(db_path)
    return _logger_instance


def log_llm_usage(
    agent: str,
    model: str,
    request_text: str,
    response_text: str,
    **kwargs
) -> LLMUsageRecord:
    """
    Convenience function to log LLM usage.
    
    Args:
        agent: Agent name
        model: Model name
        request_text: The request/prompt text
        response_text: The response text
        **kwargs: Additional arguments passed to LLMUsageLogger.log_usage
        
    Returns:
        The created LLMUsageRecord
    """
    return get_llm_logger().log_usage(
        agent=agent,
        model=model,
        request_text=request_text,
        response_text=response_text,
        **kwargs
    )
