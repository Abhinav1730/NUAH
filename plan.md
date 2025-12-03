# Trade-Agent Implementation Plan

## 1. System Overview
- **Goal**: Autonomously trade N-Dollar (pump.fun) tokens on behalf of users using the data captured by `fetch-data-agent`.
- **Languages & Frameworks**:
  - Data ingestion/cache: existing Node.js fetch-data-agent with SQLite + JSON/TOON snapshots.
  - Trading brain/execution: Python `trade-agent` built on LangGraph.
  - Machine learning: Python ecosystem (pandas, LightGBM/PyTorch) when sufficient history exists.
- **Data Flow**:
  1. `fetch-data-agent` runs every 20 minutes → writes user snapshots (SQLite + JSON/TOON).
  2. `trade-agent` runs every 30 minutes (after fetch) → loads snapshots → analyzes via LangGraph → executes buy/sell through n-dollar APIs.
  3. Execution logs feed back into SQLite for monitoring and future ML training.

```
fetch-data-agent  ──▶  shared data store (SQLite + JSON/TOON)
                           │
                           ▼
                    trade-agent (LangGraph)
                           │
                           ▼
             n-dollar-server buy/sell endpoints
```

---

## 2. Work Breakdown Structure

### Phase A – Data Layer Alignment
1. **Snapshot Schema Contract**
   - Canonical structure: `userId`, `profile`, `balances`, `portfolio`, `transactions`, `bots`, `marketData`.
   - Include schema version in every snapshot to maintain backward compatibility.
2. **Format Exporters**
   - Continue storing SQLite for internal use.
   - Export JSON (human-readable) + TOON (compact typed format) per user.
3. **Access APIs**
   - Option A: `fetch-data-agent` exposes a lightweight HTTP endpoint that returns the latest snapshot per user.
   - Option B: Put JSON/TOON files in a shared directory; trade-agent watches for updates.

### Phase B – trade-agent Skeleton (Python + LangGraph)
1. **Repository Layout**
   - `ingestion/` – SQLite + JSON/TOON readers, schema validators.
   - `graph/` – LangGraph node definitions.
   - `models/` – ML/statistical components.
   - `executors/` – n-dollar API client (buy/sell, auth).
   - `news/` – news & sentiment ingestion utilities.
2. **LangGraph Pipeline (MVP)**
   - `LoadUserDataNode`
   - `PreprocessNode` (feature engineering, balance normalization)
   - `RuleCheckNode` (hard constraints: min balance, max trades/day)
   - `MLSignalNode` (heuristic/ML prediction)
   - `SentimentNode` (news/trend adjustments)
   - `RiskManagerNode` (stop-loss, diversification)
   - `ExecutionNode` (API calls + logging)
3. **Scheduling**
   - Cron-driven entrypoint that ensures `fetch-data-agent` finishes before `trade-agent` starts.

### Phase C – ML & Intelligence
1. **Feature Store**
   - Convert historical snapshots into training datasets (pandas/DataFrame + parquet).
   - Features: price momentum, user risk scoring, bot settings, on-chain signals.
2. **Model Training / Evaluation**
   - Baseline: rule-based or logistic regression.
   - Next: LightGBM/XGBoost.
   - Future: reinforcement learning for strategy selection.
3. **News & Trend Integration**
   - `news_fetcher` hitting CryptoPanic / NewsAPI / RSS feeds.
   - Sentiment analysis (TextBlob/HuggingFace).
   - Node merges sentiment into final decision score.

### Phase D – Execution & Risk Controls
1. **Authentication**
   - Reuse BotAuthService logic or create service accounts for `trade-agent`.
2. **Order Throttling & Circuit Breakers**
   - Max trades per user/day, global fail-safe if error rate > threshold.
3. **Simulation Mode**
   - Dry-run flag to log trades without hitting APIs (useful for testing/ML backtesting).
