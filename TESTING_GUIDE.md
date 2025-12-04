# Complete Testing Guide

## Prerequisites

### 1. Software Requirements

```bash
# Python 3.9+ (check with: python --version)
# Node.js 18+ (check with: node --version)
# Git (for cloning if needed)
```

### 2. API Keys Required

You need these API keys in your `.env` files:

| Agent | Required Keys | Where to Get |
|-------|--------------|--------------|
| **news-agent** | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| **trend-agent** | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| **rules-agent** | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| **trade-agent** | `GOOGLE_GEMINI_API_KEY` | https://makersuite.google.com/app/apikey |
| **trade-agent** | `API_TOKEN` (n-dollar JWT) | From your n-dollar server |
| **fetch-data-agent** | (Already configured) | n-dollar API credentials |

---

## Step-by-Step Testing Process

### Phase 1: Environment Setup

#### 1.1 Install Python Dependencies

```bash
# Navigate to each agent directory and install dependencies

# News Agent
cd news-agent
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Trend Agent
cd ../trend-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Rules Agent
cd ../rules-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Trade Agent (most dependencies)
cd ../trade-agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

#### 1.2 Verify .env Files

Check that each agent has a `.env` file with required keys:

```bash
# news-agent/.env
OPENROUTER_API_KEY=sk-or-v1-...
NEWS_AGENT_DATA_DIR=../data
NEWS_AGENT_REFERER=https://nuah.local
NEWS_AGENT_APP_TITLE=NUAH News Agent

# trend-agent/.env
OPENROUTER_API_KEY=sk-or-v1-...
TREND_AGENT_DATA_DIR=../data
TREND_AGENT_REFERER=https://nuah.local
TREND_AGENT_APP_TITLE=NUAH Trend Agent

# rules-agent/.env
OPENROUTER_API_KEY=sk-or-v1-...
RULES_AGENT_DATA_DIR=../data
RULES_AGENT_REFERER=https://nuah.local
RULES_AGENT_APP_TITLE=NUAH Rules Agent

# trade-agent/.env
GOOGLE_GEMINI_API_KEY=AIza...
API_TOKEN=your_ndollar_jwt_token
SQLITE_PATH=../fetch-data-agent/data/user_data.db
SNAPSHOT_DIR=../fetch-data-agent/data/snapshots
DATA_DIR=../data
API_BASE_URL=https://api.ndollar.org/api/v1
GEMINI_MODEL=gemini-2.5-pro
DRY_RUN=true  # Start with dry-run!
```

---

### Phase 2: Test Individual Agents (Dry Run)

#### 2.1 Test News Agent

```bash
cd news-agent
.venv\Scripts\activate
python main.py run --dry-run
```

**Expected Output:**
- ✅ "Stored X news signals."
- ✅ Check `../data/news_signals.csv` has new rows

**What to Check:**
- CSV file is created/updated
- Timestamps are recent
- Sentiment scores are between -1 and 1

#### 2.2 Test Trend Agent

```bash
cd ../trend-agent
.venv\Scripts\activate
python main.py run --dry-run
```

**Expected Output:**
- ✅ "Trend agent stored X signals."
- ✅ Check `../data/trend_signals.csv` has new rows
- ✅ Check `../data/token_strategy_catalog.csv` is updated

**What to Check:**
- Trend scores are between -1 and 1
- Stage values are "early", "mid", or "late"
- Risk scores are between 0 and 1

#### 2.3 Test Rules Agent

```bash
cd ../rules-agent
.venv\Scripts\activate
python main.py run --dry-run
```

**Expected Output:**
- ✅ "Saved X rule evaluations."
- ✅ Check `../data/rule_evaluations.csv` has new rows

**What to Check:**
- Each user has evaluations for their tokens
- `allowed` field is boolean
- `max_daily_trades` and `max_position_ndollar` are reasonable

---

### Phase 3: Test with Real API Calls (Optional)

Once dry-run works, test with real API calls:

```bash
# News Agent (real DeepSeek calls)
cd news-agent
python main.py run  # Remove --dry-run

# Trend Agent (real DeepSeek calls)
cd ../trend-agent
python main.py run

# Rules Agent (real DeepSeek calls)
cd ../rules-agent
python main.py run
```

**What to Check:**
- API calls succeed (no 401/403 errors)
- Responses are valid JSON
- CSV files are updated with real sentiment/trend data

---

### Phase 4: Train ML Models (Trade Agent)

Before testing trade-agent, you need trained ML models:

```bash
cd trade-agent
.venv\Scripts\activate

# Train models from historical data
python scripts/train_models.py --data-dir ../data --models-dir ./models
```

**Expected Output:**
- ✅ "Training action classifier..."
- ✅ "Training amount regressor..."
- ✅ "Training confidence calibrator..."
- ✅ "Models saved to ./models/"

**What to Check:**
- `./models/action_classifier.pkl` exists
- `./models/amount_regressor.pkl` exists
- `./models/confidence_calibrator.pkl` exists
- Training metrics are printed (accuracy, R², etc.)

**Note:** If you don't have enough historical data, models will still be created but may have lower accuracy. The system will fall back to rule-based evaluation.

---

### Phase 5: Test Trade Agent (Dry Run)

#### 5.1 Ensure fetch-data-agent has data

```bash
# Make sure fetch-data-agent has run and populated SQLite
# Check: fetch-data-agent/data/user_data.db exists
# Check: fetch-data-agent/data/snapshots/ has JSON files (if enabled)
```

#### 5.2 Run Trade Agent in Dry Run Mode

```bash
cd trade-agent
.venv\Scripts\activate

