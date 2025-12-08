from __future__ import annotations

import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd

from .config import RulesAgentSettings
from .deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)


class RulesAgentPipeline:
    """
    Builds per-user rule evaluations by combining:
      - token catalog + time-series from SQLite (fetch-data-agent DB)
      - news signals (CSV)
      - trend signals (CSV)
      - rules.csv and user_preferences.csv
    Delegates final allow/limits decision to DeepSeek.
    """

    def __init__(
        self,
        settings: RulesAgentSettings,
        sqlite_path: Optional[Path] = None,
        data_dir: Optional[Path] = None,
    ) -> None:
        self.settings = settings
        self.sqlite_path = Path(sqlite_path or "../fetch-data-agent/data/user_data.db").resolve()
        self.data_dir = Path(data_dir or settings.data_dir).resolve()
        self.client = DeepSeekClient(settings)
        self._validate_sources()

    def run(self) -> List[Dict]:
        catalog, ts = self._load_sqlite_frames()
        rules_df, prefs_df = self._load_rules_and_prefs()
        news_df = self._load_csv_optional("news_signals.csv")
        trend_df = self._load_csv_optional("trend_signals.csv")

        evaluations: List[Dict] = []
        iso_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        for _, pref in prefs_df.iterrows():
            user_id = int(pref["user_id"])
            allowed_tokens = self._parse_tokens(pref.get("allowed_tokens", ""))
            blocked_tokens = set(self._parse_tokens(pref.get("blocked_tokens", "")))

            # Build token contexts for this user
            token_contexts = []
            for token in allowed_tokens:
                if token in blocked_tokens:
                    continue
                token_row = catalog[catalog["token_mint"] == token].iloc[0] if not catalog.empty and token in catalog["token_mint"].values else None
                ts_rows = ts[ts["token_mint"] == token].sort_values("timestamp")
                news_rows = news_df[news_df["token_mint"] == token] if news_df is not None else pd.DataFrame()
                trend_rows = trend_df[trend_df["token_mint"] == token] if trend_df is not None else pd.DataFrame()

                token_contexts.append(
                    {
                        "token_mint": token,
                        "risk_score": float(token_row["risk_score"]) if token_row is not None else 0.5,
                        "liquidity_score": float(token_row["liquidity_score"]) if token_row is not None else 0.5,
                        "volatility_score": float(token_row["volatility_score"]) if token_row is not None else 0.5,
                        "momentum": float(ts_rows["momentum"].iloc[-1]) if not ts_rows.empty and "momentum" in ts_rows.columns else 0.0,
                        "news_sentiment": float(news_rows["sentiment_score"].iloc[-1]) if not news_rows.empty and "sentiment_score" in news_rows.columns else 0.0,
                        "trend_score": float(trend_rows["trend_score"].iloc[-1]) if not trend_rows.empty and "trend_score" in trend_rows.columns else 0.0,
                    }
                )

            if not token_contexts:
                logger.warning("No tokens to evaluate for user %s", user_id)
                continue

            prompt = self._build_prompt(pref, token_contexts)
            decisions = self.client.structured_completion(*prompt)
            if not decisions:
                logger.warning("LLM returned no decisions for user %s", user_id)
                continue

            for dec in decisions:
                token = dec.get("token_mint")
                if not token or token not in allowed_tokens or token in blocked_tokens:
                    continue
                evaluations.append(
                    {
                        "evaluation_id": dec.get("evaluation_id") or f"RULE-{user_id}-{token}",
                        "timestamp": iso_now,
                        "user_id": user_id,
                        "token_mint": token,
                        "allowed": bool(dec.get("allowed", True)),
                        "max_daily_trades": int(dec.get("max_daily_trades", pref.get("max_trades_per_day", 3))),
                        "max_position_ndollar": float(dec.get("max_position_ndollar", pref.get("max_position_ndollar", 1000))),
                        "reason": dec.get("reason", "LLM evaluation"),
                        "confidence": float(dec.get("confidence", 0.7)),
                    }
                )

        if evaluations:
            self._write_evaluations(evaluations)
        else:
            logger.warning("No rule evaluations generated.")
        return evaluations

    # ------------------------------------------------------------------ helpers
    def _build_prompt(self, pref_row, token_contexts: List[Dict]) -> tuple[str, str]:
        system_prompt = (
            "You are a risk-policy translator. Given user preferences and token analytics, "
            "decide per token: allowed (bool), max_daily_trades, max_position_ndollar, reason, confidence (0..1). "
            "Respond with JSON array."
        )
        pref_text = (
            f"user_id={pref_row['user_id']}, "
            f"risk_profile={pref_row.get('risk_profile','balanced')}, "
            f"max_trades_per_day={pref_row.get('max_trades_per_day',3)}, "
            f"max_position_ndollar={pref_row.get('max_position_ndollar',1000)}"
        )
        user_prompt = (
            f"User preferences: {pref_text}\n"
            f"Tokens with metrics:\n{json.dumps(token_contexts, ensure_ascii=False, indent=2)}"
        )
        return system_prompt, user_prompt

    def _write_evaluations(self, rows: List[Dict]) -> None:
        path = self.data_dir / "rule_evaluations.csv"
        fields = [
            "evaluation_id",
            "timestamp",
            "user_id",
            "token_mint",
            "allowed",
            "max_daily_trades",
            "max_position_ndollar",
            "reason",
            "confidence",
        ]
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            if write_header:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _load_sqlite_frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        with sqlite3.connect(self.sqlite_path) as conn:
            try:
                ts = pd.read_sql_query(
                    "SELECT token_mint, timestamp, momentum, volatility FROM time_series",
                    conn,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to read time_series: %s", e)
                ts = pd.DataFrame()

            try:
                catalog = pd.read_sql_query(
                    "SELECT token_mint, name, symbol, bonding_curve_phase, risk_score, "
                    "liquidity_score, volatility_score, whale_concentration, last_updated "
                    "FROM token_strategy_catalog",
                    conn,
                )
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to read token_strategy_catalog: %s", e)
                catalog = pd.DataFrame()

        if not ts.empty and "timestamp" in ts.columns:
            ts["timestamp"] = pd.to_datetime(ts["timestamp"], utc=True, errors="coerce")
            ts = ts.dropna(subset=["timestamp"])
        return catalog, ts

    def _load_rules_and_prefs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        rules_path = self.data_dir / "rules.csv"
        prefs_path = self.data_dir / "user_preferences.csv"
        if not rules_path.exists() or not prefs_path.exists():
            raise FileNotFoundError("rules.csv or user_preferences.csv missing in data_dir.")
        rules_df = pd.read_csv(rules_path)
        prefs_df = pd.read_csv(prefs_path)
        return rules_df, prefs_df

    def _load_csv_optional(self, name: str) -> Optional[pd.DataFrame]:
        path = self.data_dir / name
        if not path.exists():
            return None
        try:
            return pd.read_csv(path)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to read %s: %s", name, e)
            return None

    @staticmethod
    def _parse_tokens(value: str) -> List[str]:
        if not value:
            return []
        return [t.strip() for t in str(value).split("|") if t.strip()]

