from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .config import NewsAgentSettings
from .generators import TokenNewsContext

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    Lightweight wrapper around OpenRouter's chat completions endpoint,
    with an optional helper to LLM-filter token contexts.
    """

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, settings: NewsAgentSettings):
        self.settings = settings
        self._client = httpx.Client(timeout=40)

    def structured_completion(
        self, system_prompt: str, user_prompt: str
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY not set; cannot call DeepSeek.")
            return None

        payload = {
            "model": self.settings.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "HTTP-Referer": self.settings.referer,
            "X-Title": self.settings.app_title,
            "Content-Type": "application/json",
        }

        response = self._client.post(self.API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error("DeepSeek response was not valid JSON: %s", content)
            return None

    def rank_and_filter_tokens(
        self,
        contexts: List[TokenNewsContext],
        user_owned_mints: Optional[List[str]] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Ask DeepSeek to filter/score tokens given momentum/volatility/risk and ownership hints.

        Returns a JSON array with fields:
          - token_mint
          - include (bool)  -> whether to keep for downstream processing
          - score (0..1)    -> optional confidence/priority
          - reason (string) -> short rationale
        """
        if not contexts:
            logger.warning("No contexts provided to rank_and_filter_tokens.")
            return []

        user_owned = set(user_owned_mints or [])

        rows = [
            {
                "token_mint": ctx.token_mint,
                "momentum": ctx.momentum,
                "volatility": ctx.volatility,
                "risk_score": ctx.risk_score,
                "user_owned": ctx.token_mint in user_owned,
            }
            for ctx in contexts
        ]

        system_prompt = (
            "You are an on-chain news analyst. Given token metrics, decide which tokens "
            "are trade-worthy. Prefer positive momentum, moderate volatility, and risk_score <= 0.7. "
            "Prioritize user-owned tokens if healthy; exclude high-risk or extreme-volatility tokens. "
            "Respond ONLY with JSON array of objects: "
            "[{token_mint, include (bool), score (0..1), reason}]."
        )

        user_prompt = (
            "Evaluate these tokens using the rules above:\n"
            + json.dumps(rows, ensure_ascii=False, indent=2)
        )

        return self.structured_completion(system_prompt, user_prompt)

