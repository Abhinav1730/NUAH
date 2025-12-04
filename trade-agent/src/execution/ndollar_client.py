from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger(__name__)


class NDollarClient:
    """
    Minimal HTTP client for n-dollar buy/sell endpoints.
    """

    def __init__(self, base_url: str, api_token: Optional[str], timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

    def buy(self, token_mint: str, amount: float) -> Dict[str, Any]:
        payload = {
            "tokenMintAddress": token_mint,
            "amount": amount,
        }
        return self._post("/buy", payload)

    def sell(self, token_mint: str, amount: float) -> Dict[str, Any]:
        payload = {
            "tokenMintAddress": token_mint,
            "amount": amount,
        }
        return self._post("/sell", payload)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_token:
            logger.warning("API token missing, skipping HTTP request")
            return {"success": False, "message": "API token not configured"}

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        if not response.ok:
            logger.error(
                "n-dollar API error %s: %s", response.status_code, response.text
            )
            response.raise_for_status()
        return response.json()

