from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd


class SharedDataStore:
    """
    Thin helper around the shared CSV directory.
    """

    news_fields = [
        "signal_id",
        "timestamp",
        "token_mint",
        "headline",
        "sentiment_score",
        "confidence",
        "source",
        "summary",
    ]

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_time_series(self) -> pd.DataFrame:
        path = self.data_dir / "time_series.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def load_token_catalog(self) -> pd.DataFrame:
        path = self.data_dir / "token_strategy_catalog.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def append_news_signals(self, rows: Iterable[Dict]) -> None:
        path = self.data_dir / "news_signals.csv"
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=self.news_fields)
            if write_header:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)

    @staticmethod
    def iso_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

