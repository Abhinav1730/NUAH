from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class SQLiteDataLoader:
    """
    Lightweight helper around the fetch-data-agent SQLite database.
    No ORM to keep things simple and dependency-free.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_recent_users(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = """
        SELECT id AS user_id, username, email, public_key, last_fetched_at
        FROM users
        ORDER BY last_fetched_at DESC NULLS LAST, updated_at DESC
        """
        if limit:
            sql += " LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(sql, (limit,) if limit else ()).fetchall()
        return [dict(row) for row in rows]

    def fetch_user_snapshot(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not user:
                return None

            balances = conn.execute(
                "SELECT token_mint, balance, updated_at FROM user_balances WHERE user_id = ?",
                (user_id,),
            ).fetchall()

            transactions = conn.execute(
                """
                SELECT transaction_type, token_mint, amount, signature, timestamp
                FROM user_transactions
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 100
                """,
                (user_id,),
            ).fetchall()

            portfolio = conn.execute(
                """
                SELECT total_value_ndollar, total_value_sol, token_count, snapshot_json, created_at
                FROM user_portfolios
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

        snapshot_data = {
            "user": dict(user),
            "balances": [dict(row) for row in balances],
            "transactions": [dict(row) for row in transactions],
            "portfolio": json.loads(portfolio["snapshot_json"])
            if portfolio and portfolio["snapshot_json"]
            else None,
        }
        return snapshot_data

    def fetch_news_signals(
        self, token_filter: Optional[List[str]] = None, freshness_minutes: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM news_signals"
        params: List[Any] = []
        clauses = []
        if token_filter:
            clauses.append(f"token_mint IN ({','.join(['?']*len(token_filter))})")
            params.extend(token_filter)
        if freshness_minutes:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=freshness_minutes)
            clauses.append("timestamp >= ?")
            params.append(cutoff.isoformat())
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY timestamp DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def fetch_trend_signals(
        self, token_filter: Optional[List[str]] = None, freshness_minutes: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM trend_signals"
        params: List[Any] = []
        clauses = []
        if token_filter:
            clauses.append(f"token_mint IN ({','.join(['?']*len(token_filter))})")
            params.extend(token_filter)
        if freshness_minutes:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=freshness_minutes)
            clauses.append("timestamp >= ?")
            params.append(cutoff.isoformat())
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY timestamp DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def fetch_rule_evaluations(self, user_id: int, token_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM rule_evaluations WHERE user_id = ?"
        params: List[Any] = [user_id]
        if token_filter:
            sql += f" AND token_mint IN ({','.join(['?']*len(token_filter))})"
            params.extend(token_filter)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def fetch_user_preferences(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def fetch_token_catalog(self, token_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM token_strategy_catalog"
        params: List[Any] = []
        if token_filter:
            sql += f" WHERE token_mint IN ({','.join(['?']*len(token_filter))})"
            params.extend(token_filter)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def fetch_time_series(self, token_filter: Optional[List[str]] = None, limit_per_token: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT token_mint, timestamp, open, high, low, close, volume, momentum, volatility FROM time_series"
        params: List[Any] = []
        if token_filter:
            sql += f" WHERE token_mint IN ({','.join(['?']*len(token_filter))})"
            params.extend(token_filter)
        sql += " ORDER BY token_mint, timestamp DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        if limit_per_token and rows:
            limited: List[Dict[str, Any]] = []
            counts: Dict[str, int] = {}
            for row in rows:
                token = row["token_mint"]
                counts[token] = counts.get(token, 0) + 1
                if counts[token] <= limit_per_token:
                    limited.append(dict(row))
            return limited
        return [dict(r) for r in rows]

    def latest_snapshot_timestamp(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(last_fetched_at) AS latest FROM users").fetchone()
        if not row:
            return None
        return row["latest"]