4. **Audit Logging**
   - Persist every decision (inputs, outputs, reason codes) for compliance and debugging.

### Phase E – Deployment & Observability
1. Dockerize trade-agent; orchestrate via Docker Compose/Kubernetes/CronJob.
2. Metrics/logging stack (e.g., Prometheus + Grafana, or simple Next.js dashboard reading SQLite).
3. Secret management (vault or env files with restricted access).

---

## 3. TOON vs JSON for Data Exchange

| Aspect           | JSON                                    | TOON (Typed Object Oriented Notation\*)               |
|------------------|-----------------------------------------|-------------------------------------------------------|
| Structure        | Text-based, schema-less                 | Strongly typed, schema-bound                          |
| Size             | Verbose keys → larger payloads          | Compact binary or columnar layout                     |
| Parsing Speed    | Fast but CPU-heavy for large data       | Faster thanks to known offsets & types                |
| Validation       | Requires external schema (JSON-Schema)  | Built-in schema definitions & validation              |
| Evolution        | Manual version discipline               | Field tags/defaults simplify schema evolution         |
| Security         | Human-readable (easy to leak secrets)   | Binary/encoded (harder to inspect casually)           |

\*If TOON is implemented as a ProtoBuf/FlatBuffers/Apache Arrow style format.

### Using TOON in this project
1. **Schema Definition**
   - Describe `UserSnapshot` in `.toon` schema (or ProtoBuf/Arrow).
   - Include nested structures: profile, balances[], transactions[], bots[], marketData[].
2. **Export Step**
   - After each fetch cycle, serialize:
     - `./data/snapshots/user_123.json`
     - `./data/snapshots/user_123.toon`
   - Store schema version + timestamp in headers.
3. **Trade-Agent Ingestion**
   - Python TOON decoder converts binary into dataclasses/pandas.
   - Use JSON only for debugging; TOON for production due to speed & size.
4. **Benefits Recap**
   - Lower disk/network IO.
   - Guaranteed types → fewer runtime errors in ML pipeline.
   - Easier to enforce schema evolution (backwards compatible).
   - Binary format reduces accidental exposure of sensitive data (public keys, balances).

Implementation tip: if “TOON” is not an existing standard, adopt ProtoBuf/FlatBuffers/Apache Arrow to get tooling and multi-language support immediately.

---

## 4. Required Packages & Tooling

### fetch-data-agent (Node/TypeScript)
- Already in place: `axios`, `dotenv`, `node-cron`, `sqlite`, `sqlite3`, `ts-node`, `typescript`.
- TOON/Binary serialization options (pick one):
  - `protobufjs` (Protocol Buffers encoder/decoder).
  - `flatbuffers` or `apache-arrow` for columnar exports.
  - `ajv` (if sticking with JSON but wanting strong schema validation).
- Optional helpers: `winston`/`pino` for logs, `bullmq` if job queueing becomes necessary.

### trade-agent (Python)
- Core: `langgraph`, `langchain`, `pydantic`, `python-dotenv`.
- Data processing: `pandas`, `numpy`, `sqlalchemy` (or `duckdb`), `pyarrow` (if using Arrow/TOON).
- HTTP/API: `httpx` or `requests`, `tenacity` for retries.
- ML/RL (incremental):
  - Baseline: `scikit-learn`, `lightgbm`, `xgboost`.
  - Advanced: `torch`, `stable-baselines3`, `mlflow` for experiments.
- News/Sentiment: `newsapi-python`, `feedparser`, `textblob`, `transformers` (for custom sentiment models).
- Tooling: `loguru`/`structlog` for logging, `prometheus-client` for metrics, `pytest` for tests.

### Observability & Ops
- Containerization: `docker`, `docker-compose`.
- Scheduling: cron, `apscheduler`, or Kubernetes CronJobs.
- Secrets: `.env` + `python-dotenv` initially, later Vault/Secrets Manager.

---

## 5. Implementation Approaches

