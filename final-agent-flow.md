# NUAH Agent System Flow

## Overview Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           nuahchain-backend (Go)                            │
│  • REST API server on localhost:8080                                        │
│  • PostgreSQL database (users, wallets, tokens)                             │
│  • Blockchain connection for trading                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ HTTP API calls
                                    │ (JWT authenticated)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        fetch-data-agent (TypeScript)                        │
│  • Fetches user data from nuahchain-backend                                 │
│  • Stores SNAPSHOTS in SQLite database                                      │
│  • Runs on schedule (every 20 minutes)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Writes to SQLite
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SQLite Database (user_data.db)                       │
│  • users table (profile snapshots)                                          │
│  • user_balances table (token balances)                                     │
│  • user_transactions table (trade history)                                  │
│  • user_portfolios table (portfolio snapshots)                              │
│  • news_signals, trend_signals, rule_evaluations (from other agents)        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ Reads from SQLite
                                    │
┌───────────────┬───────────────┬───────────────┬───────────────┐
│  news-agent   │  trend-agent  │  rules-agent  │  trade-agent  │
│  (Python)     │  (Python)     │  (Python)     │  (Python)     │
│               │               │               │               │
│ Analyzes news │ Analyzes      │ Evaluates     │ Makes trade   │
│ sentiment     │ price trends  │ trading rules │ decisions     │
└───────────────┴───────────────┴───────────────┴───────────────┘
```

---

## Data Flow Summary

| Step | Component | Action | Data Store |
|------|-----------|--------|------------|
| 1 | nuahchain-backend | User registers, creates tokens | PostgreSQL |
| 2 | fetch-data-agent | Fetches user data via API | SQLite |
| 3 | news-agent | Analyzes news, writes signals | SQLite |
| 4 | trend-agent | Analyzes trends, writes signals | SQLite |
| 5 | rules-agent | Evaluates rules, writes evaluations | SQLite |
| 6 | trade-agent | Reads all data, makes trade decision | SQLite → API |

---

## Step-by-Step Flow

### Step 1: nuahchain-backend (Data Source)

```
User registers → Creates wallet → Can create/buy/sell tokens
                     │
                     ▼
            PostgreSQL Database
            ┌──────────────────┐
            │ users            │ (id, email, username)
            │ wallets          │ (address, encrypted keys)
            │ tokens           │ (denom, name, symbol)
            │ sessions         │ (JWT tokens)
            └──────────────────┘
```

**Test Data Created:**
- User: `testbyabhinav@gmail.com` (ID: 1)
- Wallet: `nuah10e2dde1b41cbeeca5a700c828df18759381f61c7`
- 5 Test Coins: TBTC, TETH, TSOL, TADA, TDOT

### Step 2: fetch-data-agent (Data Collector)

```
Every 20 minutes:
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. Call /api/users/me                   │ → Get user profile
│ 2. Call /api/users/balances             │ → Get token balances
│ 3. Call /api/users/balances/history     │ → Get transactions
│ 4. Call /api/tokens/market              │ → Get market data
└─────────────────────────────────────────┘
                     │
                     ▼
            Creates a SNAPSHOT
            (Point-in-time capture of user's state)
                     │
                     ▼
            Saves to SQLite Database
```

---

## What is a SNAPSHOT?

A **snapshot** is a point-in-time capture of a user's complete financial state:

```typescript
interface UserData {
  userId: number;
  profile: {
    id: number;
    username: string;
    email: string;
    cosmos_address: string;  // Wallet address
  };
  balances: [
    { token_mint: "factory/.../TBTC", balance: "1000000" },
    { token_mint: "factory/.../TETH", balance: "2000000" },
    // ... all token holdings
  ];
  transactions: [
    { type: "buy", token: "TBTC", amount: "100", timestamp: "..." },
    // ... recent trades
  ];
  portfolio: {
    tokens: [...],
    totalValueNDollar: "150.50",
    count: 5
  };
  marketData: [
    { token_mint: "TBTC", price: "0.01", volume_24h: "..." },
    // ... current prices
  ];
  fetchedAt: "2025-12-09T17:00:00Z";  // When snapshot was taken
}
```

### Why Snapshots?

| Reason | Explanation |
|--------|-------------|
| Historical Data | Trade decisions need past data, not just current state |
| Change Detection | Can detect: "Did user's balance increase/decrease?" |
| Trend Analysis | Enables: "Is this user's portfolio growing?" |
| Consistency | Provides consistent view for all agents to read |
| Offline Analysis | Agents can analyze without constant API calls |

---

## SQLite Database Schema

Location: `fetch-data-agent/data/user_data.db`

### Core Tables

```sql
-- User profiles (from /api/users/me)
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    email TEXT,
    public_key TEXT,           -- Wallet address
    last_fetched_at TEXT,      -- When last snapshot was taken
    updated_at TEXT
);

