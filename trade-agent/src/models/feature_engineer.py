from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class FeatureEngineer:
    """
    Builds numerical features consumed by ML models.
    """

    rolling_window: int = 4

    def build(
        self,
        user_id: int,
        snapshot: Dict,
        context: Dict,
        base_features: Dict,
        sentiment: Dict,
    ) -> Dict[str, float]:
        features: Dict[str, float] = {}
        features.update(self._portfolio_features(base_features))
        features.update(self._time_series_features(context.get("time_series", [])))
        features.update(self._historical_trade_features(context.get("historical_trades", [])))
        features.update(self._sentiment_features(sentiment))
        features.update(self._token_catalog_features(context.get("token_catalog", [])))
        features["user_id_mod"] = float(user_id % 100) / 100.0
        return {k: float(v) for k, v in features.items() if pd.notna(v)}

    def _portfolio_features(self, base_features: Dict) -> Dict[str, float]:
        return {
            "portfolio_value": float(base_features.get("portfolio_value_ndollar", 0.0)),
            "deployable_value": float(base_features.get("deployable_ndollar", 0.0)),
            "token_count": float(base_features.get("token_count", 0)),
            "trades_today": float(base_features.get("trades_today", 0)),
        }

    def _time_series_features(self, rows: List[Dict]) -> Dict[str, float]:
        if not rows:
            return {
                "ts_momentum_mean": 0.0,
                "ts_volatility_mean": 0.0,
                "ts_volume_mean": 0.0,
            }
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp")
        tail = df.tail(self.rolling_window)
        return {
            "ts_momentum_mean": float(tail["momentum"].mean()),
            "ts_volatility_mean": float(tail["volatility"].mean()),
            "ts_volume_mean": float(tail["volume"].mean()),
            "ts_close_mean": float(tail["close"].mean()),
        }

    def _historical_trade_features(self, rows: List[Dict]) -> Dict[str, float]:
        if not rows:
            return {"hist_win_rate": 0.5, "hist_avg_pnl": 0.0}
        df = pd.DataFrame(rows)
        df["pnl"] = pd.to_numeric(df.get("pnl"), errors="coerce")
        wins = df["pnl"] > 0
        return {
            "hist_win_rate": float(wins.mean()),
            "hist_avg_pnl": float(df["pnl"].mean()),
        }

    def _sentiment_features(self, sentiment: Optional[Dict]) -> Dict[str, float]:
        sentiment = sentiment or {}
        return {
            "sentiment_score": float(sentiment.get("score", 0.0)),
            "sentiment_confidence": float(sentiment.get("confidence", 0.0)),
        }

    def _token_catalog_features(self, rows: List[Dict]) -> Dict[str, float]:
        if not rows:
            return {
                "token_risk_score": 0.5,
                "token_liquidity_score": 0.6,
                "token_volatility_score": 0.5,
            }
        df = pd.DataFrame(rows)
        row = df.iloc[0]
        return {
            "token_risk_score": float(row.get("risk_score", 0.5)),
            "token_liquidity_score": float(row.get("liquidity_score", 0.6)),
            "token_volatility_score": float(row.get("volatility_score", 0.5)),
        }

