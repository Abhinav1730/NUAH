"""
Token Analyzer - Gemini-Powered Scam Detection
===============================================
Uses Google Gemini to analyze new/unknown tokens for scam indicators
before the agent considers buying.

When to use:
- New tokens with no trading history
- Tokens not in our watchlist
- First time seeing a token pump
- High-risk situations where pattern rules aren't enough

What it analyzes:
- Token metadata (name, symbol, supply)
- Creator/deployer behavior
- Whale concentration
- Liquidity depth
- Social signals
- Bonding curve stage
- Red flags and scam patterns
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Token risk classification"""
    SAFE = "safe"              # Low risk, likely legitimate
    CAUTION = "caution"        # Some concerns, trade carefully
    HIGH_RISK = "high_risk"    # Significant red flags
    SCAM = "scam"              # Almost certainly a scam
    UNKNOWN = "unknown"        # Cannot determine


@dataclass
class TokenAnalysis:
    """Result of token analysis"""
    token_mint: str
    risk_level: RiskLevel
    risk_score: float  # 0.0 (safe) to 1.0 (scam)
    confidence: float  # How confident is the analysis
    
    # Detailed findings
    red_flags: List[str]
    green_flags: List[str]
    
    # Recommendations
    should_trade: bool
    max_position_percent: float  # Max % of portfolio to risk
    suggested_stop_loss: float   # Tighter for risky tokens
    
    # Analysis details
    summary: str
    detailed_analysis: str
    
    # Metadata
    analyzed_at: datetime
    analysis_time_ms: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_mint": self.token_mint,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "red_flags": self.red_flags,
            "green_flags": self.green_flags,
            "should_trade": self.should_trade,
            "max_position_percent": self.max_position_percent,
            "suggested_stop_loss": self.suggested_stop_loss,
            "summary": self.summary,
            "detailed_analysis": self.detailed_analysis,
            "analyzed_at": self.analyzed_at.isoformat(),
            "analysis_time_ms": self.analysis_time_ms,
        }