1. **Data Interchange Strategy**
   - Keep SQLite as the single source of truth.
   - Export JSON for debugging; TOON (ProtoBuf/Arrow) for production ingestion.
   - Version snapshots with `schema_version`, `generated_at`, `source_agent`.

2. **Trade Pipeline Strategy**
   - MVP: deterministic rules (e.g., rebalance, min balance, trending token buy).
   - Phase 2: hybrid approach (rules + ML probability score). Use offline training on historical trades + price series.
   - Phase 3: reinforcement learning / contextual bandits once enough labeled outcomes exist.

3. **News & Sentiment Strategy**
   - Start with keyword-based sentiment (TextBlob).
   - Upgrade to transformer-based classifier fine-tuned on crypto/news data.
   - LangGraph node applies sentiment multiplier to trade confidence.

4. **Execution & Risk Strategy**
   - Authenticate via service accounts or the existing `BotAuthService`.
   - Enforce per-user and global trade limits (max trades/day, drawdown guards).
   - Support “dry-run” mode for simulation/testing before enabling live trades.

5. **Deployment Strategy**
   - Local dev: run fetch-data-agent + trade-agent sequentially.
   - Prod: Dockerize both agents, orchestrate via cron or Kubernetes.
   - Monitoring: track key metrics (P&L, trades, errors) and set up alerting.

---

## 6. Final Execution Flow (Agreed Approach)

1. **fetch-data-agent cadence**
   - Cron every 20 minutes; updates SQLite plus JSON/TOON snapshots for each user immediately after calling the n-dollar API.
   - Snapshots include schema version + timestamp for freshness checks.

2. **trade-agent scheduling**
   - Runs 5 minutes after each fetch cycle (cron or scheduler) so it always reads fresh data.
   - On startup, verifies `last_fetched_at`; if stale, it can re-hit `/users/data/:id` before continuing or skip the user.

3. **Reference datasets provided by you**
   - `token-strategy-catalog.csv` (per-token strategies, pumpfun stage, risk metadata).
   - `time-series.csv` (historical OHLC/volume/momentum for each token).
   - `rules.csv` (explicit conditions/overrides).
   - Optional: `news_signals.csv`, `user_preferences.csv`, `historical_trades.csv`.
   - All ingested each cycle via pandas, cached, and merged with live snapshots to build feature sets.

4. **DeepSeek news agent**
   - Independent service running every 10–15 minutes.
   - Fetches pumpfun-related headlines/social feeds, asks DeepSeek to score sentiment/trend tags, writes results to `news_signals` table/CSV with timestamps.
   - Trade-agent’s `NewsSentimentNode` pulls the latest signals (only accepts entries newer than e.g. 30 minutes; otherwise falls back to neutral scores).

5. **Trade-agent pipeline**
   - Ingestion nodes load user snapshot (SQLite/JSON/TOON), reference datasets, and news signals.
   - Feature combiner aligns everything per token/user.
   - LangGraph nodes evaluate rules + ML + sentiment and output a `TradeDecision`.
   - Risk/Execution nodes enforce user/global limits and call n-dollar buy/sell APIs using service/bot tokens. Decisions are logged with the data sources used.

6. **Fallbacks & logging**
   - If any dataset (snapshots, reference CSV, news) is missing or stale, trade-agent logs the condition and either pulls fresh data or skips the impacted user/token.
   - Every trade (real or skipped) records reason codes so we can audit and retrain models later.

---

## 4. Immediate Action Items
1. Document snapshot schema & versioning for JSON + TOON outputs.
2. Implement TOON exporter in `fetch-data-agent` (likely via ProtoBuf/Arrow).
3. Scaffold trade-agent repo (Python, LangGraph) with ingestion + execution placeholders.
4. Build LangGraph nodes for MVP pipeline (rule-based first).
5. Integrate n-dollar buy/sell API client with service/bot authentication.
6. Add cron/deployment scripts so trade-agent runs after fetch-data-agent.

