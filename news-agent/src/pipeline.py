from __future__ import annotations

import logging
import uuid
from typing import Iterable, List, Optional

from .cache_manager import CacheManager
from .config import NewsAgentSettings
from .data_store import SharedDataStore
from .deepseek_client import DeepSeekClient
from .generators import (
    TokenNewsContext,
    build_prompt,
    build_token_contexts,
    fallback_signals,
)

logger = logging.getLogger(__name__)


class NewsAgentPipeline:
    def __init__(self, settings: NewsAgentSettings):
        self.settings = settings
        self.store = SharedDataStore(settings.data_dir)
        self.deepseek = DeepSeekClient(settings)
        self.cache = CacheManager(settings.cache_dir, settings.cache_ttl_hours)

    def run(self, token_filter: Optional[List[str]] = None) -> List[dict]:
        time_series = self.store.load_time_series()
        token_catalog = self.store.load_token_catalog()
        contexts = build_token_contexts(
            time_series, token_catalog, self.settings.top_tokens
        )

        if token_filter:
            contexts = [ctx for ctx in contexts if ctx.token_mint in set(token_filter)]

        if not contexts:
            logger.warning("No token contexts available for news generation.")
            return []

        iso_now = self.store.iso_now()
        signals = self._generate_signals_with_cache(contexts, iso_now, time_series)
        if not signals:
            logger.warning("Failed to generate sentiments; storing fallback signals.")
            signals = fallback_signals(contexts, iso_now)

        self.store.append_news_signals(signals)
        logger.info("Stored %d news signals.", len(signals))
        return signals

    def _generate_signals_with_cache(
        self,
        contexts: Iterable[TokenNewsContext],
        iso_now: str,
        time_series,
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
            cache_key = f"news_{ctx.token_mint}"
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
                            "risk_score": ctx.risk_score,
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
                    cached_signal["source"] = "cached"
                    signals.append(cached_signal)
                    logger.debug(f"Using cached signal for {ctx.token_mint}")
                else:
                    # No cache, use fallback
                    fallback = fallback_signals([ctx], iso_now)
                    signals.extend(fallback)

        return signals

    def _should_call_api(
        self,
        ctx: TokenNewsContext,
        cached: Optional[dict],
        time_series,
    ) -> bool:
        """
        Determine if API call is needed based on change detection (Strategy 1).
        
        Returns True if:
        1. No cache exists
        2. Cache expired (> TTL hours)
        3. Momentum changed > threshold since last cache
        4. Volume spike detected (> threshold)
        """
        if not cached:
            return True  # No cache, need to call

        # Check if cache expired
        # (Already handled by CacheManager.load_cache, but double-check)
        cached_metadata = cached.get("metadata", {})
        cached_momentum = cached_metadata.get("momentum", 0.0)

        # Check momentum change
        momentum_change = abs(ctx.momentum - cached_momentum)
        if momentum_change >= self.settings.momentum_change_threshold:
            logger.info(
                f"Momentum change detected for {ctx.token_mint}: "
                f"{cached_momentum:.3f} -> {ctx.momentum:.3f} (Δ={momentum_change:.3f})"
            )
            return True

        # Check volume spike (if time_series available)
        if not time_series.empty:
            token_ts = time_series[time_series["token_mint"] == ctx.token_mint]
            if not token_ts.empty:
                latest_volume = float(token_ts.iloc[-1].get("volume", 0))
                if len(token_ts) > 1:
                    prev_volume = float(token_ts.iloc[-2].get("volume", 0))
                    if prev_volume > 0:
                        volume_change = (latest_volume - prev_volume) / prev_volume
                        if abs(volume_change) >= self.settings.volume_spike_threshold:
                            logger.info(
                                f"Volume spike detected for {ctx.token_mint}: "
                                f"{volume_change:.1%} change"
                            )
                            return True

        # No significant change, use cache
        return False

    def _generate_signal_for_token(
        self, ctx: TokenNewsContext, iso_now: str
    ) -> Optional[dict]:
        """Generate signal for a single token via API."""
        system_prompt = (
            "You are an on-chain news analyst. "
            "Produce JSON with fields: token_mint, headline, sentiment_score (-1..1), "
            "confidence (0..1), summary."
        )
        user_prompt = (
            "Using the following quantitative context, infer likely news or narratives "
            f"that traders should know. Return a JSON object (not array). Context:\n"
            f"Token: {ctx.name} ({ctx.symbol})\n"
            f"Mint: {ctx.token_mint}\n"
            f"1h momentum: {ctx.momentum:.3f}\n"
            f"volatility: {ctx.volatility:.3f}\n"
            f"risk_score: {ctx.risk_score:.2f}"
        )
        records = self.deepseek.structured_completion(system_prompt, user_prompt)
        if not records:
            return None

        # Handle both array and single object responses
        entry = records[0] if isinstance(records, list) else records
        token = entry.get("token_mint") or ctx.token_mint
        if not token:
            return None

        return {
            "signal_id": entry.get("signal_id") or f"NEWS-{uuid.uuid4().hex[:8]}",
            "timestamp": iso_now,
            "token_mint": token,
            "headline": entry.get("headline", "DeepSeek sentiment insight"),
            "sentiment_score": float(entry.get("sentiment_score", 0)),
            "confidence": float(
                max(self.settings.min_confidence, entry.get("confidence", 0.6))
            ),
            "source": entry.get("source", "deepseek"),
            "summary": entry.get("summary", "No summary provided."),
        }

