from __future__ import annotations

import logging
import uuid
from typing import Iterable, List, Optional

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
        signals = self._generate_signals(contexts, iso_now)
        if not signals:
            logger.warning("Failed to generate sentiments; storing fallback signals.")
            signals = fallback_signals(contexts, iso_now)

        self.store.append_news_signals(signals)
        logger.info("Stored %d news signals.", len(signals))
        return signals

    def _generate_signals(
        self, contexts: Iterable[TokenNewsContext], iso_now: str
    ) -> List[dict]:
        if self.settings.dry_run:
            return fallback_signals(contexts, iso_now)

        system_prompt = (
            "You are an on-chain news analyst. "
            "Produce JSON with fields: token_mint, headline, sentiment_score (-1..1), "
            "confidence (0..1), summary."
        )
        user_prompt = (
            "Using the following quantitative context, infer likely news or narratives "
            f"that traders should know. Return a JSON array. Context:\n{build_prompt(contexts)}"
        )
        records = self.deepseek.structured_completion(system_prompt, user_prompt)
        if not records:
            return []
        normalized = []
        for entry in records:
            token = entry.get("token_mint")
            if not token:
                continue
            normalized.append(
                {
                    "signal_id": entry.get("signal_id")
                    or f"NEWS-{uuid.uuid4().hex[:8]}",
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
            )
        return normalized

