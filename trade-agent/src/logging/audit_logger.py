from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

from ..models.rule_evaluator import TradeDecision


class AuditLogger:
    """
    Persists executed (or skipped) trades for downstream analytics.
    """

    fields = [
        "trade_id",
        "user_id",
        "token_mint",
        "action",
        "amount",
        "price",
        "timestamp",
        "pnl",
        "slippage",
        "risk_score",
        "confidence",
        "notes",
    ]

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "historical_trades.csv"

    def log(self, decision: TradeDecision, metadata: Dict[str, str]) -> None:
        write_header = not self.path.exists() or self.path.stat().st_size == 0
        row = {
            "trade_id": metadata.get("trade_id"),
            "user_id": decision.user_id,
            "token_mint": decision.token_mint,
            "action": decision.action,
            "amount": decision.amount,
            "price": metadata.get("price"),
            "timestamp": metadata.get("timestamp"),
            "pnl": metadata.get("pnl"),
            "slippage": metadata.get("slippage"),
            "risk_score": metadata.get("risk_score"),
            "confidence": decision.confidence,
            "notes": decision.reason,
        }
        with self.path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=self.fields)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

