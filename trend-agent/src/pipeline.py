from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import pandas as pd

from .cache_manager import CacheManager
from .config import TrendAgentSettings
from .data_store import TrendDataStore
from .deepseek_client import DeepSeekClient
from .features import TrendContext, build_trend_contexts, fallback_signals

logger = logging.getLogger(__name__)


class TrendAgentPipeline:
    def __init__(self, settings: TrendAgentSettings):
        self.settings = settings
        self.store = TrendDataStore(settings.data_dir)
        self.client = DeepSeekClient(settings)
        self.cache = CacheManager(settings.cache_dir, settings.cache_ttl_hours)

    def run(self) -> List[dict]:
        time_series = self.store.load_time_series()
        contexts = build_trend_contexts(time_series, self.settings.max_tokens)
        if not contexts:
            logger.warning("No time-series data available for trend analysis.")
            return []

        iso_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        signals = self._generate_signals_with_cache(contexts, iso_now, time_series)
        if not signals:
            signals = fallback_signals(contexts, iso_now)

        self.store.append_trend_signals(signals)
        self._refresh_catalog(signals)
        logger.info("Trend agent stored %d signals.", len(signals))
        return signals

    def _generate_signals_with_cache(
        self,
        contexts: Iterable[TrendContext],
        iso_now: str,
        time_series: pd.DataFrame,
    ) -> List[dict]:
        """
        Generate signals with smart caching (Strategy 1).
        Only calls API if significant changes detected or cache expired.
        """
        if self.settings.dry_run:
            return fallback_signals(contexts, iso_now)

        signals = []
        contexts_list = list(contexts)

        for ctx in contexts_list:
            cache_key = f"trend_{ctx.token_mint}"
            cached = self.cache.load_cache(cache_key)

            # Check if we need to call API (Strategy 1: Smart Caching)
            should_call_api = self._should_call_api(ctx, cached, time_series)

            if should_call_api:
                logger.info(
                    f"Calling API for {ctx.token_mint} (change detected or cache expired)"
                )
                signal = self._generate_signal_for_token(ctx, iso_now)
                if signal:
                    signals.append(signal)
                    # Cache the result
                    self.cache.save_cache(
                        cache_key,
                        signal,
                        metadata={
                            "momentum": ctx.momentum,
                            "volatility": ctx.volatility,
                            "volume": ctx.volume,
                            "close": ctx.close,
                        },
                    )
                else:
                    # API failed, use fallback
                    fallback = fallback_signals([ctx], iso_now)
                    signals.extend(fallback)
            else:
                # Use cached result
                if cached and cached.get("data"):
                    cached_signal = cached["data"].copy()
                    cached_signal["timestamp"] = iso_now  # Update timestamp
                    signals.append(cached_signal)
                    logger.debug(f"Using cached signal for {ctx.token_mint}")
                else:
                    # No cache, use fallback
                    fallback = fallback_signals([ctx], iso_now)
                    signals.extend(fallback)

        return signals

    def _should_call_api(
        self,
        ctx: TrendContext,
        cached: Optional[dict],
        time_series: pd.DataFrame,
    ) -> bool:
        """
        Determine if API call is needed based on change detection (Strategy 1).
        
        Returns True if:
        1. No cache exists
        2. Cache expired (> TTL hours)
        3. Momentum changed > threshold since last cache
        4. Volatility > threshold
        """
        if not cached:
            return True  # No cache, need to call

        cached_metadata = cached.get("metadata", {})
        cached_momentum = cached_metadata.get("momentum", 0.0)
        cached_volatility = cached_metadata.get("volatility", 0.0)

        # Check momentum change
        momentum_change = abs(ctx.momentum - cached_momentum)
        if momentum_change >= self.settings.momentum_change_threshold:
            logger.info(
                f"Momentum change detected for {ctx.token_mint}: "
                f"{cached_momentum:.3f} -> {ctx.momentum:.3f} (Δ={momentum_change:.3f})"
            )
            return True

        # Check volatility threshold
        if ctx.volatility >= self.settings.volatility_threshold:
            logger.info(
                f"High volatility detected for {ctx.token_mint}: {ctx.volatility:.3f}"
            )
            return True

        # No significant change, use cache
        return False

    def _generate_signal_for_token(
        self, ctx: TrendContext, iso_now: str
    ) -> Optional[dict]:
        """Generate signal for a single token via API."""
        system_prompt = (
            "You are a DeFi trend analyst. Return JSON object (not array) with fields: "
            "token_mint, trend_score (-1..1), stage (early/mid/late), "
            "volatility_flag (low/moderate/high), liquidity_flag (thin/healthy), summary."
        )
        user_prompt = (
            f"Evaluate the following quantitative snapshot:\n"
            f"{ctx.token_mint}: momentum={ctx.momentum:.3f}, "
            f"volatility={ctx.volatility:.3f}, volume={ctx.volume:.0f}, "
            f"close={ctx.close:.3f}"
        )

        records = self.client.structured_completion(system_prompt, user_prompt)
        if not records:
            return None

        # Handle both array and single object responses
        entry = records[0] if isinstance(records, list) else records
        token = entry.get("token_mint") or ctx.token_mint
        if not token:
            return None

        return {
            "signal_id": entry.get("signal_id") or f"TREND-{uuid.uuid4().hex[:8]}",
            "timestamp": iso_now,
            "token_mint": token,
            "trend_score": float(entry.get("trend_score", 0)),
            "stage": entry.get("stage", "mid"),
            "volatility_flag": entry.get("volatility_flag", "moderate"),
            "liquidity_flag": entry.get("liquidity_flag", "healthy"),
            "confidence": float(entry.get("confidence", 0.65)),
            "summary": entry.get("summary", "No summary."),
        }

    def _refresh_catalog(self, signals: Iterable[dict]) -> None:
        catalog = self.store.load_catalog()
        if catalog.empty:
            catalog = pd.DataFrame(
                columns=[
                    "token_mint",
                    "name",
                    "symbol",
                    "bonding_curve_phase",
                    "risk_score",
                    "creator_reputation",
                    "liquidity_score",
                    "volatility_score",
                    "whale_concentration",
                    "last_updated",
                ]
            )

        catalog = catalog.copy()
        for signal in signals:
            token = signal["token_mint"]
            idx = catalog.index[catalog["token_mint"] == token].tolist()
            risk_score = self._derive_risk(signal)
            liquidity_score = self._derive_liquidity(signal["liquidity_flag"])
            volatility_score = self._derive_volatility(signal["volatility_flag"])
            row = {
                "token_mint": token,
                "bonding_curve_phase": signal["stage"],
                "risk_score": risk_score,
                "liquidity_score": liquidity_score,
                "volatility_score": volatility_score,
                "last_updated": signal["timestamp"],
            }
            if idx:
                for column, value in row.items():
                    if column in catalog.columns:
                        catalog.loc[idx, column] = value
            else:
                # create basic row with placeholders
                catalog = pd.concat(
                    [
                        catalog,
                        pd.DataFrame(
                            [
                                {
                                    **{
                                        "token_mint": token,
                                        "name": token,
                                        "symbol": "TKN",
                                        "creator_reputation": 0.5,
                                        "whale_concentration": 0.3,
                                    },
                                    **row,
                                }
                            ]
                        ),
                    ],
                    ignore_index=True,
                )
        self.store.save_catalog(catalog)

    @staticmethod
    def _derive_risk(signal: dict) -> float:
        base = 0.5 - 0.3 * signal["trend_score"]
        if signal["stage"] == "late":
            base += 0.1
        if signal["volatility_flag"] == "high":
            base += 0.1
        return max(0.0, min(1.0, base))

    @staticmethod
    def _derive_liquidity(flag: str) -> float:
        mapping = {"thin": 0.45, "moderate": 0.6, "healthy": 0.8}
        return mapping.get(flag, 0.6)

    @staticmethod
    def _derive_volatility(flag: str) -> float:
        mapping = {"low": 0.3, "moderate": 0.5, "high": 0.8}
        return mapping.get(flag, 0.5)

