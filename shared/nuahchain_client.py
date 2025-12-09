"""
NuahChain Backend API Client

Provides a Python client for interacting with nuahchain-backend APIs.
Handles authentication, error handling, and response normalization.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


class NuahChainClient:
    """
    Client for interacting with nuahchain-backend APIs.
    
    Handles:
    - Authentication via Bearer tokens
    - Error handling and retries
    - Response normalization
    - Rate limiting
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_token: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the NuahChain client.
        
        Args:
            base_url: Base URL for nuahchain-backend (default: http://localhost:8080)
            api_token: Optional JWT token for authenticated requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        
        if self.api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            })

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make an HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/api/tokens/market")
            params: Query parameters
            json_data: JSON body for POST requests
            
        Returns:
            Response JSON as dict, or None if request failed
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    logger.error("Authentication failed. Check API token.")
                    return None
                elif response.status_code == 404:
                    logger.warning(f"Resource not found: {endpoint}")
                    return None
                elif response.status_code >= 500:
                    # Server error, retry
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"Server error {response.status_code}, retrying... "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    else:
                        logger.error(f"Server error after {self.max_retries} attempts: {response.status_code}")
                        return None
                else:
                    logger.error(f"Request failed with status {response.status_code}: {response.text}")
                    return None
                    
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Request timeout, retrying... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error("Request timeout after all retries")
                    return None
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Request error: {e}, retrying... (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error(f"Request failed after all retries: {e}")
                    return None
        
        return None

    def get_marketplace_tokens(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of all tokens in marketplace.
        
        Args:
            limit: Number of tokens to return (default: 100)
            offset: Pagination offset (default: 0)
            
        Returns:
            List of token dictionaries
        """
        response = self._request(
            "GET",
            "/api/tokens/market",
            params={"limit": limit, "offset": offset},
        )
        if response and "tokens" in response:
            return response["tokens"]
        return []

    def get_token_details(self, denom: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific token.
        
        Args:
            denom: Token denom (e.g., "factory/creator/symbol")
            
        Returns:
            Token details dictionary, or None if not found
        """
        # URL encode the denom for the path
        encoded_denom = quote(denom, safe="")
        endpoint = f"/api/tokens/{encoded_denom}/details"
        return self._request("GET", endpoint)

    def search_tokens(self, query: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Search tokens by name, symbol, or denom.
        
        Args:
            query: Search query
            limit: Number of results (default: 50)
            offset: Pagination offset (default: 0)
            
        Returns:
            List of matching tokens
        """
        response = self._request(
            "GET",
            "/api/tokens/search",
            params={"query": query, "limit": limit, "offset": offset},
        )
        if response and "tokens" in response:
            return response["tokens"]
        return []

    def get_trade_quote(
        self,
        denom: str,
        operation: str,
        amount: str,
        payment_denom: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get quote for buying or selling tokens on bonding curve.
        
        Args:
            denom: Token denom
            operation: "buy" or "sell"
            amount: Payment amount (buy) or token amount (sell)
            payment_denom: Payment currency (default: unuah)
            
        Returns:
            Quote dictionary, or None if failed
        """
        params = {
            "denom": denom,
            "operation": operation,
            "amount": amount,
        }
        if payment_denom:
            params["payment_denom"] = payment_denom
            
        return self._request("GET", "/api/quote/trade", params=params)

    def buy_token(
        self,
        denom: str,
        payment_amount: str,
        payment_denom: Optional[str] = None,
        min_tokens_out: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Buy tokens from bonding curve.
        
        Args:
            denom: Token denom to buy
            payment_amount: Amount to pay (in payment_denom)
            payment_denom: Payment currency (defaults to unuah)
            min_tokens_out: Minimum tokens to receive (slippage protection)
            
        Returns:
            Buy response dictionary with tx_hash, status, etc.
        """
        if not self.api_token:
            logger.error("API token required for buy_token")
            return None
            
        payload = {
            "denom": denom,
            "payment_amount": payment_amount,
        }
        if payment_denom:
            payload["payment_denom"] = payment_denom
        if min_tokens_out:
            payload["min_tokens_out"] = min_tokens_out
            
        return self._request("POST", "/api/tokens/buy", json_data=payload)

    def sell_token(
        self,
        denom: str,
        token_amount: str,
        payment_denom: Optional[str] = None,
        min_payment_out: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Sell tokens to bonding curve.
        
        Args:
            denom: Token denom to sell
            token_amount: Amount of tokens to sell
            payment_denom: Payment currency to receive (defaults to unuah)
            min_payment_out: Minimum payment to receive (slippage protection)
            
        Returns:
            Sell response dictionary with tx_hash, status, etc.
        """
        if not self.api_token:
            logger.error("API token required for sell_token")
            return None
            
        payload = {
            "denom": denom,
            "token_amount": token_amount,
        }
        if payment_denom:
            payload["payment_denom"] = payment_denom
        if min_payment_out:
            payload["min_payment_out"] = min_payment_out
            
        return self._request("POST", "/api/tokens/sell", json_data=payload)

    def get_transaction_status(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a transaction by hash.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Transaction status dictionary
        """
        return self._request("GET", f"/api/tx/{tx_hash}")

    def get_user_balances(
        self, denom_filter: Optional[str] = None, from_blockchain: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get user balances (requires authentication).
        
        Args:
            denom_filter: Optional filter by specific denom
            from_blockchain: If True, fetch from blockchain (slower but fresh)
            
        Returns:
            List of balance dictionaries
        """
        if not self.api_token:
            logger.error("API token required for get_user_balances")
            return []
            
        endpoint = "/api/users/balances" if from_blockchain else "/api/users/balances-db"
        params = {}
        if denom_filter:
            params["denom"] = denom_filter
            
        response = self._request("GET", endpoint, params=params)
        if response and "balances" in response:
            return response["balances"]
        return []

    def get_balance_history(
        self, denom: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get balance change history (requires authentication).
        
        Args:
            denom: Optional filter by specific denom
            limit: Number of records (default: 100)
            
        Returns:
            List of balance history records
        """
        if not self.api_token:
            logger.error("API token required for get_balance_history")
            return []
            
        params = {"limit": limit}
        if denom:
            params["denom"] = denom
            
        response = self._request("GET", "/api/users/balances/history", params=params)
        if response and "history" in response:
            return response["history"]
        return []



