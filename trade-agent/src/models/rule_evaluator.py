from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


Action = Literal["buy", "sell", "hold"]


@dataclass
class TradeDecision:
    user_id: int
    action: Action
    token_mint: Optional[str]
    amount: Optional[float]
    confidence: float
    reason: str


class RuleEvaluator:
    """
    Deterministic heuristic layer that runs before LLM fusion.
    """

    def __init__(self, min_ndollar_balance: float = 50.0, max_positions: int = 5):
        self.min_ndollar_balance = min_ndollar_balance
        self.max_positions = max_positions

    def evaluate(
        self,
        *,
        user_id: int,
        snapshot: Dict[str, Any],
        features: Dict[str, Any],
        context: Dict[str, Any],
        sentiment: Dict[str, Any],
    ) -> TradeDecision:
        portfolio_value = float(features.get("portfolio_value_ndollar") or 0.0)
        if portfolio_value < self.min_ndollar_balance:
            return self._hold(user_id, "Insufficient N-Dollar balance.")

        token_count = int(features.get("token_count") or 0)
        if token_count >= self.max_positions:
            token = self._select_existing_token(snapshot)
            return TradeDecision(
                user_id=user_id,
                action="sell",
                token_mint=token,
                amount=round((features.get("deployable_ndollar") or 0) * 0.3, 4),
                confidence=0.55,
                reason="Rebalance: portfolio saturated.",
            )

        candidate = self._select_candidate_token(context)
        if not candidate:
            return self._hold(user_id, "No candidate tokens available.")

        trend_score = float(candidate.get("trend_score", 0.0))
        sentiment_score = float(sentiment.get("score", 0.0))
        combined = trend_score + 0.4 * sentiment_score
        action: Action = "hold"
        if combined > 0.1:
            action = "buy"
        elif combined < -0.15:
            action = "sell"

        amount = round(
            min(
                (features.get("deployable_ndollar") or 0.0) * min(0.6, abs(combined)),
                5000,
            ),
            4,
        )
        confidence = min(0.9, 0.55 + abs(combined))
        reason = (
            f"Trend score {trend_score:.2f} with sentiment {sentiment_score:.2f} "
            f"yielding combined {combined:.2f}."
        )

        return TradeDecision(
            user_id=user_id,
            action=action,
            token_mint=candidate.get("token_mint"),
            amount=amount if amount > 0 else None,
            confidence=confidence,
            reason=reason,
        )

    @staticmethod
    def _select_existing_token(snapshot: Dict[str, Any]) -> Optional[str]:
        portfolio = snapshot.get("portfolio") or {}
        tokens = portfolio.get("tokens") or []
        if not tokens:
            return None
        richest = max(
            tokens,
            key=lambda token: float(token.get("value_ndollar") or token.get("balance") or 0.0),
        )
        return richest.get("mint_address") or richest.get("token_mint")

    @staticmethod
    def _select_candidate_token(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        trend = context.get("trend_signals") or []
        if trend:
            trend = sorted(trend, key=lambda item: item.get("trend_score", 0), reverse=True)
            return trend[0]
        tokens = context.get("token_catalog") or []
        if tokens:
            tokens = sorted(
                tokens,
                key=lambda item: float(item.get("risk_score", 0.5)),
            )
            best = tokens[0]
            return {
                "token_mint": best.get("token_mint"),
                "trend_score": 0.05,
            }
        return None

    @staticmethod
    def _hold(user_id: int, reason: str) -> TradeDecision:
        return TradeDecision(
            user_id=user_id,
            action="hold",
            token_mint=None,
            amount=None,
            confidence=0.4,
            reason=reason,
        )

