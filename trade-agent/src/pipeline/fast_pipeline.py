"""
Fast Trading Pipeline
=====================
Real-time trading pipeline for pump.fun-style meme coin markets.

Key features:
- Runs continuously (every 5-15 seconds)
- Integrates with news/trend/rules agents for context
- Pattern-based triggers for pumps/dumps/rugs
- Automated stop-loss/take-profit
- Emergency exit capability

Flow:
1. Load Agent Signals → Get news/trend/rules context (5-min cache)
2. Price Monitor → Real-time price tracking (5-second polls)
3. Pattern Detector → Identify pump/dump/rug patterns
4. Risk Guard → Check stop-loss/take-profit
5. Fast Decision → Quick buy/sell/hold (uses agent signals + patterns)
6. Emergency Exit → Instant execution if needed

Integration with Analysis Agents:
- news_signals.csv → Token sentiment & catalysts
- trend_signals.csv → Bonding curve stage & risk
- rule_evaluations.csv → User-specific permissions & limits
"""

from __future__ import annotations

import asyncio
import csv
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any
from pathlib import Path

import pandas as pd

from ..config import Settings
from ..data_ingestion import SQLiteDataLoader
from ..execution import NDollarClient
from ..logging import AuditLogger
from ..models import TradeDecision

from ..realtime import (
    PriceMonitor,
    PriceUpdate,
    PatternDetector,
    PatternSignal,
    PatternType,
    RiskGuard,
    Position,
    StopLossConfig,
    EmergencyExit,
)

# Gemini-powered token analysis (for scam detection on new tokens)
try:
    from ..analysis import TokenAnalyzer, TokenAnalysis, RiskLevel, get_token_analyzer
    HAS_TOKEN_ANALYZER = True
except ImportError:
    HAS_TOKEN_ANALYZER = False
    TokenAnalyzer = None
    TokenAnalysis = None
    RiskLevel = None

logger = logging.getLogger(__name__)


