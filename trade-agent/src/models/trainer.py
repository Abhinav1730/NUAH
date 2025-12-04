from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split

from .feature_engineer import FeatureEngineer

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    data_dir: Path
    models_dir: Path
    test_size: float = 0.2


class MLTrainer:
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.feature_engineer = FeatureEngineer()
        self.config.models_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> None:
        dataset = self._build_dataset()
        if dataset.empty:
            logger.warning("No training data available; aborting.")
            return
        feature_cols = sorted(col for col in dataset.columns if col.startswith("feat_"))
        if not feature_cols:
            logger.warning("Dataset missing feature columns; aborting.")
            return
        joblib.dump(feature_cols, self.config.models_dir / "feature_columns.pkl")
        X = dataset[feature_cols]
        y_action = dataset["target_action"]
        y_amount = dataset["target_amount"]
        y_confidence = dataset["target_confidence"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y_action, test_size=self.config.test_size, random_state=42, stratify=y_action
        )
        base_clf = LGBMClassifier(num_leaves=31, learning_rate=0.05, n_estimators=200)
        action_model = CalibratedClassifierCV(base_clf, method="isotonic", cv=3)
        action_model.fit(X_train, y_train)
        logger.info("Action model accuracy: %.2f", action_model.score(X_test, y_test))
        joblib.dump(action_model, self.config.models_dir / "action_model.pkl")

        amount_model = LGBMRegressor(num_leaves=31, learning_rate=0.05, n_estimators=200)
        amount_model.fit(X, y_amount)
        joblib.dump(amount_model, self.config.models_dir / "amount_model.pkl")

        confidence_model = LGBMRegressor(num_leaves=31, learning_rate=0.05, n_estimators=200)
        confidence_model.fit(X, y_confidence)
        joblib.dump(confidence_model, self.config.models_dir / "confidence_model.pkl")
        logger.info("Saved models to %s", self.config.models_dir)

    def _build_dataset(self) -> pd.DataFrame:
        trades = self._load_csv("historical_trades")
        if trades.empty:
            return trades
        time_series = self._load_csv("time_series")
        news = self._load_csv("news_signals")
        trend = self._load_csv("trend_signals")
        catalog = self._load_csv("token_strategy_catalog")

        feature_rows: List[Dict] = []
        for _, trade in trades.iterrows():
            token = trade["token_mint"]
            ts = time_series[time_series["token_mint"] == token]
            context = {
                "time_series": ts.to_dict("records"),
                "historical_trades": trades[
                    (trades["user_id"] == trade["user_id"]) & (trades["timestamp"] <= trade["timestamp"])
                ].tail(25).to_dict("records"),
                "token_catalog": catalog[catalog["token_mint"] == token].to_dict("records"),
                "news_signals": news[news["token_mint"] == token].to_dict("records"),
                "trend_signals": trend[trend["token_mint"] == token].to_dict("records"),
                "tokens": [token],
            }
            base_features = {
                "portfolio_value_ndollar": float(trade.get("price", 0)) * 10,
                "deployable_ndollar": float(trade.get("price", 0)) * 2,
                "token_count": 3,
                "trades_today": 1,
            }
            sentiment = {
                "score": float(np.random.uniform(-0.1, 0.1)),
                "confidence": 0.6,
            }
            features = self.feature_engineer.build(
                user_id=int(trade["user_id"]),
                snapshot={},
                context=context,
                base_features=base_features,
                sentiment=sentiment,
            )
            row = {f"feat_{k}": v for k, v in features.items()}
            row["target_action"] = trade["action"]
            row["target_amount"] = float(trade["amount"])
            row["target_confidence"] = float(trade.get("confidence", 0.6))
            feature_rows.append(row)

        dataset = pd.DataFrame(feature_rows)
        dataset.fillna(0, inplace=True)
        return dataset

    def _load_csv(self, name: str) -> pd.DataFrame:
        path = self.config.data_dir / f"{name}.csv"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df

