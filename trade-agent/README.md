# trade-agent

Python service that analyzes user snapshots produced by `fetch-data-agent` and executes buy/sell trades on n-dollar on behalf of users. Built with LangGraph for composable decision pipelines.

## Project layout

```
trade-agent/
├── requirements.txt
├── README.md
├── main.py
└── src/
    ├── config.py
    ├── data_ingestion/
    │   ├── __init__.py
    │   ├── csv_loader.py
    │   ├── snapshot_loader.py
    │   └── sqlite_loader.py
    ├── execution/
    │   ├── __init__.py
    │   └── ndollar_client.py
    ├── graph/
    │   ├── __init__.py
    │   └── state.py
    ├── logging/
    │   ├── __init__.py
    │   └── audit_logger.py
    ├── models/
    │   ├── __init__.py
    │   └── rule_evaluator.py
    ├── pipeline/
    │   ├── __init__.py
    │   └── trade_pipeline.py
    └── services/
        ├── __init__.py
        └── gemini_client.py
```

Each component lives in its own class/module so we can extend or replace them independently (e.g. swap out the rule evaluator for an ML model).

## Quick start

```bash
cd trade-agent
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Configure environment
copy .env.example .env

# Run trade pipeline once
python main.py
```

### Continuous scheduling

To keep the pipeline in lockstep with `fetch-data-agent`, run the built-in
scheduler. It waits for fresh snapshots (defaults: fetch every 20 min, trade 5 min
after each fetch) before invoking the pipeline.

```bash
python scheduler.py --interval-minutes 30 --initial-delay-minutes 5
```

The scheduler refuses to run if the newest `last_fetched_at` timestamp in the
SQLite database is older than the configured `snapshot_freshness_minutes`, which
ensures we never trade on stale data.

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SQLITE_PATH` | Path to `fetch-data-agent` SQLite DB | `../fetch-data-agent/data/user_data.db` |
| `SNAPSHOT_DIR` | Directory containing JSON/TOON snapshots | `../fetch-data-agent/data/snapshots` |
| `DATA_DIR` | Shared CSV directory produced by other agents | `../data` |
| `API_BASE_URL` | n-dollar API base | `https://api.ndollar.org/api/v1` |
| `API_TOKEN` | JWT for trading | _required_ |
| `GOOGLE_GEMINI_API_KEY` | Used for final decision fusion | _required for live trading_ |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.5-pro` |
| `MODELS_DIR` | Directory containing ML artifacts | `./models` |
| `USER_IDS` | Comma-separated user IDs to process (optional) | empty |
| `DRY_RUN` | `true` to skip actual HTTP trades | `false` |

## ML pipeline

The `ml_signal` node now consumes scikit-learn/LightGBM models:

1. `FeatureEngineer` aggregates portfolio, time-series, and sentiment features.
2. `MLPredictor` loads pickled models from `MODELS_DIR` (action, amount, confidence).
3. If no models exist, the pipeline automatically falls back to deterministic rules.

### Training models

```bash
cd trade-agent
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# Train models from shared data/ CSVs
python scripts/train_models.py \
  --data-dir ../data \
  --models-dir ./models
```

Artifacts written:

- `models/action_model.pkl`
- `models/amount_model.pkl`
- `models/confidence_model.pkl`
- `models/feature_columns.pkl`

Re-run the trainer whenever new historical trades/time-series data is available.

## Extending

- Add ML models in `src/models/` and wire them into `TradePipeline`.
- Implement TOON decoding in `snapshot_loader.py` when the binary format is finalized.
- Enhance `ndollar_client.py` with token refresh, retries, and WebSocket streaming if needed.

## Status

LangGraph nodes (ingestion → preprocessing → rule checks → sentiment → ML signal → risk manager → decision → execution) are wired end-to-end. The pipeline expects auxiliary agents (`news-agent`, `trend-agent`, `rules-agent`) to refresh the shared CSVs before each run.