-- Token balances (from /api/users/balances)
CREATE TABLE user_balances (
    user_id INTEGER,
    token_mint TEXT,           -- e.g., "factory/.../TBTC"
    balance TEXT,              -- e.g., "1000000" (in micro-units)
    updated_at TEXT
);

-- Transaction history (from /api/users/balances/history)
CREATE TABLE user_transactions (
    user_id INTEGER,
    transaction_type TEXT,     -- "buy", "sell", "transfer"
    token_mint TEXT,
    amount TEXT,
    signature TEXT,            -- Transaction hash
    timestamp TEXT
);

-- Portfolio snapshots (calculated from balances + market prices)
CREATE TABLE user_portfolios (
    user_id INTEGER,
    total_value_ndollar TEXT,  -- Total portfolio value
    total_value_sol TEXT,
    token_count INTEGER,
    snapshot_json TEXT,        -- Full JSON snapshot
    created_at TEXT
);
```

### Signal Tables (Written by Analysis Agents)

```sql
-- From news-agent
CREATE TABLE news_signals (
    token_mint TEXT,
    headline TEXT,
    sentiment_score REAL,      -- -1.0 (bearish) to 1.0 (bullish)
    confidence REAL,           -- 0.0 to 1.0
    timestamp TEXT
);

-- From trend-agent
CREATE TABLE trend_signals (
    token_mint TEXT,
    trend TEXT,                -- "bullish", "bearish", "neutral"
    confidence REAL,
    timestamp TEXT
);

-- From rules-agent
CREATE TABLE rule_evaluations (
    user_id INTEGER,
    token_mint TEXT,
    allowed INTEGER,           -- 1=can trade, 0=blocked
    max_position_ndollar REAL,
    max_daily_trades INTEGER,
    reason TEXT,
    confidence REAL
);

-- User preferences
CREATE TABLE user_preferences (
    user_id INTEGER PRIMARY KEY,
    max_position_ndollar REAL, -- Max amount per trade
    max_trades_per_day INTEGER,
    risk_level TEXT            -- "low", "medium", "high"
);
```

---

## Trade Agent Pipeline (LangGraph)

When `trade-agent` runs for a user, it executes this pipeline:

```
┌──────────────────────────────────────────────────────────────┐
│                    LangGraph Pipeline                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. LOAD_CONTEXT                                             │
│     └─ Read user snapshot from SQLite                        │
│     └─ Read news_signals for user's tokens                   │
│     └─ Read trend_signals for user's tokens                  │
│     └─ Read rule_evaluations for user                        │
│                        ▼                                     │
│  2. PREPROCESS                                               │
│     └─ Calculate portfolio value                             │
│     └─ Determine deployable capital (25% of portfolio)       │
│     └─ Count today's trades                                  │
│                        ▼                                     │
│  3. RULE_CHECK                                               │
│     └─ Check: Has user exceeded daily trade limit?           │
│     └─ Check: Which tokens is user allowed to trade?         │
│     └─ Check: What are position size limits?                 │
│                        ▼                                     │
│  4. SENTIMENT                                                │
│     └─ Aggregate news sentiment scores                       │
│     └─ Average confidence across sources                     │
│                        ▼                                     │
│  5. ML_SIGNAL                                                │
│     └─ Run ML model (or fallback to rules)                   │
│     └─ Predict: action (buy/sell/hold)                       │
│     └─ Predict: which token                                  │
│     └─ Predict: amount                                       │
│                        ▼                                     │
│  6. RISK_MANAGER                                             │
│     └─ Validate ML signal against rules                      │
│     └─ Cap amount to max allowed                             │
│     └─ Apply hard stops if needed                            │
│                        ▼                                     │
│  7. DECISION                                                 │
│     └─ (Optional) Call Gemini AI for final fusion            │
│     └─ Generate final TradeDecision                          │
│                        ▼                                     │
│  8. EXECUTION                                                │
│     └─ If confidence > threshold (0.7):                      │
│        └─ Call /api/tokens/buy or /api/tokens/sell           │
│     └─ Log trade to audit file                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Pipeline Nodes Explained

