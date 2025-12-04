from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Iterable, List

import pandas as pd

from .config import RulesAgentSettings
from .data_store import RulesDataStore
from .deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)


class RulesAgentPipeline:
    def __init__(self, settings: RulesAgentSettings):
        self.settings = settings
        self.store = RulesDataStore(settings.data_dir)
        self.client = DeepSeekClient(settings)

    def run(self) -> List[dict]:
        rules = self.store.load_rules()
        prefs = self.store.load_user_preferences()
        catalog = self.store.load_token_catalog()
        if prefs.empty:
            logger.warning("No user preferences available; skipping rules evaluation.")
            return []

        iso_now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        evaluations: List[dict] = []
        for _, pref in prefs.iterrows():
            user_context = self._build_user_context(pref, catalog)
            if not user_context["tokens"]:
                continue
            rows = self._evaluate_user(rules, user_context, iso_now)
            evaluations.extend(rows)

        if evaluations:
            self.store.write_evaluations(evaluations)
            logger.info("Saved %d rule evaluations.", len(evaluations))
        else:
            logger.warning("No rule evaluations generated.")
        return evaluations

    def _build_user_context(self, pref_row, catalog: pd.DataFrame) -> Dict:
        allowed_tokens = (
            str(pref_row.get("allowed_tokens", "")).split("|")
            if pref_row.get("allowed_tokens")
            else []
        )
        blocked_tokens = set(
            filter(None, str(pref_row.get("blocked_tokens", "")).split("|"))
        )
        tokens = []
        for token in allowed_tokens:
            if token in blocked_tokens:
                continue
            catalog_row = (
                catalog[catalog["token_mint"] == token].iloc[0]
                if not catalog.empty
                else None
            )
            tokens.append(
                {
                    "token_mint": token,
                    "risk_score": float(
                        catalog_row["risk_score"] if catalog_row is not None else 0.5
                    ),
                    "liquidity_score": float(
                        catalog_row["liquidity_score"] if catalog_row is not None else 0.5
                    ),
                }
            )
        return {
            "user_id": int(pref_row["user_id"]),
            "risk_profile": pref_row.get("risk_profile", "balanced"),
            "max_trades_per_day": int(pref_row.get("max_trades_per_day", 3)),
            "max_position_ndollar": float(pref_row.get("max_position_ndollar", 1000)),
            "tokens": tokens,
        }

    def _evaluate_user(self, rules: pd.DataFrame, context: Dict, iso_now: str) -> List[dict]:
        if self.settings.dry_run or not self.settings.openrouter_api_key:
            return self._fallback(context, iso_now)

        rule_text = "\n".join(
            f"- {row['rule_id']}: {row['description']} ({row['param']}={row['value']})"
            for _, row in rules.iterrows()
        )
        token_text = "\n".join(
            f"{token['token_mint']} risk={token['risk_score']:.2f} "
            f"liquidity={token['liquidity_score']:.2f}"
            for token in context["tokens"]
        )
        system_prompt = (
            "You translate risk rules into executable policy. "
            "Return JSON array with fields: token_mint, allowed (bool), "
            "max_daily_trades, max_position_ndollar, reason, confidence."
        )
        user_prompt = f"""
User risk profile: {context['risk_profile']}
User max trades/day: {context['max_trades_per_day']}
User max position (ndollar): {context['max_position_ndollar']}

Rules:
{rule_text}

Tokens:
{token_text}
"""
        records = self.client.structured_completion(system_prompt, user_prompt)
        if not records:
            return self._fallback(context, iso_now)

        evaluations = []
        for entry in records:
            token = entry.get("token_mint")
            if not token:
                continue
            evaluations.append(
                {
                    "evaluation_id": entry.get("evaluation_id")
                    or f"RULE-{uuid.uuid4().hex[:8]}",
                    "timestamp": iso_now,
                    "user_id": context["user_id"],
                    "token_mint": token,
                    "allowed": bool(entry.get("allowed", True)),
                    "max_daily_trades": int(
                        entry.get("max_daily_trades", context["max_trades_per_day"])
                    ),
                    "max_position_ndollar": float(
                        entry.get(
                            "max_position_ndollar", context["max_position_ndollar"]
                        )
                    ),
                    "reason": entry.get("reason", "DeepSeek evaluation"),
                    "confidence": float(entry.get("confidence", 0.7)),
                }
            )
        return evaluations

    def _fallback(self, context: Dict, iso_now: str) -> List[dict]:
        rows = []
        for token in context["tokens"]:
            allowed = token["risk_score"] < 0.7
            rows.append(
                {
                    "evaluation_id": f"RULE-FALLBACK-{context['user_id']}-{token['token_mint']}",
                    "timestamp": iso_now,
                    "user_id": context["user_id"],
                    "token_mint": token["token_mint"],
                    "allowed": allowed,
                    "max_daily_trades": context["max_trades_per_day"]
                    if allowed
                    else max(1, context["max_trades_per_day"] - 2),
                    "max_position_ndollar": context["max_position_ndollar"]
                    * (0.5 if not allowed else 1.0),
                    "reason": "Heuristic fallback without DeepSeek.",
                    "confidence": 0.55,
                }
            )
        return rows

