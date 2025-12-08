"""
Data Sync Service

Synchronizes real blockchain data from nuahchain-backend to CSV files,
and optionally into SQLite for downstream agents. This replaces dummy data
with real data.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .denom_mapper import DenomMapper
from .nuahchain_client import NuahChainClient

logger = logging.getLogger(__name__)


class DataSyncService:
    """
    Service to sync real blockchain data from nuahchain-backend to CSV files,
    and (optionally) to a SQLite database.
    """

    def __init__(
        self,
        client: NuahChainClient,
        data_dir: Path,
        mapper: Optional[DenomMapper] = None,
        sqlite_path: Optional[Path] = None,
    ):
        self.client = client
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.mapper = mapper or DenomMapper()
        self.sqlite_path = Path(sqlite_path) if sqlite_path else None
        if self.sqlite_path:
            self._ensure_sqlite()

    # ------------------------------------------------------------------ catalog
    def sync_token_catalog(self) -> bool:
        """Sync token catalog from marketplace to token_strategy_catalog.csv (and SQLite)."""
        try:
            logger.info("Syncing token catalog from nuahchain-backend...")
            tokens = self.client.get_marketplace_tokens(limit=1000)

            if not tokens:
                logger.warning("No tokens found in marketplace")
                return False

            catalog_rows = []
            for token in tokens:
                denom = token.get("denom", "")
                if not denom:
                    continue

                token_mint = self.mapper.denom_to_token_mint(denom)

                # Extract token data
                name = token.get("name", "")
                symbol = token.get("symbol", "")
                stats = token.get("stats", {})

                # Risk score based on sale progress
                tokens_sold = float(stats.get("tokens_sold", 0) or 0)
                total_supply = float(stats.get("total_supply", 1) or 1)
                curve_completed = bool(stats.get("curve_completed", False))
                if curve_completed:
                    risk_score = 0.3
                elif tokens_sold / total_supply < 0.1:
                    risk_score = 0.8
                elif tokens_sold / total_supply < 0.5:
                    risk_score = 0.6
                else:
                    risk_score = 0.4

                # Liquidity proxy
                volume_24h = float(stats.get("volume_24h", 0) or 0)
                if volume_24h > 1_000_000:
                    liquidity_score = 0.8
                elif volume_24h > 100_000:
                    liquidity_score = 0.6
                else:
                    liquidity_score = 0.4

                # Volatility placeholder
                volatility_score = 0.5

                # Bonding curve phase
                if curve_completed:
                    phase = "late"
                elif tokens_sold / total_supply < 0.3:
                    phase = "early"
                else:
                    phase = "mid"

                catalog_rows.append(
                    {
                        "token_mint": token_mint,
                        "name": name,
                        "symbol": symbol,
                        "bonding_curve_phase": phase,
                        "risk_score": round(risk_score, 2),
                        "creator_reputation": 0.5,  # placeholder
                        "liquidity_score": round(liquidity_score, 2),
                        "volatility_score": round(volatility_score, 2),
                        "whale_concentration": 0.3,  # placeholder
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                    }
                )

            df = pd.DataFrame(catalog_rows)
            catalog_path = self.data_dir / "token_strategy_catalog.csv"
            df.to_csv(catalog_path, index=False)

            if self.sqlite_path:
                self._write_token_catalog_sqlite(df)

            logger.info(f"Synced {len(catalog_rows)} tokens to token_strategy_catalog.csv")
            return True

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error syncing token catalog: {e}", exc_info=True)
            return False

    # ---------------------------------------------------------------- time series
    def sync_time_series(self, hours: int = 24) -> bool:
        """
        Sync time-series data from balance history and transactions.
        Simplified: derives OHLCV from balance history amounts.
        """
        try:
            logger.info(f"Syncing time-series data (last {hours} hours)...")

            if not self.client.api_token:
                logger.warning("No API token, cannot fetch balance history for time-series")
                return False

            history = self.client.get_balance_history(limit=1000)
            if not history:
                logger.warning("No balance history found")
                return False

            denom_data: Dict[str, List[Dict]] = {}
            for record in history:
                denom = record.get("denom", "")
                if not denom or denom in ["unuah", "undollar"]:
                    continue
                denom_data.setdefault(denom, []).append(record)

            time_series_rows = []
            for denom, records in denom_data.items():
                token_mint = self.mapper.denom_to_token_mint(denom)
                records.sort(key=lambda x: x.get("created_at", ""))
                if len(records) < 2:
                    continue

                prices = []
                for record in records:
                    amount_after = float(record.get("amount_after", 0) or 0)
                    if amount_after > 0:
                        prices.append(amount_after)
                if len(prices) < 2:
                    continue

                latest_price = prices[-1]
                prev_price = prices[-2] if len(prices) >= 2 else latest_price
                momentum = (latest_price - prev_price) / prev_price if prev_price > 0 else 0.0

                if len(prices) >= 3:
                    changes = [
                        (prices[i] - prices[i - 1]) / prices[i - 1]
                        for i in range(1, len(prices))
                        if prices[i - 1] > 0
                    ]
                    if changes:
                        import statistics

                        volatility = (
                            statistics.stdev(changes) if len(changes) > 1 else abs(changes[0])
                        )
                    else:
                        volatility = 0.0
                else:
                    volatility = abs(momentum)

                volume = sum(abs(float(r.get("amount_delta", 0) or 0)) for r in records)
                timestamp = records[-1].get("created_at", datetime.now(timezone.utc).isoformat())

                time_series_rows.append(
                    {
                        "token_mint": token_mint,
                        "timestamp": timestamp,
                        "open": prev_price,
                        "high": max(prices),
                        "low": min(prices),
                        "close": latest_price,
                        "volume": volume,
                        "momentum": round(momentum, 6),
                        "volatility": round(volatility, 6),
                    }
                )

            if not time_series_rows:
                logger.warning("No time-series data generated")
                return False

            time_series_path = self.data_dir / "time_series.csv"
            df_new = pd.DataFrame(time_series_rows)
            if time_series_path.exists():
                df_existing = pd.read_csv(time_series_path)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=["token_mint", "timestamp"], keep="last")
                df_combined.to_csv(time_series_path, index=False)
                df_to_store = df_combined
            else:
                df_new.to_csv(time_series_path, index=False)
                df_to_store = df_new

            if self.sqlite_path:
                self._write_time_series_sqlite(df_to_store)

            logger.info(f"Synced {len(time_series_rows)} time-series records")
            return True

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error syncing time-series: {e}", exc_info=True)
            return False

    # ---------------------------------------------------------------- all
    def sync_all(self) -> Dict[str, bool]:
        """Sync all data types."""
        return {
            "token_catalog": self.sync_token_catalog(),
            "time_series": self.sync_time_series(),
        }

    # ---------------------------------------------------------------- internals (sqlite)
    def _ensure_sqlite(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_strategy_catalog (
                  token_mint TEXT PRIMARY KEY,
                  name TEXT,
                  symbol TEXT,
                  bonding_curve_phase TEXT,
                  risk_score REAL,
                  creator_reputation REAL,
                  liquidity_score REAL,
                  volatility_score REAL,
                  whale_concentration REAL,
                  last_updated TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS time_series (
                  token_mint TEXT,
                  timestamp TEXT,
                  open REAL,
                  high REAL,
                  low REAL,
                  close REAL,
                  volume REAL,
                  momentum REAL,
                  volatility REAL,
                  UNIQUE(token_mint, timestamp)
                )
                """
            )
            conn.commit()

    def _write_token_catalog_sqlite(self, df: pd.DataFrame) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            df.to_sql("token_strategy_catalog", conn, if_exists="replace", index=False)
            conn.commit()

    def _write_time_series_sqlite(self, df: pd.DataFrame) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            df.to_sql("time_series", conn, if_exists="replace", index=False)
            conn.commit()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync data from nuahchain-backend to CSV/SQLite.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="nuahchain-backend base URL")
    parser.add_argument("--api-token", required=True, help="JWT token for nuahchain-backend")
    parser.add_argument("--data-dir", default="data", help="Directory for CSV outputs")
    parser.add_argument("--sqlite-path", default="/data/time_series.db", help="Optional path to SQLite DB to store outputs")
    parser.add_argument("--hours", type=int, default=24, help="History hours for time-series")
    parser.add_argument("--interval-minutes", type=int, default=0, help="If >0, run periodically")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    args = _parse_args()

    client = NuahChainClient(base_url=args.base_url, api_token=args.api_token)
    service = DataSyncService(
        client=client,
        data_dir=Path(args.data_dir),
        sqlite_path=Path(args.sqlite_path) if args.sqlite_path else None,
    )

    def run_once():
        results = service.sync_all()
        logger.info("Sync results: %s", results)

    if args.interval_minutes and args.interval_minutes > 0:
        logger.info("Starting periodic sync every %s minutes", args.interval_minutes)
        while True:
            run_once()
            time.sleep(args.interval_minutes * 60)
    else:
        run_once()


if __name__ == "__main__":
    main()

