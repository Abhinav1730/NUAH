from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

import pandas as pd


@dataclass
class TokenNewsContext:
    token_mint: str
    name: str
    symbol: str
    momentum: float
    volatility: float
    risk_score: float


def build_token_contexts(
    time_series: pd.DataFrame, token_catalog: pd.DataFrame, limit: int
) -> List[TokenNewsContext]:
    if time_series.empty:
        return []

    latest = (
        time_series.sort_values("timestamp")
        .groupby("token_mint")
        .tail(1)
        .reset_index(drop=True)
    )
    rows: List[TokenNewsContext] = []

    for _, row in latest.iterrows():
        token_mint = row["token_mint"]
        catalog_row = (
            token_catalog[token_catalog["token_mint"] == token_mint].iloc[0]
            if not token_catalog.empty
            else None
        )
        rows.append(
            TokenNewsContext(
                token_mint=token_mint,
                name=(catalog_row["name"] if catalog_row is not None else token_mint),
                symbol=(
                    catalog_row["symbol"] if catalog_row is not None else "TKN"
                ),
                momentum=float(row.get("momentum", 0.0)),
                volatility=float(row.get("volatility", 0.0)),
                risk_score=float(
                    catalog_row["risk_score"] if catalog_row is not None else 0.5
                ),
            )
        )

    rows.sort(key=lambda ctx: ctx.momentum, reverse=True)
    return rows[:limit]


def build_prompt(contexts: Iterable[TokenNewsContext]) -> str:
    blocks = []
    for ctx in contexts:
        blocks.append(
            f"""Token: {ctx.name} ({ctx.symbol})
Mint: {ctx.token_mint}
1h momentum: {ctx.momentum:.3f}
volatility: {ctx.volatility:.3f}
risk_score: {ctx.risk_score:.2f}"""
        )
    return "\n\n".join(blocks)


def fallback_signals(
    contexts: Iterable[TokenNewsContext],
    iso_timestamp: str,
) -> List[Dict]:
    signals: List[Dict] = []
    for idx, ctx in enumerate(contexts, start=1):
        # map momentum [-1,1] to sentiment [-1,1]
        sentiment = max(-1.0, min(1.0, ctx.momentum * 2.5))
        confidence = 0.55 + min(0.35, abs(ctx.momentum))
        summary = (
            "Momentum-driven optimistic outlook"
            if sentiment > 0
            else "Momentum-driven caution signal"
        )
        signals.append(
            {
                "signal_id": f"NEWS-FALLBACK-{idx:03d}",
                "timestamp": iso_timestamp,
                "token_mint": ctx.token_mint,
                "headline": f"{ctx.name} auto-generated sentiment",
                "sentiment_score": round(sentiment, 3),
                "confidence": round(confidence, 3),
                "source": "fallback",
                "summary": summary,
            }
        )
    return signals

