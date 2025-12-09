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
        Ask DeepSeek to filter/score tokens for pump.fun-style meme coin trading.

        Returns a JSON array with fields:
          - token_mint
          - include (bool)  -> whether to keep for downstream processing
          - score (0..1)    -> confidence/priority score
          - reason (string) -> short rationale
          - catalyst (string) -> detected catalyst type
          - urgency (string) -> low/medium/high/critical
        """
        if not contexts:
            logger.warning("No contexts provided to rank_and_filter_tokens.")
            return []

        user_owned = set(user_owned_mints or [])

        rows = [
            {
                "token_mint": ctx.token_mint,
                "momentum": round(ctx.momentum, 4),
                "volatility": round(ctx.volatility, 4),
                "risk_score": round(ctx.risk_score, 3),
                "user_owned": ctx.token_mint in user_owned,
            }
            for ctx in contexts
        ]

        system_prompt = """You are a meme coin analyst for pump.fun-style trading. Your job is to identify HOT tokens with potential for rapid gains.

PUMP.FUN TRADING RULES:
1. MOMENTUM IS KING: High positive momentum (>0.1) = potential pump starting
2. VOLATILITY IS OPPORTUNITY: High volatility (>0.15) is GOOD for meme coins - it means action
3. RISK IS RELATIVE: Meme coins are inherently risky. Risk score up to 0.85 is acceptable if momentum is strong
4. FOMO DETECTION: Sudden momentum spikes often precede 2-10x moves
5. USER HOLDINGS: Prioritize tokens the user already owns if they're pumping

CATALYST TYPES:
- "pump_detected": Strong buying pressure visible
- "fomo_wave": Social momentum building
- "whale_entry": Large buyer detected
- "community_hype": Community engagement spike
- "none": No clear catalyst

URGENCY LEVELS:
- "critical": Act within seconds (rug risk or mega pump)
- "high": Act within 1-2 minutes
- "medium": Act within 5-10 minutes
- "low": Can wait for confirmation

Respond ONLY with JSON array:
[{
  "token_mint": "...",
  "include": true/false,
  "score": 0.0-1.0,
  "reason": "Brief explanation",
  "catalyst": "pump_detected|fomo_wave|whale_entry|community_hype|none",
  "urgency": "critical|high|medium|low"
}]"""

        user_prompt = f"""Analyze these pump.fun tokens for trading opportunities:

{json.dumps(rows, indent=2)}

Remember: We're looking for PUMPS, not safe investments. High volatility + high momentum = opportunity.
Exclude only if clearly dumping or extreme rug indicators."""

        return self.structured_completion(system_prompt, user_prompt)

