# Agentic Flow Reference

This document traces the full NUAH pipeline—from data collection to trade
execution—and enumerates the exact functions (with file locations) that run in
order. Use it as a map when debugging the system or onboarding new agents.

---

## 1. Fetch Data Agent (`fetch-data-agent`)

1. **Process bootstrap**
   - `main()` in `src/index.ts`  
     Loads environment variables, ensures `API_TOKEN`, opens SQLite (`getDatabase`), and instantiates `UserDataService` + `Scheduler`.
2. **Connectivity check**
   - `UserDataService.testConnection()` in `src/services/userDataService.ts`  
     Probes `/api/v1/users/data/1` to verify the n-dollar API + credentials.
3. **Scheduling**
   - `Scheduler.start()` in `src/scheduler.ts`  
     Creates a cron job (`node-cron`) using `FETCH_INTERVAL_MINUTES`. Each tick:
     1. Calls `UserDataService.fetchActiveTraders()` → prioritizes active bots.
     2. Calls `UserDataService.fetchAllUsers()` → refreshes remaining users.
4. **Data ingestion**
   - `UserDataService.fetchAndStoreUser()`  
     Fetches user snapshot via `ApiClient.fetchUserData()` (`src/services/apiClient.ts`) and persists it with `DataService.storeUserData()` (`src/services/dataService.ts`), which upserts into all SQLite tables inside a transaction.
5. **Snapshot export (JSON + TOON)**
   - `SnapshotExporter.writeSnapshots()` in `src/exporters/snapshotExporter.ts`  
     Produces `data/snapshots/user_<id>.json` (envelope) and `.toon` (Protobuf) files using the canonical schema from `SNAPSHOT_SCHEMA.md`.

Result: SQLite, JSON, and TOON snapshots are aligned and ready for downstream agents.

---

## 2. News Agent (`news-agent`)

1. **Entry point**
   - `run()` command in `main.py`  
     Parses CLI args, loads `NewsAgentSettings`, instantiates `NewsAgentPipeline`.
2. **Context assembly**
   - `NewsAgentPipeline.run()` in `src/pipeline.py`  
     Uses `SharedDataStore.load_time_series()` + `load_token_catalog()` to build token contexts via `build_token_contexts()` (`src/generators.py`).
3. **Sentiment generation**
   - `_generate_signals()` in `src/pipeline.py`  
     Calls `DeepSeekClient.structured_completion()` (`src/deepseek_client.py`) unless `dry_run` is set. Each record is normalized (token mint, headline, sentiment score, confidence, summary).
4. **Persistence**
   - `SharedDataStore.append_news_signals()` (`src/data_store.py`)  
     Appends rows to `data/news_signals.csv`, ensuring timestamps are in ISO format.

---

## 3. Trend Agent (`trend-agent`)

1. **Entry point**
   - `run` command in `main.py`  
     Loads `TrendAgentSettings`, instantiates `TrendAgentPipeline`.
2. **Context assembly**
   - `TrendAgentPipeline.run()` (`src/pipeline.py`)  
     Reads `time_series.csv`, converts to `TrendContext` objects via `build_trend_contexts()` (`src/features.py`).
3. **Trend scoring**
   - `_generate_signals()` (`src/pipeline.py`)  
     Calls `DeepSeekClient.structured_completion()` for qualitative tags (trend score, stage, liquidity flag, etc.). Falls back to heuristics if DeepSeek fails or `dry_run` is enabled.
4. **Data updates**
   - `TrendDataStore.append_trend_signals()` (`src/data_store.py`) → appends to `data/trend_signals.csv`.  
   - `_refresh_catalog()` (`src/pipeline.py`) → updates `token_strategy_catalog.csv` with latest bonding-curve phase, risk, liquidity, volatility, and timestamp.

---

## 4. Rules Agent (`rules-agent`)

1. **Entry point**
   - `run` command in `main.py`  
     Loads `RulesAgentSettings`, creates `RulesAgentPipeline`.
2. **Input gathering**
   - `RulesAgentPipeline.run()` (`src/pipeline.py`)  
     Loads `rules.csv`, `user_preferences.csv`, and `token_strategy_catalog.csv` via `RulesDataStore`.
3. **Per-user evaluation**
   - `_build_user_context()`  
     Merges preferences (allowed/blocked tokens, risk profile) with catalog scores.
   - `_evaluate_user()`  
     Calls `DeepSeekClient.structured_completion()` to return rows containing `allowed`, `max_daily_trades`, `max_position_ndollar`, `reason`, `confidence`. Falls back to heuristics if API calls fail.
4. **Persistence**
   - `RulesDataStore.write_evaluations()` writes the full table to `data/rule_evaluations.csv`.

---

