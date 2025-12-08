from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from ..models.rule_evaluator import TradeDecision


class TradeState(TypedDict, total=False):
    user_id: int
    snapshot: Dict[str, Any]
    context: Dict[str, Any]
    features: Dict[str, Any]
    rule_result: Dict[str, Any]
    ml_signal: Dict[str, Any]
    sentiment: Dict[str, Any]
    risk: Dict[str, Any]
    decision: TradeDecision
    errors: List[str]
    metadata: Dict[str, Any]


