"""
Trend Agent Pipeline
====================
Analyzes price trends and bonding curve stages for pump.fun-style tokens.

Key Functions:
- Detect bonding curve stage (early/mid/late/graduated)
- Calculate trend direction and strength
- Identify pump/dump patterns for longer timeframes
- Score tokens for trade-worthiness
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd

from .config import TrendAgentSettings, get_settings
from .deepseek_client import DeepSeekClient
from .features import TrendContext, build_trend_contexts, fallback_signals

logger = logging.getLogger(__name__)


class TrendAgentPipeline:
    """
    Trend analysis pipeline for pump.fun-style tokens.
    
    Analyzes:
    - Bonding curve stage (how close to graduation)
    - Price momentum and trend direction
    - Volume patterns and liquidity
    - Risk scores based on volatility and whale concentration
    """
    
    def __init__(
        self,
        settings: TrendAgentSettings = None,
        sqlite_path: Optional[Path] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.sqlite_path = Path(sqlite_path or "../fetch-data-agent/data/user_data.db").resolve()
        self.data_dir = Path(self.settings.data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.client = DeepSeekClient(self.settings)
    
    def run(self, token_filter: Optional[List[str]] = None) -> List[Dict]:
        """
        Run trend analysis pipeline.
        
        Args:
            token_filter: Optional list of tokens to analyze
            
        Returns:
            List of trend signals
        """
        logger.info("Starting trend analysis pipeline...")
        
        # Load data from SQLite
        time_series, catalog = self._load_data()
        
        if time_series.empty:
            logger.warning("No time series data available")
            return []
        
        # Build contexts
        contexts = build_trend_contexts(time_series, limit=self.settings.top_tokens)
        
        if token_filter:
            contexts = [ctx for ctx in contexts if ctx.token_mint in token_filter]
        
        if not contexts:
            logger.warning("No token contexts to analyze")
            return []
        
        logger.info(f"Analyzing {len(contexts)} tokens...")
        
        # Get LLM analysis or use fallback
        if self.settings.dry_run or not self.settings.openrouter_api_key:
            logger.info("Using fallback heuristics (dry run or no API key)")
            iso_now = datetime.now(timezone.utc).isoformat()
            signals = fallback_signals(contexts, iso_now)
        else:
            # Use DeepSeek for analysis
            signals = self._analyze_with_llm(contexts, catalog)
            
            if not signals:
                logger.warning("LLM returned no signals, using fallback")
                iso_now = datetime.now(timezone.utc).isoformat()
                signals = fallback_signals(contexts, iso_now)
        
        # Write outputs
        self._write_trend_signals(signals)
        self._write_token_catalog(signals, catalog)
        
        logger.info(f"✅ Generated {len(signals)} trend signals")
        return signals
    
    def _analyze_with_llm(
        self,
        contexts: List[TrendContext],
        catalog: pd.DataFrame
    ) -> List[Dict]:
        """Use DeepSeek to analyze trends with pump.fun-specific logic."""
        
        # Build context data for LLM
        token_data = []
        for ctx in contexts:
            # Get catalog info if available
            cat_row = catalog[catalog["token_mint"] == ctx.token_mint]
            
            data = {
                "token_mint": ctx.token_mint,
                "momentum": round(ctx.momentum, 4),
                "volatility": round(ctx.volatility, 4),
                "volume_24h": round(ctx.volume, 2),
                "current_price": round(ctx.close, 8),
            }
            
            if not cat_row.empty:
                row = cat_row.iloc[0]
                data.update({
                    "bonding_curve_phase": row.get("bonding_curve_phase", "unknown"),
                    "risk_score": float(row.get("risk_score", 0.5)),
                    "liquidity_score": float(row.get("liquidity_score", 0.5)),
                    "whale_concentration": float(row.get("whale_concentration", 0)),
                })
            
            token_data.append(data)
        
        # Pump.fun-specific system prompt
        system_prompt = """You are a meme coin trend analyst specializing in pump.fun-style bonding curve tokens.

BONDING CURVE STAGES:
- "early": < 30% of curve filled, high upside but risky
- "mid": 30-70% filled, moderate risk/reward
- "late": 70-95% filled, approaching graduation
- "graduated": Migrated to DEX (Raydium), different dynamics

ANALYSIS FACTORS:
1. Momentum: Positive = bullish, Negative = bearish
2. Volatility: High (>0.15) = risky, Moderate (0.05-0.15) = normal, Low (<0.05) = stable
3. Volume: High volume confirms trend, Low volume = fake move
4. Whale concentration: >30% = rug risk
5. Liquidity: Low = slippage risk

TREND SCORES:
- +0.8 to +1.0: Strong bullish (buy opportunity)
- +0.3 to +0.7: Moderate bullish
- -0.3 to +0.3: Neutral/sideways
- -0.7 to -0.3: Moderate bearish
- -1.0 to -0.8: Strong bearish (sell/avoid)

Respond ONLY with JSON array:
[{
  "token_mint": "...",
  "trend_score": -1.0 to 1.0,
  "stage": "early|mid|late|graduated",
  "volatility_flag": "high|moderate|low",
  "liquidity_flag": "thin|healthy|deep",
  "risk_level": "low|medium|high|extreme",
  "rug_risk": 0.0 to 1.0,
  "confidence": 0.0 to 1.0,
  "summary": "Brief analysis"
}]"""

        user_prompt = f"""Analyze these pump.fun tokens:

