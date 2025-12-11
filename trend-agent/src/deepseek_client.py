from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

import httpx

from .config import TrendAgentSettings

# Add shared module to path for LLM logger
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
try:
    from shared.llm_usage_logger import log_llm_usage
    LLM_LOGGING_ENABLED = True
except ImportError:
    LLM_LOGGING_ENABLED = False
    def log_llm_usage(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class DeepSeekClient:
    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, settings: TrendAgentSettings):
        self.settings = settings
        self._client = httpx.Client(timeout=40)

    def structured_completion(
        self, system_prompt: str, user_prompt: str, user_id: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY missing; cannot reach DeepSeek.")
            return None

        payload = {
            "model": self.settings.model,
            "temperature": 0.1,
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
        
        request_text = f"{system_prompt}\n\n{user_prompt}"
        response_text = ""
        start_time = time.time()
        
        try:
            response = self._client.post(self.API_URL, json=payload, headers=headers)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            response_text = content
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log usage
            if LLM_LOGGING_ENABLED:
                log_llm_usage(
                    agent="trend-agent",
                    model=self.settings.model,
                    request_text=request_text,
                    response_text=response_text,
                    user_id=user_id,
                    duration_ms=duration_ms,
                    success=True
                )
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error("DeepSeek response not JSON: %s", content)
                return None
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log failed request
            if LLM_LOGGING_ENABLED:
                log_llm_usage(
                    agent="trend-agent",
                    model=self.settings.model,
                    request_text=request_text,
                    response_text="",
                    user_id=user_id,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=str(e)
                )
            raise

