from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Import shared utilities
_shared_path = Path(__file__).parent.parent.parent.parent / "shared"
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))

from denom_mapper import token_mint_to_denom
from nuahchain_client import NuahChainClient


logger = logging.getLogger(__name__)


class NDollarClient:
    """
    HTTP client for nuahchain-backend buy/sell endpoints and trade logging.
    """

    def __init__(self, base_url: str, api_token: Optional[str], timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

        # Use NuahChain client for API calls
        self.client = NuahChainClient(
            base_url=base_url,
            api_token=api_token,
            timeout=timeout,
        )

    def buy(self, token_mint: str, amount: float, payment_denom: Optional[str] = None) -> Dict[str, Any]:
        denom = token_mint_to_denom(token_mint) or token_mint
        if denom == token_mint:
            logger.warning("No denom mapping found for %s, using as-is", token_mint)

        payment_amount = str(int(amount * 1_000_000))  # NDOLLAR -> micro-units
        logger.info("Buying %s with %s %s", denom, payment_amount, payment_denom or "unuah")

        response = self.client.buy_token(
            denom=denom,
            payment_amount=payment_amount,
            payment_denom=payment_denom,
        )

        if not response:
            return {
                "success": False,
                "message": "Failed to execute buy transaction",
                "error": "No response from API",
            }

        return {
            "success": response.get("status") in ["PENDING", "SUCCESS"],
            "tx_hash": response.get("tx_hash", ""),
            "tokens_out": response.get("tokens_out", ""),
            "price_paid": response.get("price_paid", ""),
            "status": response.get("status", "FAILED"),
            "message": response.get("message", ""),
            "error": response.get("error", ""),
        }

    def sell(self, token_mint: str, amount: float, payment_denom: Optional[str] = None) -> Dict[str, Any]:
        denom = token_mint_to_denom(token_mint) or token_mint
        if denom == token_mint:
            logger.warning("No denom mapping found for %s, using as-is", token_mint)

        token_amount = str(int(amount * 1_000_000))  # token units -> micro-units
        logger.info("Selling %s of %s", token_amount, denom)

        response = self.client.sell_token(
            denom=denom,
            token_amount=token_amount,
            payment_denom=payment_denom,
        )

        if not response:
            return {
                "success": False,
                "message": "Failed to execute sell transaction",
                "error": "No response from API",
            }

        return {
            "success": response.get("status") in ["PENDING", "SUCCESS"],
            "tx_hash": response.get("tx_hash", ""),
            "payment_out": response.get("payment_out", ""),
            "price_received": response.get("price_received", ""),
            "status": response.get("status", "FAILED"),
            "message": response.get("message", ""),
            "error": response.get("error", ""),
        }

    def log_trade(self, trade_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send executed (or simulated) trade metadata back to nuahchain-backend for auditing.
        """
        try:
            # Prefer a dedicated endpoint if available; fallback to raw request.
            if hasattr(self.client, "record_trade"):
                return self.client.record_trade(trade_payload)  # type: ignore[attr-defined]
            return self.client._request("POST", "/api/trades/record", json_data=trade_payload)  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to record trade: %s", exc)
            return None