---

## 6. Accuracy & Risk Mitigation Strategies (Pumpfun-Specific)

Given the high-risk nature of trading and regulatory accountability, the following strategies are critical for improving trade-agent accuracy and safety:

### 6.1 Pumpfun-Specific Signal Layers
- **Bonding Curve Phase Detection**
  - Classify tokens by their position on pumpfun's bonding curve (early adopter, mid-stage, late).
  - Avoid entering positions when liquidity is critically low or slippage risk is high.
  - Track curve progression over time to identify optimal entry/exit points.
- **Creator Activity Tracking**
  - Monitor on-chain and social signals from token creators.
  - Flag suspicious patterns (e.g., multi-launch behavior, dormant accounts, rug pull indicators).
  - Store creator reputation scores in `token-strategy-catalog.csv`.
- **Liquidity Depth Checks**
  - Integrate live liquidity/pool data before executing trades.
  - Ensure orders won't cause massive slippage or fail due to insufficient liquidity.
  - Set minimum liquidity thresholds per token in risk rules.

### 6.2 Dynamic Risk Scoring System
- **Per-Token Risk Calculation**
  - Combine multiple factors into a unified risk score:
    - Time since launch (newer tokens = higher risk)
    - Volume consistency (irregular volume = higher risk)
    - Whale concentration (top holders percentage)
    - Volatility metrics from time-series data
    - News sentiment stability
  - Store risk scores in reference datasets and update dynamically.
- **Position Sizing Based on Risk**
  - Adjust trade amounts: `TradeDecision.amount = base_size * risk_modifier`
  - Higher risk tokens → smaller positions
  - Lower risk tokens → larger positions (within user limits)
- **Stop-Loss & Take-Profit Thresholds**
  - Set dynamic stop-loss based on token volatility and risk score.
  - Implement trailing stops for profitable positions.

### 6.3 Multi-Model Ensemble Approach
- **Diverse Decision Makers**
  - **Rule Evaluator**: Hard filters and deterministic logic (min balance, max positions, etc.)
  - **Time-Series ML Model**: Momentum/mean reversion predictions from historical patterns
  - **News Sentiment Model**: DeepSeek-powered sentiment analysis
  - **Risk Manager**: Portfolio-level constraints and diversification rules
- **Weighted Voting System**
  - Each model outputs a confidence score and action recommendation.
  - Final decision uses weighted voting: `final_action = weighted_sum(model_outputs)`
  - Reduces over-reliance on a single signal source.
- **Confidence Thresholds**
  - Only execute trades when ensemble confidence exceeds a minimum threshold (e.g., 0.7).
  - Log low-confidence decisions for review without execution.

### 6.4 Real-Time Guardrails & Circuit Breakers
- **Daily P&L Limits**
  - Halt trading if user's daily P&L drops beyond a configurable threshold.
  - Implement per-user and global daily loss limits.
- **Stale Data Protection**
  - No trade execution if user snapshot is older than 30 minutes.
  - No trade execution if news signals are older than 45 minutes.
  - Force refresh or skip user if data freshness check fails.
- **Max Risk Per User**
  - Enforce position sizing limits based on user's total portfolio value.
  - Respect user-specific risk profiles from `user_preferences.csv`.
  - Prevent over-concentration in a single token or category.
- **Anomaly Detection**
  - Monitor for unusual patterns (e.g., rapid price movements, volume spikes).
  - Automatically pause trading for affected tokens until manual review.

### 6.5 Backtesting & Simulation Framework
- **Historical Validation**
  - Run new strategies against historical pumpfun data before deployment.
  - Use `time-series.csv` + archived snapshots to simulate past performance.
  - Calculate key metrics: Sharpe ratio, max drawdown, win rate, average P&L.
- **Shadow Mode**
  - New models/rules run in "shadow mode" for 3-7 days.
  - Log all decisions without executing trades.
  - Compare shadow performance against live trading to validate improvements.
