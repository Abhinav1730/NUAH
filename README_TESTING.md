# Testing Guide - Production Ready

This guide explains how to test each agent individually and the complete system.

## Quick Start

### Test All Agents at Once

```powershell
# From project root
cd "C:\Users\Abhinav Saxena\Desktop\NUAH"
python test_all_agents.py
```

### Test Individual Agents

```powershell
# News Agent
cd news-agent
.venv\Scripts\activate
python test_agent.py

# Trend Agent
cd ../trend-agent
.venv\Scripts\activate
python test_agent.py

# Rules Agent
cd ../rules-agent
.venv\Scripts\activate
python test_agent.py

# Trade Agent
cd ../trade-agent
.venv\Scripts\activate
python test_agent.py
```

## What Each Test Does

### 1. News Agent Test (`news-agent/test_agent.py`)

**What it tests:**
- Generates dummy time-series and token catalog data
- Runs news-agent pipeline
- Validates output CSV structure and data ranges

**Expected output:**
- ✅ `data/news_signals.csv` with sentiment scores
- ✅ All sentiment scores between -1 and 1
- ✅ All confidence scores between 0 and 1

### 2. Trend Agent Test (`trend-agent/test_agent.py`)

**What it tests:**
- Generates dummy time-series data
- Runs trend-agent pipeline
- Validates trend signals and catalog updates

**Expected output:**
- ✅ `data/trend_signals.csv` with trend scores
- ✅ `data/token_strategy_catalog.csv` updated
- ✅ Trend scores between -1 and 1
- ✅ Stages are "early", "mid", or "late"

### 3. Rules Agent Test (`rules-agent/test_agent.py`)

**What it tests:**
- Generates dummy rules, user preferences, and token catalog
- Runs rules-agent pipeline
- Validates rule evaluations per user/token

**Expected output:**
- ✅ `data/rule_evaluations.csv` with per-user evaluations
- ✅ All evaluations have valid boolean "allowed" field
- ✅ Confidence scores between 0 and 1

### 4. Trade Agent Test (`trade-agent/test_agent.py`)

**What it tests:**
- Creates dummy SQLite database with user data
- Generates all required CSV files
- Runs complete LangGraph pipeline
- Validates trade decisions and audit logs

**Expected output:**
- ✅ Trade decisions generated for test users
- ✅ Audit logs in `data/historical_trades.csv`
- ✅ No errors in pipeline execution

## Test Data

All test scripts generate dummy data automatically:
- **Users**: 2-3 test users (IDs: 101, 202, 303)
- **Tokens**: MintAlpha123, MintBeta456, MintGamma789
- **Time-series**: 10-20 data points per token
- **All data**: Realistic but synthetic values

## Production Checklist

Before deploying to production, ensure:

- [ ] All individual agent tests pass
- [ ] Master test script (`test_all_agents.py`) passes
- [ ] No errors in logs
- [ ] CSV files are created with correct structure
- [ ] SQLite database is populated correctly
- [ ] Trade decisions are logged properly

## Troubleshooting

### Import Errors

If you get "ModuleNotFoundError":
```powershell
# Make sure you're in the agent directory
cd news-agent  # or trend-agent, rules-agent, trade-agent

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Path Errors

If you get path-related errors:
- Make sure you're running from the agent's directory
- Check that `../data` directory exists
- Verify relative paths in `.env` files

### Empty Output Files

If CSV files are empty:
- Check that dummy data generation succeeded
- Verify file permissions
- Check that agents are running in dry-run mode (for testing)

## Running Tests Before Production Deployment

1. **Run all tests:**
   ```powershell
   python test_all_agents.py
   ```

2. **Review output:**
   - Check for any ❌ failures
   - Verify all ✅ passed tests
   - Review generated CSV files

3. **If all pass:**
   - System is ready for production
   - You can deploy with confidence

4. **If any fail:**
   - Review error messages
   - Fix issues in the failing agent
   - Re-run tests until all pass

## Next Steps After Testing

1. **Train ML Models:**
   ```powershell
   cd trade-agent
   python scripts/train_models.py --data-dir ../data --models-dir ./models
   ```

2. **Run in Production Mode:**
   - Set `DRY_RUN=false` in `.env` files
   - Configure real API keys
   - Start agents with production schedulers

3. **Monitor:**
   - Check audit logs regularly
   - Monitor API usage
   - Review trade decisions

