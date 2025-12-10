# Agent Orchestration

## Trading Mode: Fast Mode Only

The NUAH trading system is optimized for **pump.fun-style meme coin trading** with real-time 5-15 second decision cycles.

```powershell
# Start the fast trading pipeline
cd trade-agent
python main.py --user-ids 1,2,3,4,5 --dry-run
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PUMP.FUN TRADING SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 1: DATA SYNC (Every 5 minutes)                                      │
│  ─────────────────────────────────────                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    fetch-data-agent (TypeScript)                    │   │
│  │                                                                     │   │
│  │  Syncs from nuahchain-backend:                                      │   │
│  │  • User profiles & balances                                         │   │
│  │  • Token portfolios                                                 │   │
│  │  • Transaction history                                              │   │
│  │  • Market data                                                      │   │
│  │                                                                     │   │
│  │  Outputs: SQLite (user_data.db)                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  LAYER 2: BACKGROUND INTELLIGENCE (Every 5 minutes)                        │
│  ───────────────────────────────────────────────────                       │
│                              │                                              │
│  ┌───────────────┬───────────┴──────────┬───────────────┐                  │
│  │  news-agent   │     trend-agent      │  rules-agent  │                  │
│  │  (5 min)      │     (5 min)          │  (5 min)      │                  │
│  │               │                      │               │                  │
│  │ • Sentiment   │ • Bonding curve      │ • User limits │                  │
│  │ • Catalysts   │ • Rug risk           │ • Rug blocks  │                  │
│  │ • Urgency     │ • Trend direction    │ • Position $  │                  │
│  │               │ • Stage detection    │               │                  │
│  └───────┬───────┴──────────┬───────────┴───────┬───────┘                  │
│          │                  │                   │                          │
│          ▼                  ▼                   ▼                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│  │ news_signals  │  │ trend_signals │  │ rule_evals    │                   │
│  │   .csv        │  │   .csv        │  │   .csv        │                   │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                   │
│          │                  │                   │                          │
│          └──────────────────┼───────────────────┘                          │
│                             │                                              │
│                             ▼                                              │
│  LAYER 3: REAL-TIME TRADING (Every 5-15 seconds)                           │
│  ────────────────────────────────────────────────                          │
│                             │                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    trade-agent FAST PIPELINE                        │   │
│  │                                                                     │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │   │
│  │  │   Price     │    │  Pattern    │    │   Risk      │             │   │
│  │  │  Monitor    │───►│  Detector   │───►│   Guard     │             │   │
│  │  │  (5 sec)    │    │             │    │  (SL/TP)    │             │   │
│  │  └─────────────┘    └─────────────┘    └──────┬──────┘             │   │
│  │                                               │                     │   │
│  │                           ┌───────────────────┼───────────────────┐ │   │
│  │                           │                   │                   │ │   │
│  │                           ▼                   ▼                   ▼ │   │
│  │                    ┌─────────────┐     ┌─────────────┐     ┌──────┐│   │
│  │                    │ Agent       │     │   Fast      │     │Emerg.││   │
│  │                    │ Signals     │────►│  Decision   │     │ Exit ││   │
│  │                    │ (cached)    │     │  Engine     │     │      ││   │
│  │                    └─────────────┘     └──────┬──────┘     └──┬───┘│   │
│  │                                               │               │    │   │
│  │                    ┌─────────────┐            │               │    │   │
│  │    NEW TOKEN? ────►│   GEMINI    │────────────┤               │    │   │
│  │                    │ Scam Check  │  (block if SCAM/HIGH_RISK) │    │   │
│  │                    └─────────────┘            │               │    │   │
│  │                                               ▼               ▼    │   │
│  │                                        ┌─────────────────────────┐ │   │
│  │                                        │   EXECUTE TRADE         │ │   │
│  │                                        │   via nuahchain-backend │ │   │
│  │                                        └─────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Execution Order

### Step 1: fetch-data-agent (Every 5 minutes)
```powershell
cd fetch-data-agent
npm run start
# Runs on cron: */5 * * * *
```

Syncs user data from nuahchain-backend to SQLite for local processing.

### Step 2: Analysis Agents (Every 5 minutes, staggered)
```powershell
# Terminal 1 - News Agent
cd news-agent
python scheduler.py --interval-minutes 5 --initial-delay-minutes 1

# Terminal 2 - Trend Agent
cd trend-agent
python scheduler.py --interval-minutes 5 --initial-delay-minutes 1

