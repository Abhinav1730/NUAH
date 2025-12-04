from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .config import NewsAgentSettings

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    Lightweight wrapper around OpenRouter's chat completions endpoint.
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

