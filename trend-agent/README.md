# trend-agent

Transforms raw price/time-series snapshots into qualitative trend assessments using DeepSeek via OpenRouter. The agent updates `token_strategy_catalog.csv` with the latest bonding curve phases, risk multipliers, and trend scores so `trade-agent` can consume structured insights each run.

## Usage

```bash
cd trend-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py run
```

## Environment variables

| Variable | Description |
| --- | --- |
| `OPENROUTER_API_KEY` | Required for DeepSeek |
| `TREND_AGENT_DATA_DIR` | Override shared data dir (default `../data`) |
| `TREND_AGENT_REFERER` | HTTP referer header for OpenRouter |
| `TREND_AGENT_APP_TITLE` | X-Title header |

## Outputs

1. Appends high-level rows to `trend_signals.csv` (trend_score, stage, liquidity flags, summary).
2. Refreshes the matching rows inside `token_strategy_catalog.csv` with the new stage & risk measurements.

Schedule this agent shortly after `fetch-data-agent` so that `trade-agent` always reads fresh analytics (< 60 minutes old).

