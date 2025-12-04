from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiDecisionClient:
    """
    Wraps Google Gemini (via google-generativeai) to obtain structured execution guidance.
    """

    def __init__(self, api_key: Optional[str], model: str):
        self.api_key = api_key
        self.model_name = model
        self.model = None
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(model)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to configure Gemini client.")
                self.model = None

    def score(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.model:
            logger.warning("Gemini API key/model not configured; skipping decision fusion.")
            return None

        system_prompt = (
            "You are an execution risk manager for a crypto trading agent. "
            "Given constraints and suggested signals, respond with a JSON object "
            "containing fields: action (buy/sell/hold), token_mint, amount (number), "
            "confidence (0..1), and reason. Respect hard stops and never exceed "
            "max position sizes."
        )
        user_payload = json.dumps(payload)
        prompt = (
            f"{system_prompt}\n\nContext payload:\n{user_payload}\n\n"
            "Return only valid JSON."
        )
        try:
            response = self.model.generate_content(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini request failed: %s", exc)
            return None

        text = getattr(response, "text", None) or "".join(
            part.text for part in getattr(response, "candidates", []) if hasattr(part, "text")
        )
        if not text:
            logger.error("Gemini response empty.")
            return None

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error("Gemini response was not valid JSON: %s", text)
            return None

