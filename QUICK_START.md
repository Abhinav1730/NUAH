# Quick Start Guide - Fix Dependencies

## Step 1: Install All Dependencies

Run the PowerShell script to install all dependencies:

```powershell
cd C:\Users\Abhinav Saxena\Desktop\NUAH
.\install_all_dependencies.ps1
```

Or manually install in each agent:

```powershell
# Shared dependencies
cd shared
pip install -r requirements.txt
cd ..

# News-agent
cd news-agent
pip install -r requirements.txt
cd ..

# Trend-agent
cd trend-agent
pip install -r requirements.txt
cd ..

# Rules-agent
cd rules-agent
pip install -r requirements.txt
cd ..

# Trade-agent
cd trade-agent
pip install -r requirements.txt
cd ..
```

## Step 2: Run Integration Tests

```powershell
cd C:\Users\Abhinav Saxena\Desktop\NUAH
python test_integration.py
```

This will test:
- ✅ Imports
- ✅ Configuration loading
- ✅ API connectivity
- ✅ Data fetching
- ✅ Denom mapping

## Step 3: Test Individual Agents

### News Agent
```powershell
cd news-agent
python main.py run --dry-run
```

### Trend Agent
```powershell
cd trend-agent
python main.py run --dry-run
```

### Rules Agent
```powershell
cd rules-agent
python main.py run --dry-run
```

### Trade Agent
```powershell
cd trade-agent
# Make sure DRY_RUN=true in .env
python main.py
```

## What Was Fixed

1. ✅ **Pydantic BaseSettings**: Updated to use `pydantic-settings` package
2. ✅ **Field Validators**: Updated from `@validator` to `@field_validator` for Pydantic v2
3. ✅ **Requirements**: Added `pydantic-settings>=2.0.0` to all agent requirements
4. ✅ **Syntax Error**: Fixed missing closing brace in `ndollar_client.py`
5. ✅ **Dependencies**: Added `requests` to all agent requirements

## Common Issues

### "ModuleNotFoundError: No module named 'httpx'"
- Solution: Run `pip install httpx` in the agent's virtual environment

### "ModuleNotFoundError: No module named 'langgraph'"
- Solution: Run `pip install langgraph` in trade-agent's virtual environment

### "PydanticImportError: BaseSettings has been moved"
- Solution: Run `pip install pydantic-settings` (already fixed in code)

### "Cannot connect to http://localhost:8080"
- Solution: Make sure nuahchain-backend is running
- Test with: `curl http://localhost:8080/health`

## Next Steps

1. ✅ Install dependencies (Step 1)
2. ✅ Run integration tests (Step 2)
3. ✅ Configure `.env` files with API tokens
4. ✅ Test individual agents (Step 3)
5. ✅ Run full pipeline