- **A/B Testing**
  - Test multiple strategy variants simultaneously on different user subsets.
  - Measure performance differences and adopt winning strategies.

### 6.6 Continuous Learning & Model Updates
- **Trade Outcome Tracking**
  - Save every executed trade with full context:
    - `historical_trades.csv`: `user_id`, `token_mint`, `action`, `amount`, `price`, `timestamp`, `pnl`, `slippage`, `holding_period`, `risk_score`, `confidence`
  - Track both successful and failed trades for learning.
- **Periodic Model Retraining**
  - Retrain ML models weekly/monthly using latest historical data.
  - Adapt to evolving pumpfun market behaviors and patterns.
  - Version control model artifacts and track performance over time.
- **Feedback Loop Integration**
  - Use actual P&L outcomes to adjust model weights and rule thresholds.
  - Identify and deprecate underperforming strategies.

### 6.7 Alerting & Explainability
- **Decision Transparency**
  - Every trade logs top 3-5 reasons (e.g., "momentum_score > 0.8", "positive_news_sentiment", "low_risk_score", "user_bot_enabled").
  - Store decision rationale in execution logs for audit trails.
- **Real-Time Alerts**
  - Alert on repeated rule triggers or anomalies (e.g., 5+ trades skipped due to stale news).
  - Notify on circuit breaker activations or risk limit breaches.
  - Send alerts for manual review when confidence is low or risk is high.
- **Audit Logging**
  - Comprehensive logging of all inputs, intermediate calculations, and final decisions.
  - Enable post-trade analysis and regulatory compliance.

### 6.8 Tiered Token Whitelist/Blacklist System
- **Curated Token Lists**
  - Maintain whitelist in `token-strategy-catalog.csv` for verified, safe tokens.
  - Maintain blacklist for tokens with known issues (rug pulls, scams, low liquidity).
  - Require tokens to pass baseline due diligence before trading:
    - Verified creator identity
    - Minimum liquidity threshold
    - Positive trend indicators
    - No recent negative news
- **Manual Overrides**
  - Allow rapid blacklisting of suspicious tokens via admin interface or CSV update.
  - Support emergency stop for all trading on specific tokens or categories.

### 6.9 External Data Integration
- **Pumpfun Analytics APIs**
  - Integrate pumpfun-specific analytics endpoints (if available) for:
    - Live order book data
    - Token leaderboard rankings
    - Creator verification status
    - Bonding curve metrics
- **On-Chain Monitoring**
  - Real-time watchers for rug pull indicators:
    - Mass sell-offs (large holder exits)
    - Liquidity removal
    - Suspicious transaction patterns
  - Trigger immediate exit or trading halt when detected.
- **Social Signal Aggregation**
  - Monitor Farcaster, Telegram, Twitter for token-specific chatter.
  - Correlate social volume with price movements for early trend detection.

### 6.10 Regulatory & Compliance Safeguards
- **User Consent & Preferences**
  - Respect user-defined trading preferences (opt-in/opt-out per token).
  - Store consent records and trading authorizations.
- **Position Limits**
  - Enforce regulatory position size limits per user and globally.
  - Prevent market manipulation through coordinated trading.
- **Transaction Reporting**
  - Generate detailed reports for compliance audits.
  - Track all trades, decisions, and risk metrics for regulatory review.

---

## 7. Long-Term Enhancements
- Reinforcement learning or portfolio optimization models.
- Social signal ingestion (Farcaster, Telegram sentiment).
- Web dashboard for live monitoring (positions, P&L, news links).
- Auto-stop/circuit breakers when drawdown exceeds threshold.
- Multi-agent strategies (e.g., scalper vs. swing trader profiles per user).

---

This plan keeps the agents decoupled, allows gradual ML integration, and leverages TOON for high-performance, typed data exchange once the JSON pipeline is validated.