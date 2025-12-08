# rules-agent

Evaluates declarative guardrails (global rules + user preferences) and emits structured allowances for `trade-agent`. The agent leans on DeepSeek (via OpenRouter) to translate complex rule sets into per-user enforcement artifacts.

## Setup

```bash
cd rules-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py run
```

## Environment

| Variable | Description |
| --- | --- |
| `OPENROUTER_API_KEY` | Required for DeepSeek reasoning |
| `RULES_AGENT_DATA_DIR` | Shared data dir override |
| `RULES_AGENT_REFERER` | Referer header for OpenRouter |
| `RULES_AGENT_APP_TITLE` | X-Title header |

## Outputs

- Writes per-user/token policy rows to `rule_evaluations.csv`:
  - `allowed` (bool)
  - `max_daily_trades`
  - `max_position_ndollar`
  - `reason`
  - `confidence`

`trade-agent` consumes this file to short-circuit executions that would violate governance requirements.


