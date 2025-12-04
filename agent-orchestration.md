# Agent Orchestration & API Keys

## Execution order

1. `fetch-data-agent` (Node) refreshes SQLite + JSON snapshots every ~20 minutes.
2. `news-agent` (Python) ingests the latest time-series data and queries DeepSeek via OpenRouter for qualitative sentiment, appending rows to `data/news_signals.csv`.
3. `trend-agent` recalculates bonding-curve stages and risk scores (also via DeepSeek) and updates `data/token_strategy_catalog.csv` + `data/trend_signals.csv`.
4. `rules-agent` merges global rules + user preferences + newest analytics, emitting per-user decisions in `data/rule_evaluations.csv`.
5. `trade-agent` runs LangGraph pipeline, consuming SQLite snapshots plus all CSV outputs to execute trades (or dry-run) against `n-dollar-server`.
   - Use `python scheduler.py --interval-minutes 30 --initial-delay-minutes 5` to ensure trade runs always trail the fetch cadence and only fire when `last_fetched_at` values are fresh.

Each agent writes timestamps and schema versions so old data stays archived for backtesting while the pipeline enforces freshness windows.

## Required environment variables

| Agent | Variables |
| --- | --- |
| `trade-agent` | `SQLITE_PATH`, `SNAPSHOT_DIR`, `DATA_DIR`, `API_BASE_URL`, `NDOLLAR_API_TOKEN`, `GOOGLE_GEMINI_API_KEY`, `GEMINI_MODEL`, `DRY_RUN` |
| `news-agent` | `OPENROUTER_API_KEY`, `NEWS_AGENT_DATA_DIR`, `NEWS_AGENT_REFERER`, `NEWS_AGENT_APP_TITLE`, optional `NEWS_AGENT_DRY_RUN` |
| `trend-agent` | `OPENROUTER_API_KEY`, `TREND_AGENT_DATA_DIR`, `TREND_AGENT_REFERER`, `TREND_AGENT_APP_TITLE`, optional `TREND_AGENT_DRY_RUN` |
| `rules-agent` | `OPENROUTER_API_KEY`, `RULES_AGENT_DATA_DIR`, `RULES_AGENT_REFERER`, `RULES_AGENT_APP_TITLE`, optional `RULES_AGENT_DRY_RUN` |

## API keys checklist

| Purpose | Key | Notes |
| --- | --- | --- |
| Final trade fusion & reasoning | `GOOGLE_GEMINI_API_KEY` | Required so trade-agent can call Gemini (`gemini-2.5-pro`) before hitting n-dollar. |
| ML artifacts | `MODELS_DIR` | Directory where `scripts/train_models.py` writes pickled models. |
| News/trend/rule agents | `OPENROUTER_API_KEY` | Required for DeepSeek v3.2 on OpenRouter. |
| Trade execution | `NDOLLAR_API_TOKEN` | JWT/service account token for n-dollar buy/sell endpoints. |
| Pump.fun / on-chain telemetry (optional) | `HELIUS_API_KEY` or `PUMP_FUN_ANALYTICS_KEY` | Needed when we upgrade trend-agent to ingest live bonding-curve + liquidity data. |
| External news feeds (optional) | `CRYPTOPANIC_API_KEY`, `NEWSAPI_KEY` | Allows news-agent to supplement DeepSeek prompts with raw headlines. |
| Social signal ingestion (optional) | `FARCASTER_API_KEY`, `TELEGRAM_BOT_TOKEN` | Future work for social sentiment agent. |

Keep historical responses in the shared CSV folder—every new run appends instead of truncating so we can backtest, retrain ML models, and audit trade justifications.