## 5. Trade Agent (`trade-agent`)

### 5.1 Batch execution (single run)

1. **Entry point**
   - `main()` in `main.py`  
     Loads `Settings`, instantiates `TradePipeline`, parses optional `--user-ids`.
2. **TradePipeline graph**
   - Constructed in `src/pipeline/trade_pipeline.py` via `StateGraph`. Nodes execute sequentially:
     1. `load_context` → `_node_load_context()`  
        - Loads snapshots: `SnapshotLoader.load_json_snapshot()` (`src/data_ingestion/snapshot_loader.py`) or falls back to `SQLiteDataLoader.fetch_user_snapshot()` (`src/data_ingestion/sqlite_loader.py`).  
        - Calls `CSVDataLoader.build_context()` (`src/data_ingestion/csv_loader.py`) to pull news, trend, rules, preferences, token catalog, time-series, and historical trades.
     2. `preprocess` → `_node_preprocess()`  
        - Computes basic portfolio features (value, deployable capital, trades today).
     3. `rule_check` → `_node_rule_check()`  
        - Applies rule evaluations + user preferences to identify allowed tokens and max trades.
     4. `sentiment` → `_node_sentiment()`  
        - Aggregates news signals into an averaged score + confidence.
     5. `ml_signal` → `_node_ml_signal()`  
        - Calls `MLPredictor.predict()` (`src/models/ml_predictor.py`), which uses `FeatureEngineer.build()` to create feature vectors and either loads trained LightGBM models or falls back to `RuleEvaluator.evaluate()` (`src/models/rule_evaluator.py`).
     6. `risk_manager` → `_node_risk_manager()`  
        - Enforces deployable caps, token allowances, and hard stops.
     7. `decision` → `_node_decision()`  
        - Calls `GeminiDecisionClient.score()` (`src/services/gemini_client.py`) for final fusion; falls back to ML output if Gemini is unavailable.
     8. `execution` → `_node_execution()`  
        - Checks confidence thresholds, performs dry-run logging or live HTTP requests using `NDollarClient.buy/sell()` (`src/execution/ndollar_client.py`), and records every decision via `AuditLogger.log()` (`src/logging/audit_logger.py`) into `data/historical_trades.csv`.

### 5.2 Continuous scheduling

1. **Scheduler CLI**
   - `scheduler.py`  
     - `parse_args()` reads `--interval-minutes` and `--initial-delay-minutes`.
     - `run_scheduler()` checks snapshot freshness via `SQLiteDataLoader.latest_snapshot_timestamp()`. If data is younger than `snapshot_freshness_minutes`, it calls `TradePipeline.run()`; otherwise, it skips the cycle.
2. **Orchestration**
   - Documented in `agent-orchestration.md` – run `fetch-data-agent` every 20 min, then start `python scheduler.py --interval-minutes 30 --initial-delay-minutes 5` so each trade cycle trails data collection by five minutes.

---

## 6. Data products consumed by ML training

1. `scripts/train_models.py` → `MLTrainer.run()` (`src/models/trainer.py`)
   - Loads `historical_trades.csv`, `time_series.csv`, `news_signals.csv`, `trend_signals.csv`, and `token_strategy_catalog.csv`.
   - Builds features via `FeatureEngineer.build()` and trains:
     - `action_model.pkl` (CalibratedClassifierCV over LightGBM classifier)
     - `amount_model.pkl` (LightGBM regressor)
     - `confidence_model.pkl` (LightGBM regressor)
     - `feature_columns.pkl` (ordered feature names)

These artifacts are stored under `models/` and automatically loaded by `MLPredictor` during the `ml_signal` node.

---

### Quick reference: key functions & locations (chronological)

1. `fetch-data-agent/src/index.ts` → `main()`
2. `fetch-data-agent/src/scheduler.ts` → `Scheduler.start()`
3. `fetch-data-agent/src/services/userDataService.ts` → `fetchAndStoreUser()`  
   → `DataService.storeUserData()` (`src/services/dataService.ts`)  
   → `SnapshotExporter.writeSnapshots()` (`src/exporters/snapshotExporter.ts`)
4. `news-agent/main.py` → `run()` → `NewsAgentPipeline.run()`
5. `trend-agent/main.py` → `run()` → `TrendAgentPipeline.run()`
6. `rules-agent/main.py` → `run()` → `RulesAgentPipeline.run()`
7. `trade-agent/main.py` → `main()` → `TradePipeline.run()` (nodes listed above)
8. Optional continuous mode: `trade-agent/scheduler.py` → `run_scheduler()`
9. ML retraining: `trade-agent/scripts/train_models.py` → `MLTrainer.run()`

This chain represents the full agentic loop from data ingestion to automated trades.

