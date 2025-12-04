from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd


def _parse_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


@dataclass
class ContextBundle:
    news_signals: List[dict]
    trend_signals: List[dict]
    rule_evaluations: List[dict]
    user_preferences: Optional[dict]
    token_catalog: List[dict]
    time_series: List[dict]
    historical_trades: List[dict]


class CSVDataLoader:
    """
    Loads shared CSV datasets produced by the auxiliary agents.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, pd.DataFrame] = {}

    def build_context(
        self,
        user_id: int,
        tokens: Sequence[str],
        *,
        news_freshness: int,
        trend_freshness: int,
    ) -> ContextBundle:
        token_set = set(tokens)
        return ContextBundle(
            news_signals=self._latest_signals(
                "news_signals",
                token_set,
                freshness_minutes=news_freshness,
            ),
            trend_signals=self._latest_signals(
                "trend_signals",
                token_set,
                freshness_minutes=trend_freshness,
            ),
            rule_evaluations=self._rule_evaluations(user_id, token_set),
            user_preferences=self._user_preferences(user_id),
            token_catalog=self._filter_tokens("token_strategy_catalog", token_set),
            time_series=self._filter_tokens("time_series", token_set),
            historical_trades=self._historical_trades(user_id, limit=25),
        )

    # --- internal helpers -------------------------------------------------

    def _read_csv(self, name: str) -> pd.DataFrame:
        if name in self._cache:
            return self._cache[name]
        path = self.data_dir / f"{name}.csv"
        if not path.exists():
            df = pd.DataFrame()
        else:
            df = pd.read_csv(path)
        self._cache[name] = df
        return df

    def _latest_signals(
        self,
        name: str,
        tokens: Iterable[str],
        *,
        freshness_minutes: int,
    ) -> List[dict]:
        df = self._read_csv(name)
        if df.empty or not tokens:
            return []
        df = df[df["token_mint"].isin(tokens)].copy()
        if df.empty:
            return []
        df["timestamp"] = _parse_timestamp(df["timestamp"])
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=freshness_minutes)
        df = df[df["timestamp"] >= cutoff]
        if df.empty:
            return []
        df = df.sort_values("timestamp", ascending=False)
        records = df.to_dict("records")
        # Cast timestamp back to iso strings
        for record in records:
            stamp = record.get("timestamp")
            if isinstance(stamp, pd.Timestamp):
                record["timestamp"] = stamp.isoformat()
        return records

    def _rule_evaluations(self, user_id: int, tokens: Iterable[str]) -> List[dict]:
        df = self._read_csv("rule_evaluations")
        if df.empty:
            return []
        df = df[df["user_id"] == user_id]
        if tokens:
            df = df[df["token_mint"].isin(tokens)]
        return df.to_dict("records")

    def _user_preferences(self, user_id: int) -> Optional[dict]:
        df = self._read_csv("user_preferences")
        if df.empty:
            return None
        row = df[df["user_id"] == user_id]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def _filter_tokens(self, name: str, tokens: Iterable[str]) -> List[dict]:
        df = self._read_csv(name)
        if df.empty or not tokens:
            return []
        df = df[df["token_mint"].isin(tokens)]
        return df.to_dict("records")

    def _historical_trades(self, user_id: int, limit: int) -> List[dict]:
        df = self._read_csv("historical_trades")
        if df.empty:
            return []
        df = df[df["user_id"] == user_id]
        if df.empty:
            return []
        df["timestamp"] = _parse_timestamp(df["timestamp"])
        df = df.sort_values("timestamp", ascending=False).head(limit)
        records = df.to_dict("records")
        for rec in records:
            stamp = rec.get("timestamp")
            if isinstance(stamp, pd.Timestamp):
                rec["timestamp"] = stamp.isoformat()
        return records