class TokenAnalyzer:
    """
    Gemini-powered token analyzer for scam/rug detection.
    
    Uses Google Gemini to analyze token data and identify red flags
    before the trading agent considers buying.
    """
    
    # Analysis cache to avoid repeated API calls
    _cache: Dict[str, TokenAnalysis] = {}
    _cache_ttl_seconds: int = 300  # 5 minutes
    
    def __init__(
        self,
        gemini_api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 10.0,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize the token analyzer.
        
        Args:
            gemini_api_key: Google Gemini API key
            model: Gemini model to use
            timeout: API timeout in seconds
            cache_ttl_seconds: How long to cache analysis results
        """
        self.api_key = gemini_api_key
        self.model = model
        self.timeout = timeout
        self._cache_ttl_seconds = cache_ttl_seconds
        
        self._client = httpx.Client(timeout=timeout)
        self._api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    def analyze(
        self,
        token_mint: str,
        token_data: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
        creator_data: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> TokenAnalysis:
        """
        Analyze a token for scam/rug indicators.
        
        Args:
            token_mint: Token identifier
            token_data: Token metadata (name, symbol, supply, etc.)
            market_data: Market data (price, volume, holders, etc.)
            creator_data: Creator/deployer information
            force_refresh: Bypass cache and re-analyze
            
        Returns:
            TokenAnalysis with risk assessment
        """
        # Check cache
        if not force_refresh and token_mint in self._cache:
            cached = self._cache[token_mint]
            age = (datetime.now(timezone.utc) - cached.analyzed_at).total_seconds()
            if age < self._cache_ttl_seconds:
                logger.debug(f"Using cached analysis for {token_mint}")
                return cached
        
        start_time = time.time()
        
        try:
            # Build the prompt
            prompt = self._build_prompt(token_mint, token_data, market_data, creator_data)
            
            # Call Gemini
            response = self._call_gemini(prompt)
            
            # Parse response
            analysis = self._parse_response(token_mint, response, start_time)
            
            # Cache result
            self._cache[token_mint] = analysis
            
            logger.info(
                f"🔍 Token analysis complete: {token_mint} | "
                f"Risk: {analysis.risk_level.value} ({analysis.risk_score:.2f}) | "
                f"Trade: {'YES' if analysis.should_trade else 'NO'}"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Token analysis failed for {token_mint}: {e}")
            
            # Return conservative unknown analysis
            return TokenAnalysis(
                token_mint=token_mint,
                risk_level=RiskLevel.UNKNOWN,
                risk_score=0.7,  # Assume moderately risky if analysis fails
                confidence=0.3,
                red_flags=["Analysis failed - treat with caution"],
                green_flags=[],
                should_trade=False,
                max_position_percent=0.02,  # Very small position
                suggested_stop_loss=0.05,   # Tight stop loss
                summary="Analysis failed, defaulting to high caution",
                detailed_analysis=f"Error: {str(e)}",
                analyzed_at=datetime.now(timezone.utc),
                analysis_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def _build_prompt(
        self,
        token_mint: str,
        token_data: Dict[str, Any],
        market_data: Optional[Dict[str, Any]],
        creator_data: Optional[Dict[str, Any]],
    ) -> str:
        """Build the analysis prompt for Gemini."""
        
        # Format token data
        token_info = json.dumps(token_data, indent=2) if token_data else "No token data available"
        market_info = json.dumps(market_data, indent=2) if market_data else "No market data available"
        creator_info = json.dumps(creator_data, indent=2) if creator_data else "No creator data available"
        
        prompt = f"""You are a crypto security analyst specializing in detecting meme coin scams and rug pulls on pump.fun-style platforms.

Analyze this token and provide a risk assessment:

TOKEN IDENTIFIER: {token_mint}

TOKEN DATA:
{token_info}

MARKET DATA:
{market_info}

CREATOR DATA:
{creator_info}

SCAM DETECTION CRITERIA:

RED FLAGS (Increase Risk):
1. Token name copies famous meme coins (fake PEPE, DOGE, etc.)
2. Extremely high total supply (>1 trillion)
3. Creator holds >30% of supply
4. Very few holders (<50)
5. No social media presence or fake followers
6. Token age < 1 hour with huge pump (classic pump & dump)
7. Suspicious contract (mint authority not revoked, etc.)
8. Copy-paste description from other tokens
9. Anonymous team with no track record
10. Liquidity < $5,000 (easy to manipulate)
11. Price pumped >100% in <10 minutes (likely manipulation)
12. Deployer has history of rugged tokens

GREEN FLAGS (Decrease Risk):
1. Active community on Twitter/Telegram
2. Verified contract
3. Mint authority revoked
4. Good holder distribution (no single whale >20%)
5. Decent liquidity (>$20,000)
6. Token exists >24 hours
7. Organic price movement (not just vertical pumps)
8. Creator has history of successful tokens

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "risk_level": "safe|caution|high_risk|scam",
    "risk_score": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "red_flags": ["list", "of", "red", "flags", "found"],
    "green_flags": ["list", "of", "green", "flags", "found"],
    "should_trade": true or false,
    "max_position_percent": 0.01 to 0.10,
    "suggested_stop_loss": 0.05 to 0.20,
    "summary": "One sentence summary",
    "detailed_analysis": "2-3 sentence detailed analysis"
}}