# Test with specific user IDs (if you know them)
python main.py --user-ids 101,202

# Or let it discover users automatically
python main.py
```

**Expected Output:**
- ✅ "Processing X user(s)"
- ✅ "User X decision: buy/sell/hold token=... amount=... conf=..."
- ✅ "[Dry Run] Would execute buy/sell ..." (if action is buy/sell)
- ✅ Check `../data/historical_trades.csv` has new audit log entries

**What to Check:**
- No errors in logs
- Decisions are logged with reasons
- Confidence scores are between 0 and 1
- Amounts are reasonable (not negative, not too large)
- Audit log entries are created

---

### Phase 6: Test Trade Agent (Live - CAREFUL!)

**⚠️ WARNING: This will execute real trades!**

Only proceed if:
- ✅ You've tested everything in dry-run
- ✅ You trust the ML models
- ✅ You have proper risk limits set
- ✅ You're ready to monitor trades

```bash
cd trade-agent

# Edit .env and set:
DRY_RUN=false

# Run with live execution
python main.py --user-ids 101  # Test with one user first!
```

**What to Monitor:**
- API calls to n-dollar succeed
- Trades are executed correctly
- Audit logs capture everything
- No unexpected errors

---

## Troubleshooting

### Issue: "No snapshot available for user X"

**Solution:**
- Run `fetch-data-agent` first to populate SQLite
- Check `SQLITE_PATH` in trade-agent `.env` is correct
- Verify user exists in database

### Issue: "Models not found" or "ML predictor using fallback"

**Solution:**
- Run `python scripts/train_models.py` to create models
- Check `MODELS_DIR` path in config
- Models directory exists and has `.pkl` files

### Issue: "CSV file not found" or "Empty DataFrame"

**Solution:**
- Run news-agent, trend-agent, rules-agent first
- Check `DATA_DIR` path is correct (should be `../data`)
- Verify CSV files exist in the data directory

### Issue: API Key Errors (401, 403)

**Solution:**
- Verify API keys are correct in `.env` files
- Check keys haven't expired
- For OpenRouter: Ensure `REFERER` and `APP_TITLE` are set
- For Gemini: Check API key has proper permissions

### Issue: "Confidence below threshold" - no trades executed

**Solution:**
- This is normal! System is being conservative
- Lower `DECISION_CONFIDENCE_THRESHOLD` in trade-agent `.env` (default 0.7)
- Or improve ML model training with more data

### Issue: "Stale data" warnings

**Solution:**
- Run auxiliary agents (news/trend/rules) more frequently
- Adjust freshness windows in trade-agent config:
  - `NEWS_FRESHNESS_MINUTES=45`
  - `TREND_FRESHNESS_MINUTES=60`
  - `SNAPSHOT_FRESHNESS_MINUTES=30`

---

## Quick Test Checklist

- [ ] All Python environments created and dependencies installed
- [ ] All `.env` files configured with API keys
- [ ] News agent runs in dry-run mode
- [ ] Trend agent runs in dry-run mode
- [ ] Rules agent runs in dry-run mode
- [ ] ML models trained successfully
- [ ] Trade agent runs in dry-run mode
- [ ] Audit logs are created
- [ ] CSV files are updated correctly
- [ ] (Optional) Live API calls work
- [ ] (Optional) Live trade execution works

---

## Recommended Testing Schedule

For production, set up cron jobs or schedulers:

```bash
# Every 20 minutes: fetch-data-agent
# Every 15 minutes: news-agent, trend-agent
# Every 30 minutes: rules-agent
# Every 30 minutes: trade-agent (5 min after fetch-data-agent)
```

Example cron (Linux/Mac):
```bash
*/20 * * * * cd /path/to/fetch-data-agent && npm run start
*/15 * * * * cd /path/to/news-agent && .venv/bin/python main.py run
*/15 * * * * cd /path/to/trend-agent && .venv/bin/python main.py run
*/30 * * * * cd /path/to/rules-agent && .venv/bin/python main.py run
35 * * * * cd /path/to/trade-agent && .venv/bin/python main.py
```

Windows Task Scheduler:
- Create tasks for each agent with appropriate intervals
- Use PowerShell scripts to activate venv and run commands

---

## Next Steps After Testing

1. **Monitor Performance**: Track P&L, win rate, confidence scores
2. **Retrain Models**: Weekly/monthly retraining with new historical data
3. **Tune Thresholds**: Adjust confidence thresholds based on results
4. **Add Features**: Enhance ML models with more features as data grows
5. **Scale Up**: Gradually increase number of users/tokens

---

## Support

If you encounter issues:
1. Check logs in each agent directory
2. Verify all paths are correct (use absolute paths if needed)
3. Ensure all CSV files have proper headers
4. Check API rate limits haven't been exceeded
5. Review the audit logs in `historical_trades.csv` for clues

