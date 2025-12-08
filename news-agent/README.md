# news-agent

Generates near-real-time sentiment snapshots for pump.fun tokens by blending cached metrics with DeepSeek analysis (served via OpenRouter). Results are written to the shared data directory (`../data/news_signals.csv`) so that `trade-agent` can consume fresh news every run.

## Quick start

```bash
cd news-agent
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# create .env (see Environment section)
python main.py --tokens MintAlpha123 MintBeta456
```

## Environment

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Required to call DeepSeek via OpenRouter |
| `NEWS_AGENT_DATA_DIR` | Override path to shared data directory (default `../data`) |
| `NEWS_AGENT_REFERER` | Optional referer header required by OpenRouter |
| `NEWS_AGENT_APP_TITLE` | Value for `X-Title` header |

## Outputs

- Appends structured rows to `news_signals.csv` with timestamps, token mint, sentiment score, confidence, and a concise summary.
- Maintains provenance fields (source=`deepseek` or fallback) making it easy to audit trade decisions later.

## Scheduling

Run every 10–15 minutes (cron/Task Scheduler/k8s CronJob). The agent enforces freshness in the CSV by always writing ISO timestamps and trimming duplicate signal IDs.


