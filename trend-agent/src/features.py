from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import pandas as pd


@dataclass
class TrendContext:
    token_mint: str
    momentum: float
    volatility: float
    volume: float
    close: float


def build_trend_contexts(time_series: pd.DataFrame, limit: int) -> List[TrendContext]:
    if time_series.empty:
        return []
    latest = (
        time_series.sort_values("timestamp")
        .groupby("token_mint")
        .tail(1)
        .reset_index(drop=True)
    )
    contexts: List[TrendContext] = []
    for _, row in latest.iterrows():
        contexts.append(
            TrendContext(
                token_mint=row["token_mint"],
                momentum=float(row.get("momentum", 0.0)),
                volatility=float(row.get("volatility", 0.0)),
                volume=float(row.get("volume", 0.0)),
                close=float(row.get("close", 0.0)),
            )
        )
    contexts.sort(key=lambda ctx: ctx.momentum, reverse=True)
    return contexts[:limit]


def fallback_signals(contexts: Iterable[TrendContext], iso_now: str) -> List[dict]:
    signals = []
    for idx, ctx in enumerate(contexts, start=1):
        trend_score = max(-1.0, min(1.0, ctx.momentum * 2))
        stage = (
            "early"
            if ctx.momentum > 0.05
            else "mid"
            if ctx.momentum > -0.02
            else "late"
        )
        volatility_flag = "high" if ctx.volatility > 0.12 else "moderate"
        liquidity_flag = "thin" if ctx.volume < 7000 else "healthy"
        signals.append(
            {
                "signal_id": f"TREND-FALLBACK-{idx:03d}",
                "timestamp": iso_now,
                "token_mint": ctx.token_mint,
                "trend_score": round(trend_score, 3),
                "stage": stage,
                "volatility_flag": volatility_flag,
                "liquidity_flag": liquidity_flag,
                "confidence": 0.6,
                "summary": f"Heuristic stage={stage}, vol={volatility_flag}, liq={liquidity_flag}",
            }
        )
    return signals

