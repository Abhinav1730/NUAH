from __future__ import annotations

import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .config import NewsAgentSettings
from .generators import build_token_contexts
from .deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)


class NewsAgentPipeline:
    """
    SQLite-backed pipeline for news-agent.

    Loads time-series and token catalog from fetch-data-agent/data/user_data.db (or provided path),
    builds token contexts, filters them via DeepSeek, and writes news_signals.csv.
    """

    def __init__(
        self,
        settings: NewsAgentSettings,
        sqlite_path: Optional[Path] = None,
    ) -> None:
        self.settings = settings
        self.sqlite_path = Path(sqlite_path or "/data/user_data.db").resolve()
        self.data_dir = Path(settings.data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.client = DeepSeekClient(settings)
        self._validate_db()

    def run(self, token_filter: Optional[List[str]] = None) -> List[dict]:
        time_series, catalog = self._load_dataframes()

        contexts = build_token_contexts(time_series, catalog, self.settings.top_tokens)

        if token_filter:
            allowed = set(token_filter)
            contexts = [ctx for ctx in contexts if ctx.token_mint in allowed]

        if not contexts:
            logger.warning("No token contexts available from SQLite.")
            return []

        logger.info("Built %d token contexts from SQLite.", len(contexts))

        ranked = self.client.rank_and_filter_tokens(contexts, user_owned_mints=None)
        if ranked is None:
            logger.warning("DeepSeek returned no ranking; skipping.")
            return []

        filtered = [r for r in ranked if r.get("include")]
        if not filtered:
            logger.info("DeepSeek excluded all tokens; no signals to write.")
            return []

        signals = self._build_signals(filtered)
        self._write_news_signals(signals)
        logger.info("Wrote %d signals to news_signals.csv", len(signals))
        return signals

    # ------------------------------------------------------------------ helpers
    def _build_signals(self, ranked: List[dict]) -> List[dict]:
        iso_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        signals: List[dict] = []
        for idx, item in enumerate(ranked, start=1):
            token = item.get("token_mint") or f"TOKEN-{idx}"
            score = float(item.get("score", 0.6))
            reason = item.get("reason", "LLM-selected token")
            signals.append(
                {
                    "signal_id": f"NEWS-{idx:04d}",
                    "timestamp": iso_now,
                    "token_mint": token,
                    "headline": f"LLM selection for {token}",
                    "sentiment_score": max(-1.0, min(1.0, score * 2 - 1)),  # map 0..1 to -1..1
                    "confidence": max(0.0, min(1.0, score)),
                    "source": "deepseek",
                    "summary": reason,
                }
            )
        return signals

    def _write_news_signals(self, signals: List[dict]) -> None:
        path = self.data_dir / "news_signals.csv"
        fields = [
            "signal_id",
            "timestamp",
            "token_mint",
            "headline",
            "sentiment_score",
            "confidence",
            "source",
            "summary",
        ]
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            if write_header:
                writer.writeheader()
            for row in signals:
                writer.writerow(row)

    # ------------------------------------------------------------------ internals
    def _validate_db(self) -> None:
        if not self.sqlite_path.exists():
            raise FileNotFoundError(
                f"SQLite database not found at {self.sqlite_path}. "
                "Ensure upstream ingestion has populated user_data.db."
            )

    def _load_dataframes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        with sqlite3.connect(self.sqlite_path) as conn:
            try:
                time_series = pd.read_sql_query(
                    "SELECT token_mint, timestamp, open, high, low, close, volume, momentum, volatility "
                    "FROM time_series",
                    conn,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to read time_series from SQLite: %s", e)
                time_series = pd.DataFrame()

            try:
                catalog = pd.read_sql_query(
                    "SELECT token_mint, name, symbol, bonding_curve_phase, risk_score, "
                    "liquidity_score, volatility_score, whale_concentration, last_updated "
                    "FROM token_strategy_catalog",
                    conn,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to read token_strategy_catalog from SQLite: %s", e)
                catalog = pd.DataFrame()

        if not time_series.empty and "timestamp" in time_series.columns:
            time_series["timestamp"] = pd.to_datetime(time_series["timestamp"], utc=True, errors="coerce")
            time_series = time_series.dropna(subset=["timestamp"])

        return time_series, catalog