{json.dumps(token_data, indent=2)}

Consider:
1. Is this a good entry point or should we wait?
2. What's the rug pull risk based on whale concentration?
3. Is the volume supporting the price movement?
4. Where is this token in its bonding curve lifecycle?"""

        response = self.client.structured_completion(system_prompt, user_prompt)
        
        if not response:
            return []
        
        # Convert to signals format
        signals = []
        iso_now = datetime.now(timezone.utc).isoformat()
        
        for idx, item in enumerate(response, start=1):
            signals.append({
                "signal_id": f"TREND-{idx:04d}",
                "timestamp": iso_now,
                "token_mint": item.get("token_mint", ""),
                "trend_score": float(item.get("trend_score", 0)),
                "stage": item.get("stage", "unknown"),
                "volatility_flag": item.get("volatility_flag", "moderate"),
                "liquidity_flag": item.get("liquidity_flag", "healthy"),
                "risk_level": item.get("risk_level", "medium"),
                "rug_risk": float(item.get("rug_risk", 0.3)),
                "confidence": float(item.get("confidence", 0.6)),
                "summary": item.get("summary", "LLM analysis"),
            })
        
        return signals
    
    def _write_trend_signals(self, signals: List[Dict]) -> None:
        """Write trend signals to CSV."""
        path = self.data_dir / "trend_signals.csv"
        
        fields = [
            "signal_id", "timestamp", "token_mint", "trend_score",
            "stage", "volatility_flag", "liquidity_flag", "risk_level",
            "rug_risk", "confidence", "summary"
        ]
        
        write_header = not path.exists() or path.stat().st_size == 0
        
        with path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            if write_header:
                writer.writeheader()
            for signal in signals:
                # Ensure all fields exist
                row = {k: signal.get(k, "") for k in fields}
                writer.writerow(row)
        
        logger.info(f"Wrote {len(signals)} signals to trend_signals.csv")
    
    def _write_token_catalog(self, signals: List[Dict], catalog: pd.DataFrame) -> None:
        """Update token strategy catalog with new analysis."""
        path = self.data_dir / "token_strategy_catalog.csv"
        
        # Build catalog entries
        entries = []
        iso_now = datetime.now(timezone.utc).isoformat()
        
        for signal in signals:
            token = signal.get("token_mint")
            
            # Get existing catalog data
            existing = catalog[catalog["token_mint"] == token]
            
            entry = {
                "token_mint": token,
                "name": existing.iloc[0]["name"] if not existing.empty else token,
                "symbol": existing.iloc[0]["symbol"] if not existing.empty else token[:8],
                "bonding_curve_phase": signal.get("stage", "unknown"),
                "trend_score": signal.get("trend_score", 0),
                "risk_score": signal.get("rug_risk", 0.5),
                "liquidity_score": 0.7 if signal.get("liquidity_flag") == "healthy" else 0.3,
                "volatility_score": 0.8 if signal.get("volatility_flag") == "high" else 0.4,
                "recommendation": self._get_recommendation(signal),
                "last_updated": iso_now,
            }
            entries.append(entry)
        
        if not entries:
            return
        
        # Write catalog
        fields = list(entries[0].keys())
        
        with path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            writer.writeheader()
            writer.writerows(entries)
        
        logger.info(f"Updated token_strategy_catalog.csv with {len(entries)} entries")
    
    def _get_recommendation(self, signal: Dict) -> str:
        """Generate trading recommendation from signal."""
        trend = signal.get("trend_score", 0)
        rug_risk = signal.get("rug_risk", 0.5)
        stage = signal.get("stage", "unknown")
        
        if rug_risk > 0.7:
            return "AVOID - High rug risk"
        
        if trend > 0.5 and stage in ["early", "mid"]:
            return "BUY - Strong trend, good stage"
        elif trend > 0.3:
            return "WATCH - Moderate bullish"
        elif trend < -0.5:
            return "SELL - Strong bearish"
        elif trend < -0.3:
            return "REDUCE - Weakening"
        else:
            return "HOLD - Neutral"
    
    def _load_data(self) -> tuple:
        """Load time series and catalog from SQLite."""
        time_series = pd.DataFrame()
        catalog = pd.DataFrame()
        
        if not self.sqlite_path.exists():
            logger.error(f"SQLite database not found: {self.sqlite_path}")
            return time_series, catalog
        
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                try:
                    time_series = pd.read_sql_query(
                        """SELECT token_mint, timestamp, open, high, low, close, 
                                  volume, momentum, volatility 
                           FROM time_series 
                           ORDER BY timestamp DESC""",
                        conn
                    )
                except Exception as e:
                    logger.warning(f"Could not load time_series: {e}")
                
                try:
                    catalog = pd.read_sql_query(
                        """SELECT token_mint, name, symbol, bonding_curve_phase,
                                  risk_score, liquidity_score, volatility_score,
                                  whale_concentration, last_updated
                           FROM token_strategy_catalog""",
                        conn
                    )
                except Exception as e:
                    logger.warning(f"Could not load token_strategy_catalog: {e}")
        
        except Exception as e:
            logger.error(f"Database error: {e}")
        
        if not time_series.empty and "timestamp" in time_series.columns:
            time_series["timestamp"] = pd.to_datetime(
                time_series["timestamp"], utc=True, errors="coerce"
            )
            time_series = time_series.dropna(subset=["timestamp"])
        
        return time_series, catalog

