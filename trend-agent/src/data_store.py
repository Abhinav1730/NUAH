from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd


class TrendDataStore:
    signals_fields = [
        "signal_id",
        "timestamp",
        "token_mint",
        "trend_score",
        "stage",
        "volatility_flag",
        "liquidity_flag",
        "confidence",
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

    def load_catalog(self) -> pd.DataFrame:
        path = self.data_dir / "token_strategy_catalog.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def save_catalog(self, df: pd.DataFrame) -> None:
        path = self.data_dir / "token_strategy_catalog.csv"
        df.to_csv(path, index=False)

    def append_trend_signals(self, rows: Iterable[Dict]) -> None:
        path = self.data_dir / "trend_signals.csv"
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=self.signals_fields)
            if write_header:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)