class FastTradePipeline:
    """
    Real-time trading pipeline for pump.fun-style meme coin markets.
    
    Integrates with analysis agents (news, trend, rules) for intelligent
    fast trading decisions. Runs continuously with 5-15 second cycles.
    
    Agent Signal Integration:
    - news_signals: Token sentiment, catalyst detection, urgency
    - trend_signals: Bonding curve stage, rug risk, trend direction
    - rule_evaluations: User-specific permissions and limits
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Data sources
        self.sqlite_loader = SQLiteDataLoader(settings.sqlite_path)
        self.data_dir = Path(settings.data_dir) if hasattr(settings, 'data_dir') else Path("data")
        
        # Execution
        self.client = NDollarClient(settings.api_base_url, settings.api_token)
        self.audit_logger = AuditLogger(settings.sqlite_path)
        
        # Real-time components
        self.price_monitor = PriceMonitor(
            api_base_url=settings.api_base_url,
            api_token=settings.api_token,
            poll_interval_seconds=settings.price_poll_interval_seconds,
            alert_threshold_1m=settings.pump_threshold_1m,
            alert_threshold_5m=0.15,
            volume_spike_threshold=settings.volume_spike_threshold,
        )
        
        self.pattern_detector = PatternDetector(
            micro_pump_threshold=settings.pump_threshold_1m,
            dump_threshold=settings.dump_threshold_1m,
            rug_threshold=settings.rug_threshold_1m,
            volume_spike_threshold=settings.volume_spike_threshold,
        )
        
        stop_loss_config = StopLossConfig(
            stop_loss_percent=settings.stop_loss_percent,
            trailing_stop_percent=settings.trailing_stop_percent,
            take_profit_percent=settings.take_profit_percent,
            emergency_threshold=settings.emergency_exit_threshold,
            rug_threshold=settings.rug_threshold_1m,
        )
        self.risk_guard = RiskGuard(config=stop_loss_config)
        
        self.emergency_exit = EmergencyExit(
            api_base_url=settings.api_base_url,
            api_token=settings.api_token,
            dry_run=settings.dry_run,
            max_slippage=settings.max_slippage,
        )
        
        # State
        self._running = False
        self._watched_tokens: Set[str] = set()
        self._user_contexts: Dict[int, Dict] = {}
        self._last_decision_time: Dict[int, float] = {}
        
        # Agent signals cache (refreshed every 5 minutes)
        self._news_signals: Dict[str, Dict] = {}  # token_mint -> latest signal
        self._trend_signals: Dict[str, Dict] = {}  # token_mint -> latest signal
        self._rule_evaluations: Dict[str, Dict] = {}  # f"{user_id}:{token}" -> evaluation
        self._signals_last_loaded: float = 0
        self._signals_cache_ttl: float = 60  # Refresh every 60 seconds
        
        # Stats
        self.stats = {
            "cycles": 0,
            "decisions_made": 0,
            "trades_executed": 0,
            "emergency_exits": 0,
            "patterns_detected": {},
            "signals_used": {"news": 0, "trend": 0, "rules": 0},
            "tokens_analyzed": 0,
            "scams_blocked": 0,
        }
        
        # Gemini-powered token analyzer for scam detection
        self._token_analyzer: Optional[TokenAnalyzer] = None
        self._analyzed_tokens: Dict[str, TokenAnalysis] = {}  # Cache of analyzed tokens
        self._known_tokens: Set[str] = set()  # Tokens we've seen before (no need to analyze)
        
        # Initialize token analyzer if Gemini key available
        if HAS_TOKEN_ANALYZER and settings.gemini_api_key:
            try:
                self._token_analyzer = get_token_analyzer(
                    gemini_api_key=settings.gemini_api_key,
                    model=getattr(settings, 'gemini_model', 'gemini-2.0-flash'),
                    timeout=10.0,
                    cache_ttl_seconds=300,  # 5 min cache
                )
                logger.info("✅ Gemini token analyzer enabled for scam detection")
            except Exception as e:
                logger.warning(f"Could not initialize token analyzer: {e}")
                self._token_analyzer = None
        else:
            logger.info("ℹ️ Token analyzer disabled (no Gemini API key or module not available)")
    
    # ==========================================================================
    # GEMINI SCAM DETECTION
    # ==========================================================================
    
    def _is_new_token(self, token_mint: str) -> bool:
        """Check if this is a new/unknown token that needs analysis."""
        # Already analyzed
        if token_mint in self._analyzed_tokens:
            return False
        
        # Already in our known safe list
        if token_mint in self._known_tokens:
            return False
        
        # Check if we have trend signals (means agents have seen it)
        if token_mint in self._trend_signals:
            self._known_tokens.add(token_mint)
            return False
        
        return True
    
    def _analyze_new_token(
        self,
        token_mint: str,
        price_update: Optional[PriceUpdate] = None
    ) -> Optional[TokenAnalysis]:
        """
        Analyze a new token using Gemini for scam detection.
        
        This is called BEFORE considering a buy on unknown tokens.
        Worth the 1-2s delay to avoid losing money to scams.
        
        Args:
            token_mint: Token to analyze
            price_update: Current price data if available
            
        Returns:
            TokenAnalysis or None if analyzer not available
        """
        if not self._token_analyzer:
            return None
        
        # Check cache first
        if token_mint in self._analyzed_tokens:
            analysis = self._analyzed_tokens[token_mint]
            # Check if cache is still valid (5 minutes)
            age = (datetime.now(timezone.utc) - analysis.analyzed_at).total_seconds()
            if age < 300:
                return analysis
        
        logger.info(f"🔍 Analyzing new token with Gemini: {token_mint}")
        
        # Build token data from available sources
        token_data = self._gather_token_data(token_mint, price_update)
        
        try:
            analysis = self._token_analyzer.analyze(
                token_mint=token_mint,
                token_data=token_data,
                market_data=token_data.get("market_data"),
                creator_data=token_data.get("creator_data"),
            )
            
            # Cache result
            self._analyzed_tokens[token_mint] = analysis
            self.stats["tokens_analyzed"] += 1
            
            # Log result
            if analysis.risk_level in [RiskLevel.SCAM, RiskLevel.HIGH_RISK]:
                logger.warning(
                    f"🚫 SCAM ALERT: {token_mint} | "
                    f"Risk: {analysis.risk_level.value} | "
                    f"Red flags: {', '.join(analysis.red_flags[:3])}"
                )
                self.stats["scams_blocked"] += 1
            elif analysis.risk_level == RiskLevel.CAUTION:
                logger.info(
                    f"⚠️ CAUTION: {token_mint} | "
                    f"Score: {analysis.risk_score:.2f} | "
                    f"Max position: {analysis.max_position_percent*100:.1f}%"
                )
            else:
                logger.info(
                    f"✅ Token OK: {token_mint} | "
                    f"Risk: {analysis.risk_level.value}"
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Token analysis failed: {e}")
            return None
    
    def _gather_token_data(
        self,
        token_mint: str,
        price_update: Optional[PriceUpdate] = None
    ) -> Dict[str, Any]:
        """Gather all available data about a token for analysis."""
        data = {
            "token_mint": token_mint,
        }
        
        # Add price data if available
        if price_update:
            data["current_price"] = price_update.price
            data["volume"] = price_update.volume
            data["price_change_1m"] = price_update.price_change_1m
            data["price_change_5m"] = price_update.price_change_5m
            data["momentum"] = price_update.momentum
            data["volume_spike"] = price_update.volume_spike
        
        # Add trend signal data if available
        trend = self._trend_signals.get(token_mint)
        if trend:
            data["bonding_curve_stage"] = trend.get("stage")
            data["rug_risk"] = trend.get("rug_risk")
            data["volatility_flag"] = trend.get("volatility_flag")
            data["liquidity_flag"] = trend.get("liquidity_flag")
        
        # Add news signal data if available
        news = self._news_signals.get(token_mint)
        if news:
            data["sentiment_score"] = news.get("sentiment_score")
            data["catalyst"] = news.get("catalyst")
        
        # Try to get additional data from SQLite
        try:
            # This would fetch from market_data table
            # Implementation depends on your schema
            pass
        except Exception:
            pass
        
        return data
    
    def _should_block_trade(self, token_mint: str) -> tuple:
        """
        Check if a trade should be blocked based on token analysis.
        
        Returns:
            (should_block: bool, reason: str, analysis: TokenAnalysis or None)
        """
        # No analyzer = don't block
        if not self._token_analyzer:
            return False, "", None
        
        # Get or perform analysis
        analysis = self._analyzed_tokens.get(token_mint)
        
        if not analysis:
            # Analyze if this is a new token
            if self._is_new_token(token_mint):
                analysis = self._analyze_new_token(token_mint)
        
        if not analysis:
            return False, "", None
        
        # Block scams
        if analysis.risk_level == RiskLevel.SCAM:
            return True, f"SCAM detected: {analysis.summary}", analysis
        
        # Block high risk unless explicitly allowed
        if analysis.risk_level == RiskLevel.HIGH_RISK and not analysis.should_trade:
            return True, f"High risk token: {analysis.summary}", analysis
        
        return False, "", analysis
    
    # ==========================================================================
    # AGENT SIGNALS INTEGRATION
    # ==========================================================================
    
    def _load_agent_signals(self, force: bool = False) -> None:
        """
        Load signals from news/trend/rules agents.
        Uses caching to avoid I/O on every cycle.
        """
        now = time.time()
        
        if not force and (now - self._signals_last_loaded) < self._signals_cache_ttl:
            return  # Use cached signals
        
        logger.info("🔄 Refreshing agent signals...")
        
        # Load news signals
        self._news_signals = self._load_csv_signals(
            "news_signals.csv",
            key_field="token_mint",
            fields=["sentiment_score", "confidence", "summary", "source"]
        )
        
        # Load trend signals
        self._trend_signals = self._load_csv_signals(
            "trend_signals.csv",
            key_field="token_mint",
            fields=["trend_score", "stage", "rug_risk", "volatility_flag", "liquidity_flag", "confidence"]
        )
        
        # Load rule evaluations
        self._rule_evaluations = self._load_csv_signals(
            "rule_evaluations.csv",
            key_field=None,  # Use composite key
            composite_key=["user_id", "token_mint"],
            fields=["allowed", "max_daily_trades", "max_position_ndollar", "confidence"]
        )
        
        self._signals_last_loaded = now
        
        logger.info(
            f"📊 Loaded signals: {len(self._news_signals)} news, "
            f"{len(self._trend_signals)} trend, {len(self._rule_evaluations)} rules"
        )
    
    def _load_csv_signals(
        self,
        filename: str,
        key_field: Optional[str] = None,
        composite_key: Optional[List[str]] = None,
        fields: List[str] = None
    ) -> Dict[str, Dict]:
        """Load latest signals from a CSV file."""
        path = self.data_dir / filename
        result = {}
        
        if not path.exists():
            logger.debug(f"Signal file not found: {path}")
            return result
        
        try:
            df = pd.read_csv(path)
            
            if df.empty:
                return result
            
            # Sort by timestamp to get latest
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df.sort_values("timestamp", ascending=False)
            
            # Build result dict
            for _, row in df.iterrows():
                # Determine key
                if composite_key:
                    key = ":".join(str(row.get(k, "")) for k in composite_key)
                elif key_field:
                    key = str(row.get(key_field, ""))
                else:
                    continue
                
                # Skip if already have more recent
                if key in result:
                    continue
                
                # Extract fields
                signal = {"_raw": row.to_dict()}
                for field in (fields or []):
                    if field in row:
                        signal[field] = row[field]
                
                result[key] = signal
            
        except Exception as e:
            logger.warning(f"Failed to load {filename}: {e}")
        
        return result
    
    def get_news_signal(self, token_mint: str) -> Optional[Dict]:
        """Get latest news signal for a token."""
        self._load_agent_signals()
        signal = self._news_signals.get(token_mint)
        if signal:
            self.stats["signals_used"]["news"] += 1
        return signal
    
    def get_trend_signal(self, token_mint: str) -> Optional[Dict]:
        """Get latest trend signal for a token."""
        self._load_agent_signals()
        signal = self._trend_signals.get(token_mint)
        if signal:
            self.stats["signals_used"]["trend"] += 1
        return signal
    
    def get_rule_evaluation(self, user_id: int, token_mint: str) -> Optional[Dict]:
        """Get rule evaluation for a user-token pair."""
        self._load_agent_signals()
        key = f"{user_id}:{token_mint}"
        signal = self._rule_evaluations.get(key)
        if signal:
            self.stats["signals_used"]["rules"] += 1
        return signal
    
    def is_token_allowed(self, user_id: int, token_mint: str) -> bool:
        """Check if token is allowed for user based on rules."""
        evaluation = self.get_rule_evaluation(user_id, token_mint)
        if not evaluation:
            return True  # Default to allowed if no rule
        return bool(evaluation.get("allowed", True))
    
    def get_max_position(self, user_id: int, token_mint: str) -> float:
        """Get max position size for user-token pair."""
        evaluation = self.get_rule_evaluation(user_id, token_mint)
        if evaluation:
            return float(evaluation.get("max_position_ndollar", 500))
        return 500  # Default
    
    def get_rug_risk(self, token_mint: str) -> float:
        """Get rug risk from trend signals."""
        trend = self.get_trend_signal(token_mint)
        if trend:
            return float(trend.get("rug_risk", 0.3))
        return 0.3  # Default moderate risk
    
    def get_bonding_stage(self, token_mint: str) -> str:
        """Get bonding curve stage from trend signals."""
        trend = self.get_trend_signal(token_mint)
        if trend:
            return str(trend.get("stage", "unknown"))
        return "unknown"
    
    # ==========================================================================
    
    def load_user_context(self, user_id: int) -> Dict:
        """Load context for a user"""
        snapshot = self.sqlite_loader.fetch_user_snapshot(user_id)
        if not snapshot:
            return {}
        
        # Extract tokens user holds
        tokens = set()
        for balance in snapshot.get("balances", []):
            token_mint = balance.get("token_mint")
            if token_mint:
                tokens.add(token_mint)
        
        portfolio = snapshot.get("portfolio") or {}
        
        return {
            "user_id": user_id,
            "tokens": list(tokens),
            "portfolio_value": float(portfolio.get("totalValueNDollar", 0)),
            "preferences": self.sqlite_loader.fetch_user_preferences(user_id) or {},
            "snapshot": snapshot,
        }
    
    def initialize_users(self, user_ids: List[int]):
        """Initialize monitoring for users"""
        logger.info(f"Initializing fast pipeline for {len(user_ids)} users...")
        
        all_tokens = set()
        
        for user_id in user_ids:
            context = self.load_user_context(user_id)
            if context:
                self._user_contexts[user_id] = context
                all_tokens.update(context.get("tokens", []))
                
                # Initialize positions in risk guard
                for balance in context.get("snapshot", {}).get("balances", []):
                    token = balance.get("token_mint")
                    amount = float(balance.get("balance", 0)) / 1_000_000  # Convert from micro
                    
                    if token and amount > 0:
                        # Get current price (simplified)
                        price = 0.001  # Would get from market data
                        self.risk_guard.add_position(
                            user_id=user_id,
                            token_mint=token,
                            entry_price=price,
                            amount=amount,
                        )
        
        # Watch all tokens
        self._watched_tokens = all_tokens
        self.price_monitor.watch_all(list(all_tokens))
        
        logger.info(f"Watching {len(all_tokens)} tokens for {len(self._user_contexts)} users")
    
    def _process_price_update(self, update: PriceUpdate):
        """Process a single price update"""
        # 1. Detect pattern
        signal = self.pattern_detector.detect(update)
        
        # Track pattern stats
        pattern_name = signal.pattern.value
        self.stats["patterns_detected"][pattern_name] = (
            self.stats["patterns_detected"].get(pattern_name, 0) + 1
        )
        
        # 2. Check risk guard for exits
        exit_signal = self.risk_guard.check_price_update(update)
        if exit_signal:
            self._handle_exit(exit_signal)
            return
        
        # 3. Check pattern-based exits
        pattern_exit = self.risk_guard.check_pattern_signal(signal)
        if pattern_exit:
            self._handle_exit(pattern_exit)
            return
        
        # 4. Check for entry opportunities
        if signal.action == "buy" and signal.confidence >= 0.65:
            self._consider_entry(signal)
    
    def _handle_exit(self, exit_signal):
        """Handle an exit signal"""
        # Use emergency exit for speed
        result = self.emergency_exit.execute_exit(exit_signal)
        
        if result.success:
            self.stats["trades_executed"] += 1
            if exit_signal.reason.value == "emergency":
                self.stats["emergency_exits"] += 1
        
        # Log the trade
        self._log_trade(exit_signal, result)
    
    def _consider_entry(self, signal: PatternSignal):
        """
        Consider entering a position based on pattern signal.
        
        Integrates with agent signals:
        - Checks rules-agent for user permissions
        - Uses news-agent sentiment as confidence boost
        - Uses trend-agent for rug risk filtering
        - Uses Gemini for scam detection on new tokens
        """
        token = signal.token_mint
        
        # Load latest agent signals
        self._load_agent_signals()
        
        # =====================================================
        # GEMINI SCAM DETECTION - Check new tokens before entry
        # =====================================================
        if self._token_analyzer and self._is_new_token(token):
            # Get price update for context
            price_update = self.price_monitor.get_latest(token)
            
            # Analyze token with Gemini
            analysis = self._analyze_new_token(token, price_update)
            
            if analysis:
                # Block scams entirely
                if analysis.risk_level == RiskLevel.SCAM:
                    logger.warning(
                        f"🚫 BLOCKED SCAM: {token} | {analysis.summary}"
                    )
                    return
                
                # Block high risk unless should_trade is True
                if analysis.risk_level == RiskLevel.HIGH_RISK and not analysis.should_trade:
                    logger.warning(
                        f"⚠️ BLOCKED HIGH RISK: {token} | {analysis.summary}"
                    )
                    return
                
                # For caution-level tokens, we'll reduce position size below
                logger.info(
                    f"✅ Token analysis passed: {token} | "
                    f"Risk: {analysis.risk_level.value} | "
                    f"Max position: {analysis.max_position_percent*100:.0f}%"
                )
        
        # Pre-check: Skip if high rug risk detected by trend-agent
        rug_risk = self.get_rug_risk(token)
        if rug_risk > 0.7:
            logger.debug(f"Skipping {token}: high rug risk ({rug_risk:.2f})")
            return
        
        # Find users who might want to trade this token
        for user_id, context in self._user_contexts.items():
            # Check rate limiting
            last_decision = self._last_decision_time.get(user_id, 0)
            if time.time() - last_decision < self.settings.decision_interval_seconds:
                continue
            
            # Check rules-agent permissions
            if not self.is_token_allowed(user_id, token):
                logger.debug(f"Token {token} not allowed for user {user_id}")
                continue
            
            # Check if user already has this position
            if self.risk_guard.get_position(token):
                continue
            
            # Get max position from rules-agent or preferences
            rules_max = self.get_max_position(user_id, token)
            preferences = context.get("preferences", {})
            pref_max = float(preferences.get("max_position_ndollar", 500))
            portfolio_value = context.get("portfolio_value", 0)
            
            # Get max position from Gemini token analyzer (if available)
            analyzer_max_percent = 0.10  # Default 10%
            analyzer_stop_loss = None
            if token in self._analyzed_tokens:
                analysis = self._analyzed_tokens[token]
                analyzer_max_percent = analysis.max_position_percent
                analyzer_stop_loss = analysis.suggested_stop_loss
                
                # Extra reduction for caution-level tokens
                if analysis.risk_level == RiskLevel.CAUTION:
                    analyzer_max_percent *= 0.7  # 30% reduction
            
            # Calculate position size (use smallest constraint)
            position_size = min(
                rules_max,
                pref_max,
                portfolio_value * analyzer_max_percent,  # Gemini-recommended max
            )
            
            # Reduce position if rug risk is elevated
            if rug_risk > 0.4:
                position_size *= (1 - rug_risk)
            
            if position_size < 10:  # Minimum $10
                continue
            
            # Make decision with agent context
            decision = self._make_fast_decision(user_id, signal, position_size)
            
            if decision and decision.action == "buy":
                self._execute_decision(decision)
                self._last_decision_time[user_id] = time.time()
    
    def _make_fast_decision(
        self,
        user_id: int,
        signal: PatternSignal,
        max_amount: float
    ) -> Optional[TradeDecision]:
        """
        Make a fast trading decision using pattern + agent signals + Gemini analysis.
        
        Decision factors:
        1. Pattern signal (primary trigger)
        2. News sentiment (confidence boost/reduction)
        3. Trend stage (entry timing)
        4. Rug risk (position sizing)
        5. Gemini token analysis (scam detection, risk level)
        """
        token = signal.token_mint
        pattern = signal.pattern
        confidence = signal.confidence
        
        # Get agent signals
        news = self.get_news_signal(token)
        trend = self.get_trend_signal(token)
        
        # Build decision context
        reasons = [f"Pattern: {pattern.value}"]
        
        # =====================================================
        # GEMINI ANALYSIS INTEGRATION
        # =====================================================
        gemini_analysis = self._analyzed_tokens.get(token)
        suggested_stop_loss = None
        
        if gemini_analysis:
            # Adjust confidence based on Gemini risk assessment
            if gemini_analysis.risk_level == RiskLevel.SAFE:
                confidence = min(1.0, confidence + 0.10)
                reasons.append(f"Gemini: SAFE ({gemini_analysis.risk_score:.2f})")
            elif gemini_analysis.risk_level == RiskLevel.CAUTION:
                confidence = max(0.0, confidence - 0.10)
                reasons.append(f"Gemini: CAUTION ({gemini_analysis.risk_score:.2f})")
            elif gemini_analysis.risk_level == RiskLevel.HIGH_RISK:
                confidence = max(0.0, confidence - 0.25)
                reasons.append(f"Gemini: HIGH_RISK ({gemini_analysis.risk_score:.2f})")
            
            # Use Gemini's suggested stop-loss
            suggested_stop_loss = gemini_analysis.suggested_stop_loss
            
            # Add green/red flags to reasons
            if gemini_analysis.green_flags:
                reasons.append(f"Green: {gemini_analysis.green_flags[0]}")
            if gemini_analysis.red_flags:
                reasons.append(f"Red: {gemini_analysis.red_flags[0]}")
        
        # Adjust confidence based on news sentiment
        if news:
            sentiment = float(news.get("sentiment_score", 0))
            if sentiment > 0.3:
                confidence = min(1.0, confidence + 0.1)
                reasons.append(f"News: positive ({sentiment:.2f})")
            elif sentiment < -0.3:
                confidence = max(0.0, confidence - 0.2)
                reasons.append(f"News: negative ({sentiment:.2f})")
        
        # Adjust based on bonding curve stage
        stage = self.get_bonding_stage(token)
        if stage == "early":
            confidence = min(1.0, confidence + 0.05)  # Early = good entry
            reasons.append("Stage: early (good entry)")
        elif stage == "late":
            confidence = max(0.0, confidence - 0.15)  # Late = risky
            reasons.append("Stage: late (risky)")
        elif stage == "graduated":
            # Different dynamics post-graduation
            reasons.append("Stage: graduated (DEX)")
        
        # Adjust for rug risk
        rug_risk = self.get_rug_risk(token)
        if rug_risk > 0.5:
            confidence = max(0.0, confidence - rug_risk * 0.3)
            reasons.append(f"Rug risk: {rug_risk:.2f}")
        
        # Decision logic based on pattern type
        if pattern in [PatternType.MICRO_PUMP, PatternType.ACCUMULATION]:
            min_confidence = 0.55  # Lower threshold for fast entry
            if confidence >= min_confidence:
                amount = max_amount * confidence
                decision = TradeDecision(
                    user_id=user_id,
                    action="buy",
                    token_mint=token,
                    amount=round(amount, 2),
                    confidence=confidence,
                    reason=f"Fast buy: {', '.join(reasons)}",
                )
                # Attach Gemini-suggested stop loss as metadata
                decision._gemini_stop_loss = suggested_stop_loss
                return decision
        
        elif pattern == PatternType.MID_PUMP:
            # More selective with mid pumps
            min_confidence = 0.65
            if confidence >= min_confidence:
                # Smaller position for chasing pumps
                amount = max_amount * 0.6 * confidence
                decision = TradeDecision(
                    user_id=user_id,
                    action="buy",
                    token_mint=token,
                    amount=round(amount, 2),
                    confidence=confidence,
                    reason=f"Momentum entry: {', '.join(reasons)}",
                )
                decision._gemini_stop_loss = suggested_stop_loss
                return decision
        
        elif pattern == PatternType.MEGA_PUMP:
            # Be very careful with mega pumps (often top signals)
            min_confidence = 0.80
            if confidence >= min_confidence and stage == "early":
                # Only enter early-stage mega pumps
                amount = max_amount * 0.4 * confidence
                decision = TradeDecision(
                    user_id=user_id,
                    action="buy",
                    token_mint=token,
                    amount=round(amount, 2),
                    confidence=confidence,
                    reason=f"FOMO entry: {', '.join(reasons)}",
                )
                # Use tighter stop loss for mega pumps (they reverse fast)
                decision._gemini_stop_loss = suggested_stop_loss or 0.08
                return decision
        
        return None
    
    def _execute_decision(self, decision: TradeDecision):
        """Execute a trading decision"""
        self.stats["decisions_made"] += 1
        
        if self.settings.dry_run:
            logger.info(
                f"[DRY RUN] Would execute: {decision.action} {decision.token_mint} "
                f"amount={decision.amount} confidence={decision.confidence:.2f}"
            )
            return
        
        try:
            if decision.action == "buy":
                result = self.client.buy(decision.token_mint, decision.amount)
            elif decision.action == "sell":
                result = self.client.sell(decision.token_mint, decision.amount)
            else:
                return
            
            if result.get("success"):
                self.stats["trades_executed"] += 1
                
                # Add to risk guard if buy
                if decision.action == "buy":
                    # Use Gemini-suggested stop loss if available
                    gemini_stop_loss = getattr(decision, '_gemini_stop_loss', None)
                    
                    self.risk_guard.add_position(
                        user_id=decision.user_id,
                        token_mint=decision.token_mint,
                        entry_price=float(result.get("price_paid", decision.amount)),
                        amount=decision.amount,
                        custom_stop_loss=gemini_stop_loss,  # Gemini-recommended stop loss
                    )
                
            logger.info(f"Trade executed: {decision.action} {decision.token_mint}")
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
    
    def _log_trade(self, exit_signal, result):
        """Log a trade to audit log"""
        try:
            decision = TradeDecision(
                user_id=exit_signal.position.user_id,
                action="sell",
                token_mint=exit_signal.position.token_mint,
                amount=exit_signal.exit_amount,
                confidence=0.95,
                reason=f"Auto-exit: {exit_signal.reason.value}",
            )
            
            metadata = {
                "trade_id": f"FAST-{int(time.time()*1000)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "exit_reason": exit_signal.reason.value,
                "execution_time_ms": result.execution_time_ms,
            }
            
            self.audit_logger.log(
                decision,
                metadata,
                status="completed" if result.success else "failed",
                tx_hash=result.tx_hash,
                error_message=result.error,
            )
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")
    
    async def run(self, user_ids: List[int] = None):
        """
        Run the fast trading pipeline.
        
        Args:
            user_ids: List of user IDs to trade for
        """
        user_ids = user_ids or self.settings.user_ids or []
        
        if not user_ids:
            logger.warning("No user IDs specified for fast pipeline")
            return
        
        # Initialize
        self.initialize_users(user_ids)
        
        # Register price update callback
        def on_price(update: PriceUpdate):
            self._process_price_update(update)
        
        self.price_monitor.on_price_update(on_price)
        
        # Start monitoring
        self._running = True
        logger.info("🚀 Fast trading pipeline started!")
        
        try:
            await self.price_monitor.start()
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted")
        finally:
            self.stop()
    
    def run_sync(self, user_ids: List[int] = None, duration_seconds: float = None):
        """Run synchronously for testing"""
        user_ids = user_ids or self.settings.user_ids or []
        
        if not user_ids:
            return
        
        self.initialize_users(user_ids)
        
        self._running = True
        start = time.time()
        
        logger.info(f"Starting fast pipeline (sync mode, duration={duration_seconds}s)")
        
        while self._running:
            if duration_seconds and (time.time() - start) >= duration_seconds:
                break
            
            self.stats["cycles"] += 1
            
            # Fetch prices
            from ..realtime.price_monitor import SyncPriceMonitor
            sync_monitor = SyncPriceMonitor(
                api_base_url=self.settings.api_base_url,
                api_token=self.settings.api_token,
            )
            sync_monitor.watch_all(list(self._watched_tokens))
            
            updates = sync_monitor.fetch_once()
            
            for update in updates:
                self._process_price_update(update)
            
            time.sleep(self.settings.price_poll_interval_seconds)
        
        self.stop()
    
    def stop(self):
        """Stop the pipeline"""
        self._running = False
        self.price_monitor.stop()
        logger.info("Fast trading pipeline stopped")
        self.print_stats()
    
    def print_stats(self):
        """Print pipeline statistics"""
        logger.info("=" * 50)
        logger.info("FAST PIPELINE STATS")
        logger.info("=" * 50)
        logger.info(f"Cycles: {self.stats['cycles']}")
        logger.info(f"Decisions Made: {self.stats['decisions_made']}")
        logger.info(f"Trades Executed: {self.stats['trades_executed']}")
        logger.info(f"Emergency Exits: {self.stats['emergency_exits']}")
        logger.info(f"Patterns Detected: {self.stats['patterns_detected']}")
        logger.info("=" * 50)