# Terminal 3 - Rules Agent
cd rules-agent
python scheduler.py --interval-minutes 5 --initial-delay-minutes 2
```

Analysis agents provide:
- **news-agent**: Pump/dump catalysts, sentiment scores, urgency levels
- **trend-agent**: Bonding curve stage, rug risk scores, trend direction
- **rules-agent**: Per-user trading permissions, position limits, rug protection

### Step 3: trade-agent (Continuous, 5-second cycles)
```powershell
cd trade-agent
python main.py --user-ids 1,2,3,4,5
```

The fast pipeline:
1. Polls prices every 5 seconds
2. Detects patterns (pump, dump, rug, FOMO)
3. Loads agent signals (cached, refreshed every 60s)
4. Makes decisions considering: pattern + news + trend + rules
5. Executes trades or emergency exits

---

## Fast Mode Features

| Feature | Timing | Description |
|---------|--------|-------------|
| Price Polling | 5 sec | Real-time price tracking |
| Pattern Detection | 5 sec | Pump/dump/rug/FOMO patterns |
| Agent Signal Refresh | 60 sec | News/trend/rules cache |
| Decision Cycle | 15 sec | Buy/sell evaluation |
| Stop-Loss | Instant | Auto-trigger at -10% |
| Take-Profit | Instant | Auto-trigger at +25% |
| Trailing Stop | Instant | Trail by 8% |
| Emergency Exit | <1 sec | Rug pull detection at -50% |

---

## Pattern Types Detected

| Pattern | Change | Timeframe | Action |
|---------|--------|-----------|--------|
| MICRO_PUMP | +5-15% | 1 min | Buy opportunity |
| MID_PUMP | +15-50% | 5 min | Momentum entry |
| MEGA_PUMP | +50-200% | 15 min | FOMO (careful) |
| DUMP | -10-30% | 1 min | Exit signal |
| RUG_PULL | -50%+ | 1 min | Emergency exit |
| FOMO_SPIKE | +30%+ | 2 min | High risk/reward |
| ACCUMULATION | Volume spike | 5 min | Early entry |

---

## Agent Signal Integration

The fast pipeline integrates signals from analysis agents:

```python
# Example decision flow
if pattern == MICRO_PUMP:
    # Check news sentiment
    news = get_news_signal(token)  # From news-agent
    if news.sentiment > 0.3:
        confidence += 0.1  # Boost on positive news
    
    # Check bonding curve stage
    trend = get_trend_signal(token)  # From trend-agent
    if trend.stage == "early":
        confidence += 0.05  # Early = good entry
    
    # Check rug risk
    if trend.rug_risk > 0.5:
        confidence -= 0.3  # Reduce for risky tokens
    
    # Check user permissions
    rules = get_rule_evaluation(user_id, token)  # From rules-agent
    if not rules.allowed:
        return None  # Blocked by rules
    
    max_position = rules.max_position_ndollar
    
    # Final decision
    if confidence >= 0.55:
        return BUY(amount=max_position * confidence)
```

---

## Required Environment Variables

### Core Variables

| Agent | Variables |
|-------|-----------|
| `fetch-data-agent` | `NUAHCHAIN_API_URL`, `NUAHCHAIN_API_TOKEN`, `FETCH_INTERVAL_MINUTES=5` |
| `news-agent` | `OPENROUTER_API_KEY`, `NEWS_AGENT_DATA_DIR`, `NEWS_INTERVAL_MINUTES=5` |
| `trend-agent` | `OPENROUTER_API_KEY`, `TREND_AGENT_DATA_DIR`, `TREND_INTERVAL_MINUTES=5` |
| `rules-agent` | `OPENROUTER_API_KEY`, `RULES_AGENT_DATA_DIR`, `RULES_INTERVAL_MINUTES=5` |
| `trade-agent` | `SQLITE_PATH`, `API_BASE_URL`, `API_TOKEN`, `DRY_RUN` |

### trade-agent Fast Mode Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRICE_POLL_INTERVAL_SECONDS` | `5` | Price polling frequency |
| `DECISION_INTERVAL_SECONDS` | `15` | Decision cycle frequency |
| `STOP_LOSS_PERCENT` | `0.10` | Auto stop-loss at 10% |
| `TRAILING_STOP_PERCENT` | `0.08` | Trail by 8% |
| `TAKE_PROFIT_PERCENT` | `0.25` | Auto take-profit at 25% |
| `EMERGENCY_EXIT_THRESHOLD` | `-0.30` | Emergency exit trigger |
| `RUG_THRESHOLD_1M` | `-0.50` | Rug pull detection |
| `PUMP_THRESHOLD_1M` | `0.05` | Pump detection |
| `DUMP_THRESHOLD_1M` | `-0.10` | Dump detection |
| `VOLUME_SPIKE_THRESHOLD` | `3.0` | Volume spike multiplier |

### Gemini Scam Detection (Optional but Recommended)

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | - | Google Gemini API key for scam detection |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model (flash for speed) |
| `ENABLE_TOKEN_ANALYZER` | `true` | Enable/disable scam detection |
| `TOKEN_ANALYZER_CACHE_TTL` | `300` | Cache duration in seconds |

**What it does**: When the agent sees a NEW token (not in trend_signals.csv), it calls Gemini to analyze:
- Token name (copies of famous coins?)
- Creator concentration (>30% = risky)
- Holder count (<50 = risky)
- Liquidity depth (<$5k = easy to manipulate)
- Social presence (none = risky)
- Price patterns (100%+ in 10 min = manipulation)

**Result**: Returns risk level (SAFE, CAUTION, HIGH_RISK, SCAM) with:
- Custom stop-loss suggestion
- Max position % recommendation
- Red/green flags list

---

## API Keys Checklist

| Purpose | Key | Required |
|---------|-----|----------|
| Analysis agents (news/trend/rules) | `OPENROUTER_API_KEY` | ✅ Yes |
| Trade execution | `API_TOKEN` (JWT) | ✅ Yes |
| On-chain data | `HELIUS_API_KEY` | Optional |
| Social signals | `TWITTER_API_KEY` | Future |

---

## Quick Start

```powershell
# 1. Start nuahchain-backend
cd nuahchain-backend
go run .

# 2. Start data sync
cd fetch-data-agent
npm run start

# 3. Start analysis agents (parallel terminals)
cd news-agent && python scheduler.py --interval-minutes 5
cd trend-agent && python scheduler.py --interval-minutes 5
cd rules-agent && python scheduler.py --interval-minutes 5

# 4. Start trading (dry run first)
cd trade-agent
python main.py --user-ids 1,2,3,4,5 --dry-run

# 5. Enable live trading
python main.py --user-ids 1,2,3,4,5
```
