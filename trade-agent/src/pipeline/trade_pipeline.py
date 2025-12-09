from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from langgraph.graph import END, StateGraph

from ..config import Settings
from ..data_ingestion import SQLiteDataLoader
from ..execution import NDollarClient
from ..graph import TradeState
from ..logging import AuditLogger
from ..models import FeatureEngineer, MLPredictor, RuleEvaluator, TradeDecision
from ..services import GeminiDecisionClient

logger = logging.getLogger(__name__)


class TradePipeline:
    """
    LangGraph-powered coordination layer that fuses multi-agent signals from SQLite
    and executes trades via nuahchain-backend.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.sqlite_loader = SQLiteDataLoader(settings.sqlite_path)
        self.rule_evaluator = RuleEvaluator()
        self.feature_engineer = FeatureEngineer()
        self.client = NDollarClient(settings.api_base_url, settings.api_token)
        self.audit_logger = AuditLogger(settings.sqlite_path)
        self.gemini_client = GeminiDecisionClient(
            settings.gemini_api_key, settings.gemini_model
        )
        self.ml_predictor = MLPredictor(
            settings.models_dir, self.feature_engineer, self.rule_evaluator
        )
        self.graph = self._build_graph()

    def run(self, user_ids: Optional[Iterable[int]] = None) -> Dict[str, int]:
        """
        Process users through the trade pipeline.
        
        Args:
            user_ids: Optional list of specific user IDs to process.
                     If None, discovers and processes ALL users in batches.
        
        Returns:
            Dict with processing stats: total, processed, failed, skipped
        """
        user_ids = list(user_ids or self._discover_user_ids())
        if not user_ids:
            logger.warning("No users discovered to process.")
            return {"total": 0, "processed": 0, "failed": 0, "skipped": 0}
        
        total_users = len(user_ids)
        batch_size = self.settings.batch_size
        batch_delay = self.settings.batch_delay_seconds
        
        # Stats tracking
        stats = {"total": total_users, "processed": 0, "failed": 0, "skipped": 0}
        
        # If batch_size is 0 or negative, process all at once (no batching)
        if batch_size <= 0:
            batch_size = total_users
        
        num_batches = (total_users + batch_size - 1) // batch_size  # Ceiling division
        
        logger.info(
            "Processing %d user(s) in %d batch(es) of %d",
            total_users, num_batches, batch_size
        )

        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_users)
            batch = user_ids[start_idx:end_idx]
            
            logger.info(
                "📦 Batch %d/%d: Processing users %d-%d (%d users)",
                batch_num + 1, num_batches, start_idx + 1, end_idx, len(batch)
            )
            
            for user_id in batch:
                try:
                    result = self.graph.invoke({"user_id": user_id})
                    decision = result.get("decision")
                    if decision:
                        logger.info(
                            "User %s decision: %s token=%s amount=%s conf=%.2f reason=%s",
                            user_id,
                            decision.action,
                            decision.token_mint,
                            decision.amount,
                            decision.confidence,
                            decision.reason,
                        )
                        if decision.action == "hold":
                            stats["skipped"] += 1
                        else:
                            stats["processed"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception:  # noqa: BLE001
                    logger.exception("Trade pipeline failed for user %s", user_id)
                    stats["failed"] += 1
            
            # Delay between batches (except after the last batch)
            if batch_num < num_batches - 1 and batch_delay > 0:
                logger.info(
                    "⏳ Batch %d complete. Waiting %d seconds before next batch...",
                    batch_num + 1, batch_delay
                )
                time.sleep(batch_delay)
        
        logger.info(
            "✅ Pipeline complete: %d total, %d processed, %d skipped, %d failed",
            stats["total"], stats["processed"], stats["skipped"], stats["failed"]
        )
        return stats

    # --- LangGraph assembly -------------------------------------------------

    def _build_graph(self):
        graph = StateGraph(TradeState)
        graph.add_node("load_context", self._node_load_context)
        graph.add_node("preprocess", self._node_preprocess)
        graph.add_node("rule_check", self._node_rule_check)
        graph.add_node("sentiment", self._node_sentiment)
        graph.add_node("ml_signal", self._node_ml_signal)
        graph.add_node("risk_manager", self._node_risk_manager)
        graph.add_node("decision", self._node_decision)
        graph.add_node("execution", self._node_execution)

        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "preprocess")
        graph.add_edge("preprocess", "rule_check")
        graph.add_edge("rule_check", "sentiment")
        graph.add_edge("sentiment", "ml_signal")
        graph.add_edge("ml_signal", "risk_manager")
        graph.add_edge("risk_manager", "decision")
        graph.add_edge("decision", "execution")
        graph.add_edge("execution", END)
        return graph.compile()

    # --- Nodes --------------------------------------------------------------

    def _node_load_context(self, state: TradeState) -> TradeState:
        user_id = state["user_id"]
        snapshot = self.sqlite_loader.fetch_user_snapshot(user_id)
        if not snapshot:
            raise ValueError(f"No snapshot available for user {user_id}")

        tokens = self._extract_tokens(snapshot)
        news_signals = self.sqlite_loader.fetch_news_signals(
            tokens, self.settings.news_freshness_minutes
        )
        trend_signals = self.sqlite_loader.fetch_trend_signals(
            tokens, self.settings.trend_freshness_minutes
        )
        rule_evaluations = self.sqlite_loader.fetch_rule_evaluations(user_id, tokens)
        preferences = self.sqlite_loader.fetch_user_preferences(user_id) or {}
        token_catalog = self.sqlite_loader.fetch_token_catalog(tokens)
        time_series = self.sqlite_loader.fetch_time_series(tokens)

        context = {
            "tokens": tokens,
            "news_signals": news_signals,
            "trend_signals": trend_signals,
            "rule_evaluations": rule_evaluations,
            "preferences": preferences,
            "token_catalog": token_catalog,
            "time_series": time_series,
            "historical_trades": snapshot.get("transactions", []),
        }
        errors: List[str] = []
        if self._snapshot_is_stale(snapshot):
            errors.append("snapshot_stale")

        return {
            "snapshot": snapshot,
            "context": context,
            "errors": errors,
            "metadata": {"notes": []},
        }

    def _node_preprocess(self, state: TradeState) -> TradeState:
        snapshot = state["snapshot"]
        context = state["context"]
        portfolio = snapshot.get("portfolio") or {}
        balances = snapshot.get("balances") or []
        portfolio_value = float(portfolio.get("totalValueNDollar") or 0.0)
        token_count = int(portfolio.get("count") or len(context["tokens"]))
        deployable = max(0.0, portfolio_value * 0.25)
        preferences = context.get("preferences") or {}
        if preferences:
            deployable = min(
                deployable,
                float(preferences.get("max_position_ndollar", deployable)),
            )
        trades_today = self._count_recent_trades(context.get("historical_trades", []))
        features = {
            "portfolio_value_ndollar": portfolio_value,
            "token_count": token_count,
            "deployable_ndollar": round(deployable, 2),
            "trades_today": trades_today,
            "balances": balances,
        }
        return {"features": features}

    def _node_rule_check(self, state: TradeState) -> TradeState:
        context = state["context"]
        features = state["features"]
        preferences = context.get("preferences") or {}
        max_trades = int(preferences.get("max_trades_per_day", 3))
        if context.get("rule_evaluations"):
            rule_limits = [
                int(row.get("max_daily_trades", max_trades))
                for row in context["rule_evaluations"]
            ]
            if rule_limits:
                max_trades = min([max_trades] + rule_limits)
        hard_stop = features["trades_today"] >= max_trades

        allowed_tokens = []
        for token in context["tokens"]:
            rule_row = next(
                (
                    row
                    for row in context.get("rule_evaluations", [])
                    if row["token_mint"] == token
                ),
                None,
            )
            if rule_row and not bool(rule_row.get("allowed", True)):
                continue
            allowed_tokens.append(
                {
                    "token_mint": token,
                    "max_position_ndollar": float(
                        rule_row.get(
                            "max_position_ndollar",
                            preferences.get(
                                "max_position_ndollar", features["deployable_ndollar"]
                            ),
                        )
                    )
                    if rule_row
                    else float(
                        preferences.get(
                            "max_position_ndollar", features["deployable_ndollar"]
                        )
                    ),
                    "max_daily_trades": int(
                        rule_row.get("max_daily_trades", max_trades)
                        if rule_row
                        else max_trades
                    ),
                    "reason": rule_row.get("reason") if rule_row else "preferences",
                    "confidence": float(rule_row.get("confidence", 0.7))
                    if rule_row
                    else 0.5,
                }
            )

        rule_result = {
            "allowed_tokens": allowed_tokens,
            "hard_stop": hard_stop,
            "max_daily_trades": max_trades,
        }
        if hard_stop:
            state["metadata"]["notes"].append("max_trades_reached")
        return {"rule_result": rule_result}

    def _node_sentiment(self, state: TradeState) -> TradeState:
        news = state["context"].get("news_signals", [])
        if not news:
            return {"sentiment": {"score": 0.0, "confidence": 0.0, "sources": []}}
        avg_score = sum(float(item.get("sentiment_score", 0)) for item in news) / len(
            news
        )
        avg_conf = sum(float(item.get("confidence", 0)) for item in news) / len(news)
        summary = [item.get("headline") for item in news[:3]]
        return {
            "sentiment": {
                "score": round(avg_score, 3),
                "confidence": round(avg_conf, 3),
                "sources": summary,
            }
        }

    def _node_ml_signal(self, state: TradeState) -> TradeState:
        sentiment = state.get("sentiment", {"score": 0.0, "confidence": 0.0})
        signal = self.ml_predictor.predict(
            user_id=state["user_id"],
            snapshot=state["snapshot"],
            base_features=state["features"],
            context=state["context"],
            sentiment=sentiment,
        )
        return {"ml_signal": signal}

    def _node_risk_manager(self, state: TradeState) -> TradeState:
        rule_result = state.get("rule_result") or {}
        ml_signal: Optional[TradeDecision] = state.get("ml_signal")
        features = state.get("features") or {}
        allowed_map = {
            entry["token_mint"]: entry for entry in rule_result.get("allowed_tokens", [])
        }
        notes = []
        hard_stop = rule_result.get("hard_stop", False)
        suggested_amount = 0.0
        max_amount = 0.0
        if not ml_signal or ml_signal.action == "hold":
            hard_stop = True
        else:
            allowance = allowed_map.get(ml_signal.token_mint)
            if not allowance:
                notes.append("token_blocked_by_rules")
                hard_stop = True
            else:
                max_amount = min(
                    allowance["max_position_ndollar"],
                    features.get("deployable_ndollar", allowance["max_position_ndollar"]),
                )
                suggested_amount = min(ml_signal.amount or max_amount, max_amount)
        risk_payload = {
            "hard_stop": hard_stop,
            "max_amount": round(max_amount, 2),
            "suggested_amount": round(suggested_amount, 2),
            "notes": notes,
        }
        state["metadata"]["risk"] = risk_payload
        return {"risk": risk_payload}

    def _node_decision(self, state: TradeState) -> TradeState:
        ml_signal: Optional[TradeDecision] = state.get("ml_signal")
        risk = state.get("risk") or {}
        features = state.get("features") or {}
        sentiment = state.get("sentiment") or {}
        rule_result = state.get("rule_result") or {}

        if risk.get("hard_stop"):
            decision = TradeDecision(
                user_id=state["user_id"],
                action="hold",
                token_mint=None,
                amount=None,
                confidence=0.4,
                reason="Risk guardrail prevented trading.",
            )
            return {"decision": decision}

        payload = {
            "user_id": state["user_id"],
            "features": {
                "portfolio_value_ndollar": features.get("portfolio_value_ndollar"),
                "deployable_ndollar": features.get("deployable_ndollar"),
                "trades_today": features.get("trades_today"),
            },
            "rule_constraints": rule_result,
            "ml_signal": ml_signal.__dict__ if ml_signal else None,
            "risk": risk,
            "sentiment": sentiment,
        }
        structured = self.gemini_client.score(payload)

        if structured:
            amount = min(
                float(structured.get("amount", 0)),
                risk.get("max_amount") or structured.get("amount", 0),
            )
            decision = TradeDecision(
                user_id=state["user_id"],
                action=structured.get("action", "hold"),
                token_mint=structured.get("token_mint"),
                amount=round(amount, 4) if amount else None,
                confidence=float(structured.get("confidence", 0.5)),
                reason=structured.get("reason", "Gemini fusion"),
            )
        elif ml_signal:
            decision = TradeDecision(
                user_id=state["user_id"],
                action=ml_signal.action,
                token_mint=ml_signal.token_mint,
                amount=risk.get("suggested_amount") or ml_signal.amount,
                confidence=ml_signal.confidence,
                reason=ml_signal.reason + " (fallback)",
            )
        else:
            decision = TradeDecision(
                user_id=state["user_id"],
                action="hold",
                token_mint=None,
                amount=None,
                confidence=0.4,
                reason="No signal generated.",
            )
        return {"decision": decision}

    def _node_execution(self, state: TradeState) -> TradeState:
        decision: Optional[TradeDecision] = state.get("decision")
        if not decision:
            return {}

        exec_resp: Optional[Dict] = None

        if decision.confidence < self.settings.decision_confidence_threshold:
            logger.info(
                "Skipping execution for user %s due to low confidence %.2f",
                decision.user_id,
                decision.confidence,
            )
            decision = TradeDecision(
                user_id=decision.user_id,
                action="hold",
                token_mint=decision.token_mint,
                amount=None,
                confidence=decision.confidence,
                reason="Confidence below threshold.",
            )
            state["decision"] = decision
        elif (
            decision.action in ("buy", "sell")
            and decision.token_mint
            and decision.amount
        ):
            if self.settings.dry_run or not self.settings.api_token:
                logger.info(
                    "[Dry Run] Would execute %s %s qty=%s",
                    decision.action,
                    decision.token_mint,
                    decision.amount,
                )
            else:
                if decision.action == "buy":
                    exec_resp = self.client.buy(decision.token_mint, decision.amount)
                else:
                    exec_resp = self.client.sell(decision.token_mint, decision.amount)
        else:
            logger.debug("No execution required for user %s", decision.user_id)

        metadata = {
            "trade_id": f"TRADE-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "risk_score": (state.get("risk") or {}).get("max_amount"),
        }

        # Determine execution status
        tx_hash = None
        exec_status = "skipped"
        error_message = None

        if decision.action == "hold":
            exec_status = "skipped"
        elif self.settings.dry_run or not self.settings.api_token:
            exec_status = "simulated"
        elif exec_resp:
            exec_status = (exec_resp.get("status") or "completed").lower()
            tx_hash = exec_resp.get("tx_hash")
            if exec_resp.get("error"):
                error_message = exec_resp.get("error")
                exec_status = "failed"

        try:
            self.client.log_trade(
                {
                    "user_id": decision.user_id,
                    "action": decision.action,
                    "token_mint": decision.token_mint,
                    "amount": decision.amount,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    "status": exec_status.upper(),
                    "tx_hash": tx_hash,
                    "timestamp": metadata["timestamp"],
                    "metadata": metadata,
                }
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to log trade to backend for user %s", decision.user_id, exc_info=True
            )

        # Log to SQLite database
        self.audit_logger.log(
            decision,
            metadata,
            status=exec_status,
            tx_hash=tx_hash,
            error_message=error_message,
        )
        return {}

    # --- Helpers ------------------------------------------------------------

    def _discover_user_ids(self) -> List[int]:
        """
        Discover ALL users from the database.
        No limit - processes every user in the system.
        """
        rows = self.sqlite_loader.fetch_recent_users(limit=None)  # Fetch ALL users
        user_ids = [row["user_id"] for row in rows]
        logger.info("Discovered %d users in database", len(user_ids))
        return user_ids

    @staticmethod
    def _extract_tokens(snapshot: Dict) -> List[str]:
        tokens = set()
        portfolio = snapshot.get("portfolio") or {}
        for item in portfolio.get("tokens", []):
            token_mint = item.get("mint_address") or item.get("token_mint")
            if token_mint:
                tokens.add(token_mint)
        for balance in snapshot.get("balances", []):
            token_mint = balance.get("token_mint")
            if token_mint:
                tokens.add(token_mint)
        for market in snapshot.get("marketData", []):
            token_mint = market.get("token_mint") or market.get("token_mint_address")
            if token_mint:
                tokens.add(token_mint)
        return list(tokens)

    def _snapshot_is_stale(self, snapshot: Dict) -> bool:
        fetched_at = snapshot.get("fetchedAt") or (snapshot.get("user") or {}).get(
            "last_fetched_at"
        )
        if not fetched_at:
            return False
        try:
            ts_str = str(fetched_at).replace("Z", "+00:00")
            ts = datetime.fromisoformat(ts_str)
            # Make timezone-aware if naive
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        age = datetime.now(timezone.utc) - ts
        return age.total_seconds() > self.settings.snapshot_freshness_minutes * 60

    @staticmethod
    def _count_recent_trades(trades: List[dict]) -> int:
        if not trades:
            return 0
        now = datetime.now(timezone.utc)
        count = 0
        for trade in trades:
            timestamp = trade.get("timestamp")
            if not timestamp:
                continue
            try:
                ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                # Make timezone-aware if naive
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if (now - ts).total_seconds() <= 24 * 3600:
                count += 1
        return count