| Node | Purpose | Input | Output |
|------|---------|-------|--------|
| load_context | Gather all data for user | user_id | snapshot, signals |
| preprocess | Calculate features | snapshot | features dict |
| rule_check | Apply trading rules | features, rules | allowed_tokens, hard_stop |
| sentiment | Aggregate news sentiment | news_signals | sentiment score |
| ml_signal | Generate ML prediction | all above | TradeDecision candidate |
| risk_manager | Apply risk limits | ml_signal, rules | adjusted amount |
| decision | Final decision fusion | all above | final TradeDecision |
| execution | Execute or log trade | decision | API call or dry-run log |

---

## Example Trade Decision

For user 1 with test coins:

```python
TradeDecision {
    user_id: 1,
    action: "buy",                                    # buy/sell/hold
    token_mint: "factory/.../TBTC",                   # Which token
    amount: 10.5,                                     # How much N$
    confidence: 0.85,                                 # 0.0-1.0
    reason: "Bullish trend + positive news sentiment"
}
```

### Execution Modes

**Dry Run Mode** (`DRY_RUN=true`):
```
[Dry Run] Would execute buy factory/.../TBTC qty=10.5
```

**Live Mode** (`DRY_RUN=false`):
```http
POST /api/tokens/buy
{
    "denom": "factory/nuah.../TBTC",
    "payment_amount": "10500000"  # 10.5 * 1,000,000 micro-units
}
```

---

## Token Denom Mapping

The system maps between human-readable symbols and blockchain denoms:

| Symbol | Denom (Blockchain Format) |
|--------|---------------------------|
| TBTC | `factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TBTC` |
| TETH | `factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TETH` |
| TSOL | `factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TSOL` |
| TADA | `factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TADA` |
| TDOT | `factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TDOT` |

The `denom_mapper.py` in `shared/` handles these conversions.

---

## Running the System

### Prerequisites

1. **nuahchain-backend running** on localhost:8080
2. **PostgreSQL** with database `serverdb`
3. **JWT Token** for authentication
4. **Python** installed with agent dependencies

### Start Commands (All Agents with Schedulers)

Each agent has its own scheduler. Start each in a separate terminal:

```powershell
# Terminal 1: Start nuahchain-backend
cd C:\Users\Abhinav Saxena\Desktop\nuahchain-backend
./build/server.exe

# Terminal 2: fetch-data-agent (fetches every 30 min)
cd C:\Users\Abhinav Saxena\Desktop\NUAH\fetch-data-agent
$env:NUAHCHAIN_API_TOKEN="your_jwt_token"
npm run dev

# Terminal 3: news-agent (runs every 35 min)
cd C:\Users\Abhinav Saxena\Desktop\NUAH\news-agent
python scheduler.py

# Terminal 4: trend-agent (runs every 35 min)
cd C:\Users\Abhinav Saxena\Desktop\NUAH\trend-agent
python scheduler.py

# Terminal 5: rules-agent (runs every 40 min)
cd C:\Users\Abhinav Saxena\Desktop\NUAH\rules-agent
python scheduler.py

# Terminal 6: trade-agent (runs every 40 min)
cd C:\Users\Abhinav Saxena\Desktop\NUAH\trade-agent
$env:API_TOKEN="your_jwt_token"
$env:DRY_RUN="true"
python scheduler.py
```

### Agent Schedule Intervals

| Agent | Interval | Purpose |
|-------|----------|---------|
| fetch-data-agent | 30 min | Fetches user data from nuahchain-backend |
| news-agent | 35 min | Analyzes news sentiment |
| trend-agent | 35 min | Analyzes price trends |
| rules-agent | 40 min | Evaluates trading rules |
| trade-agent | 40 min | Makes and executes trade decisions |

