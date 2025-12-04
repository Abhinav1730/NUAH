from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pandas as pd


class RulesDataStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_rules(self) -> pd.DataFrame:
        path = self.data_dir / "rules.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def load_user_preferences(self) -> pd.DataFrame:
        path = self.data_dir / "user_preferences.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def load_token_catalog(self) -> pd.DataFrame:
        path = self.data_dir / "token_strategy_catalog.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def write_evaluations(self, rows: Iterable[dict]) -> None:
        df = pd.DataFrame(rows)
        path = self.data_dir / "rule_evaluations.csv"
        df.to_csv(path, index=False)

