"""
Denom ↔ Token Mint Mapper

Handles conversion between nuahchain-backend denom format (factory/creator/symbol)
and agent token_mint format.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DenomMapper:
    """
    Maps between denom format (factory/creator/symbol) and token_mint format.
    
    Since agents expect token_mint format but nuahchain uses denom format,
    we need a consistent mapping strategy.
    """

    def __init__(self):
        """Initialize the mapper with an optional cache."""
        self._cache: Dict[str, str] = {}
        self._reverse_cache: Dict[str, str] = {}

    def denom_to_token_mint(self, denom: str) -> str:
        """
        Convert denom to token_mint format.
        
        Strategy:
        1. If denom is already in token_mint format (no slashes), return as-is
        2. For factory/creator/symbol format, use symbol as token_mint
        3. If symbol not available, create hash-based identifier
        
        Args:
            denom: Token denom (e.g., "factory/creator/symbol" or "MintAlpha123")
            
        Returns:
            Token mint identifier
        """
        if denom in self._cache:
            return self._cache[denom]
        
        # If no slashes, assume it's already a token_mint
        if "/" not in denom:
            self._cache[denom] = denom
            self._reverse_cache[denom] = denom
            return denom
        
        # Parse factory/creator/symbol format
        parts = denom.split("/")
        if len(parts) >= 3 and parts[0] == "factory":
            # Use symbol as token_mint (most readable)
            symbol = parts[-1].upper()  # Use uppercase for consistency
            token_mint = symbol
            
            # If symbol is too short or generic, create hash-based identifier
            if len(symbol) < 3:
                # Create hash from full denom
                hash_obj = hashlib.md5(denom.encode())
                token_mint = f"TKN{hash_obj.hexdigest()[:8].upper()}"
        else:
            # For other formats (e.g., asset/GOLD), use last part
            token_mint = parts[-1].upper()
        
        self._cache[denom] = token_mint
        self._reverse_cache[token_mint] = denom
        return token_mint

    def token_mint_to_denom(self, token_mint: str) -> Optional[str]:
        """
        Convert token_mint back to denom format.
        
        Args:
            token_mint: Token mint identifier
            
        Returns:
            Denom string, or None if not found in cache
        """
        return self._reverse_cache.get(token_mint)

    def add_mapping(self, denom: str, token_mint: Optional[str] = None) -> str:
        """
        Add a mapping between denom and token_mint.
        
        Args:
            denom: Token denom
            token_mint: Optional token_mint (if not provided, will be generated)
            
        Returns:
            The token_mint (generated or provided)
        """
        if token_mint:
            self._cache[denom] = token_mint
            self._reverse_cache[token_mint] = denom
            return token_mint
        else:
            return self.denom_to_token_mint(denom)

    def clear_cache(self) -> None:
        """Clear the mapping cache."""
        self._cache.clear()
        self._reverse_cache.clear()


# Global mapper instance
_global_mapper = DenomMapper()


def denom_to_token_mint(denom: str) -> str:
    """Convenience function to convert denom to token_mint."""
    return _global_mapper.denom_to_token_mint(denom)


def token_mint_to_denom(token_mint: str) -> Optional[str]:
    """Convenience function to convert token_mint to denom."""
    return _global_mapper.token_mint_to_denom(token_mint)


def add_mapping(denom: str, token_mint: Optional[str] = None) -> str:
    """Convenience function to add a mapping."""
    return _global_mapper.add_mapping(denom, token_mint)


