from __future__ import annotations

import json
import sqlite3
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

    def latest_snapshot_timestamp(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(last_fetched_at) AS latest FROM users").fetchone()
        if not row:
            return None
        return row["latest"]

