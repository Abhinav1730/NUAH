from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional, List

import joblib
import numpy as np

from .feature_engineer import FeatureEngineer
from .rule_evaluator import TradeDecision, RuleEvaluator

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    Loads pre-trained models and produces trade decisions.
    Falls back to deterministic rules when models are unavailable.
    """

    def __init__(
        self,
        models_dir: Path,
        feature_engineer: FeatureEngineer,
        rule_fallback: RuleEvaluator,
    ):
        self.models_dir = Path(models_dir)
        self.feature_engineer = feature_engineer
        self.rule_fallback = rule_fallback
        self.action_model = self._load_model("action_model.pkl")
        self.amount_model = self._load_model("amount_model.pkl")
        self.confidence_model = self._load_model("confidence_model.pkl")
        self.feature_columns = self._load_feature_columns()

    def predict(
        self,
        user_id: int,
        snapshot: Dict,
        base_features: Dict,
        context: Dict,
        sentiment: Dict,
    ) -> TradeDecision:
        ml_features = self.feature_engineer.build(
            user_id=user_id,
            snapshot=snapshot,
            context=context,
            base_features=base_features,
            sentiment=sentiment,
        )
        if not self._models_ready():
            logger.debug("ML models unavailable; falling back to rule evaluator.")
            return self.rule_fallback.evaluate(
                user_id=user_id,
                snapshot=snapshot,
                features={**base_features, **ml_features},
                context=context,
                sentiment=sentiment,
            )

        feature_vector = self._dict_to_vector(ml_features)
        action = self._predict_action(feature_vector, user_id)
        amount = self._predict_amount(feature_vector)
        confidence = self._predict_confidence(feature_vector)

        return TradeDecision(
            user_id=user_id,
            action=action,
            token_mint=self._select_token(context),
            amount=amount,
            confidence=confidence,
            reason="ML ensemble decision",
        )

    # ------------------------------------------------------------------ #

    def _load_model(self, filename: str):
        path = self.models_dir / filename
        if not path.exists():
            return None
        try:
            return joblib.load(path)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load model %s", path)
            return None

    def _load_feature_columns(self) -> Optional[List[str]]:
        path = self.models_dir / "feature_columns.pkl"
        if not path.exists():
            return None
        try:
            return joblib.load(path)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load feature columns metadata.")
            return None

    def _models_ready(self) -> bool:
        return all([self.action_model, self.amount_model, self.confidence_model])

    def _dict_to_vector(self, features: Dict[str, float]):
        if not features:
            return np.zeros((1, 1))
        if self.feature_columns:
            ordered_keys = self.feature_columns
        else:
            ordered_keys = sorted(features.keys())
        return np.array([[features.get(key, 0.0) for key in ordered_keys]])

    def _predict_action(self, vector, user_id: int):
        proba = self.action_model.predict_proba(vector)[0]
        classes = list(self.action_model.classes_)
        idx = int(np.argmax(proba))
        return classes[idx]

    def _predict_amount(self, vector):
        amount = float(self.amount_model.predict(vector)[0])
        return max(amount, 0.0)

    def _predict_confidence(self, vector):
        confidence = float(self.confidence_model.predict(vector)[0])
        return float(min(max(confidence, 0.0), 0.99))

    def _select_token(self, context: Dict) -> Optional[str]:
        tokens = context.get("tokens", [])
        if tokens:
            return tokens[0]
        catalog = context.get("token_catalog") or []
        if catalog:
            return catalog[0].get("token_mint")
        return None