IMPORTANT:
- Be conservative - it's better to miss a pump than lose to a rug
- If data is missing, assume the worst
- For unknown tokens, default to high_risk unless clear green flags
- Response must be valid JSON only, no other text"""

        return prompt
    
    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        """Call Gemini API and get response."""
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.1,  # Low temp for consistent analysis
                "topK": 1,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        url = f"{self._api_url}?key={self.api_key}"
        
        response = self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract text from response
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Clean up response (remove markdown code blocks if present)
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.debug(f"Raw response: {data}")
            raise ValueError(f"Invalid Gemini response: {e}")
    
    def _parse_response(
        self,
        token_mint: str,
        response: Dict[str, Any],
        start_time: float
    ) -> TokenAnalysis:
        """Parse Gemini response into TokenAnalysis."""
        
        # Map risk level string to enum
        risk_level_map = {
            "safe": RiskLevel.SAFE,
            "caution": RiskLevel.CAUTION,
            "high_risk": RiskLevel.HIGH_RISK,
            "scam": RiskLevel.SCAM,
        }
        
        risk_level_str = response.get("risk_level", "unknown").lower()
        risk_level = risk_level_map.get(risk_level_str, RiskLevel.UNKNOWN)
        
        return TokenAnalysis(
            token_mint=token_mint,
            risk_level=risk_level,
            risk_score=float(response.get("risk_score", 0.5)),
            confidence=float(response.get("confidence", 0.5)),
            red_flags=response.get("red_flags", []),
            green_flags=response.get("green_flags", []),
            should_trade=bool(response.get("should_trade", False)),
            max_position_percent=float(response.get("max_position_percent", 0.02)),
            suggested_stop_loss=float(response.get("suggested_stop_loss", 0.10)),
            summary=response.get("summary", "No summary provided"),
            detailed_analysis=response.get("detailed_analysis", "No detailed analysis"),
            analyzed_at=datetime.now(timezone.utc),
            analysis_time_ms=int((time.time() - start_time) * 1000),
        )
    
    def quick_check(self, token_data: Dict[str, Any]) -> bool:
        """
        Quick rule-based check without calling Gemini.
        Use this for obvious red flags before spending API credits.
        
        Returns:
            True if token passes basic checks, False if obvious scam
        """
        # Check for obvious red flags
        
        # 1. Token name red flags
        name = (token_data.get("name") or "").lower()
        scam_keywords = ["elon", "musk", "trump", "official", "v2", "real", "legit"]
        if any(kw in name for kw in scam_keywords):
            logger.warning(f"Quick check failed: suspicious name '{name}'")
            return False
        
        # 2. Supply red flags
        total_supply = float(token_data.get("total_supply") or 0)
        if total_supply > 1_000_000_000_000_000:  # > 1 quadrillion
            logger.warning(f"Quick check failed: absurd supply {total_supply}")
            return False
        
        # 3. Price red flags
        price = float(token_data.get("price") or token_data.get("price_ndollar") or 0)
        if price <= 0:
            logger.warning("Quick check failed: zero/negative price")
            return False
        
        # 4. Holder concentration
        creator_percent = float(token_data.get("creator_percent") or token_data.get("whale_concentration") or 0)
        if creator_percent > 0.5:  # Creator holds > 50%
            logger.warning(f"Quick check failed: creator holds {creator_percent*100:.1f}%")
            return False
        
        return True
    
    def get_cached(self, token_mint: str) -> Optional[TokenAnalysis]:
        """Get cached analysis if available and not expired."""
        if token_mint in self._cache:
            cached = self._cache[token_mint]
            age = (datetime.now(timezone.utc) - cached.analyzed_at).total_seconds()
            if age < self._cache_ttl_seconds:
                return cached
        return None
    
    def clear_cache(self, token_mint: str = None):
        """Clear cache for a specific token or all tokens."""
        if token_mint:
            self._cache.pop(token_mint, None)
        else:
            self._cache.clear()


# Singleton instance for easy access
_analyzer_instance: Optional[TokenAnalyzer] = None


def get_token_analyzer(
    gemini_api_key: str = None,
    **kwargs
) -> TokenAnalyzer:
    """Get or create the token analyzer singleton."""
    global _analyzer_instance
    
    if _analyzer_instance is None:
        if not gemini_api_key:
            import os
            gemini_api_key = os.environ.get("GOOGLE_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        
        if not gemini_api_key:
            raise ValueError("Gemini API key required for token analysis")
        
        _analyzer_instance = TokenAnalyzer(gemini_api_key, **kwargs)
    
    return _analyzer_instance