### Run Once (Testing)

To run each agent once for testing:

```powershell
# fetch-data-agent - run once
cd C:\Users\Abhinav Saxena\Desktop\NUAH\fetch-data-agent
$env:NUAHCHAIN_API_TOKEN="your_jwt_token"
npx ts-node src/index.ts --run-now

# news-agent - run once
cd C:\Users\Abhinav Saxena\Desktop\NUAH\news-agent
python scheduler.py --run-once

# trend-agent - run once
cd C:\Users\Abhinav Saxena\Desktop\NUAH\trend-agent
python scheduler.py --run-once

# rules-agent - run once
cd C:\Users\Abhinav Saxena\Desktop\NUAH\rules-agent
python scheduler.py --run-once

# trade-agent - run once
cd C:\Users\Abhinav Saxena\Desktop\NUAH\trade-agent
$env:API_TOKEN="your_jwt_token"
$env:DRY_RUN="true"
python main.py --user-ids 1
```

### Generate Test Data

```powershell
cd C:\Users\Abhinav Saxena\Desktop\nuahchain-backend
go run ./cmd/seed_test_data
```

This creates:
- 1 test user (testbyabhinav@gmail.com)
- 1 wallet
- 5 test coins (TBTC, TETH, TSOL, TADA, TDOT)
- JWT token for authentication

---

## Testing

### Test fetch-data-agent

```powershell
cd C:\Users\Abhinav Saxena\Desktop\NUAH\fetch-data-agent
$env:NUAHCHAIN_API_TOKEN="your_jwt_token"
npx ts-node src/test-api.ts
```

### Test trade-agent

```powershell
cd C:\Users\Abhinav Saxena\Desktop\NUAH\trade-agent
$env:API_TOKEN="your_jwt_token"
$env:DRY_RUN="true"
python test_integration.py
```

---

## Quick Reference

| Question | Answer |
|----------|--------|
| **What is a snapshot?** | Point-in-time capture of user's balances, transactions, portfolio value |
| **Where is data saved?** | SQLite database at `fetch-data-agent/data/user_data.db` |
| **Why SQLite?** | Fast local storage, all agents can read without network calls |
| **How does trade-agent decide?** | LangGraph pipeline: rules → sentiment → ML → risk → execute |
| **What's the confidence threshold?** | 0.7 (70%) - trades below this are skipped |
| **How often does fetch run?** | Every 20 minutes by default |
| **What triggers a trade?** | High confidence signal + allowed by rules + under risk limits |

---

## File Locations

```
NUAH/
├── fetch-data-agent/
│   ├── data/
│   │   └── user_data.db          # SQLite database (snapshots)
│   ├── src/
│   │   ├── services/
│   │   │   ├── apiClient.ts      # API calls to nuahchain-backend
│   │   │   └── userDataService.ts
│   │   └── test-api.ts           # Test script
│   └── package.json
│
├── trade-agent/
│   ├── src/
│   │   ├── pipeline/
│   │   │   └── trade_pipeline.py # LangGraph pipeline
│   │   ├── execution/
│   │   │   └── ndollar_client.py # Trade execution
│   │   └── data_ingestion/
│   │       └── sqlite_loader.py  # Read from SQLite
│   ├── test_integration.py       # Test script
│   └── requirements.txt
│
├── shared/
│   ├── nuahchain_client.py       # Shared API client
│   └── denom_mapper.py           # Token denom mapping
│
└── nuahchain-backend/
    ├── cmd/
    │   └── seed_test_data/
    │       └── main.go           # Test data generator
    ├── api/
    │   └── router.go             # API routes
    └── tokens/
        └── repository.go         # Token storage
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No snapshot available" | Run fetch-data-agent first to populate SQLite |
| "API_TOKEN not set" | Set `$env:API_TOKEN="your_jwt"` in PowerShell |
| "Connection refused" | Ensure nuahchain-backend is running on :8080 |
| "Invalid token" | JWT expired - regenerate with `go run ./cmd/seed_test_data` |
| "No tokens in marketplace" | Tokens are in DB but not on blockchain (expected for test data) |

---

*Document generated: December 9, 2025*
*System: NUAH Multi-Agent Trading Platform*

