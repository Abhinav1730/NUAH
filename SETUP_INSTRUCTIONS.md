# Setup Instructions for NuahChain Integration

## Prerequisites

1. **nuahchain-backend must be running** on `http://localhost:8080` (or your configured URL)
2. **Get a JWT token** from nuahchain-backend (via login/register endpoint)

## Step 1: Install Shared Dependencies

The shared folder needs `requests` and `pandas`:

```bash
cd NUAH/shared
pip install -r requirements.txt
```

Or install directly:
```bash
pip install requests>=2.31.0 pandas>=2.0.0
```

## Step 2: Configure Environment Variables

Create `.env` files in each agent folder:

### `news-agent/.env`
```bash
NUAHCHAIN_API_BASE_URL=http://localhost:8080
NUAHCHAIN_API_TOKEN=your_jwt_token_here
NEWS_AGENT_USE_REAL_DATA=true
```

### `trend-agent/.env`
```bash
NUAHCHAIN_API_BASE_URL=http://localhost:8080
NUAHCHAIN_API_TOKEN=your_jwt_token_here
TREND_AGENT_USE_REAL_DATA=true
```

### `rules-agent/.env`
```bash
NUAHCHAIN_API_BASE_URL=http://localhost:8080
NUAHCHAIN_API_TOKEN=your_jwt_token_here
RULES_AGENT_USE_REAL_DATA=true
```

### `trade-agent/.env`
```bash
API_BASE_URL=http://localhost:8080
API_TOKEN=your_jwt_token_here
# ... other existing trade-agent config
```

## Step 3: Test the Integration

### Test 1: Check if nuahchain-backend is accessible
```bash
curl http://localhost:8080/health
```

### Test 2: Test news-agent
```bash
cd news-agent
python main.py run --dry-run
```

### Test 3: Test trade-agent (dry run)
```bash
cd trade-agent
# Make sure DRY_RUN=true in .env
python main.py
```

## Step 4: Run Data Sync (Optional but Recommended)

To populate CSV files with real data, you can create a simple script:

```python
# sync_data.py in NUAH root
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "shared"))

from nuahchain_client import NuahChainClient
from data_sync_service import DataSyncService

client = NuahChainClient(
    base_url="http://localhost:8080",
    api_token="your_token_here"
)

service = DataSyncService(client, Path("data"))
results = service.sync_all()
print(f"Sync results: {results}")
```

## Troubleshooting

### Import Errors
If you see `ModuleNotFoundError: No module named 'nuahchain_client'`:
- Make sure you're running from the agent's directory
- Check that `shared/` folder exists at `NUAH/shared/`
- Verify Python can find the shared folder (agents add it to sys.path automatically)

### API Connection Errors
- Verify nuahchain-backend is running: `curl http://localhost:8080/health`
- Check your API token is valid
- Verify `NUAHCHAIN_API_BASE_URL` is correct

### Token Mapping Issues
- The denom_mapper will build its cache as it encounters tokens
- If a token_mint doesn't map to denom, check the mapping cache
- You may need to manually add mappings for specific tokens

### Fallback to CSV
- If API is unavailable, agents will automatically use CSV files
- Check logs for "Falling back to CSV data" messages
- This is expected behavior and maintains backward compatibility

## Current Status

✅ **Code Integration**: Complete
✅ **Import Paths**: Fixed
⚠️ **Dependencies**: Need to install `requests` and `pandas` in shared folder
⚠️ **Configuration**: Need to set environment variables
⚠️ **Testing**: Should test each agent individually

## What Will Work Immediately

1. **With proper setup**: All agents will fetch real data from nuahchain-backend
2. **Trade execution**: Will work if API token is valid and user has sufficient balance
3. **Fallback mode**: If API unavailable, agents use CSV files (backward compatible)

## What Might Need Adjustment

1. **Amount conversion**: Currently assumes 6 decimals (1 NDOLLAR = 1,000,000 micro-units)
   - If your tokens use different decimals, adjust in `ndollar_client.py`

2. **Denom mapping**: Initial mapping is automatic but may need refinement
   - Check `shared/denom_mapper.py` if tokens aren't mapping correctly

3. **Time-series data**: Currently simplified - may need enhancement for production
   - See `shared/data_sync_service.py` for time-series generation



