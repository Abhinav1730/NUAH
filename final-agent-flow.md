# NUAH Agent System Flow

## Overview

The NUAH trading system is optimized for **pump.fun-style meme coin trading** with:
- Real-time price monitoring (5-second cycles)
- Background intelligence from analysis agents (5-minute refresh)
- Automated risk management (stop-loss, take-profit)
- Emergency exit capability (<1 second)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                        nuahchain-backend (Go)                               │
│                      ┌─────────────────────────┐                            │
│                      │ REST API + PostgreSQL   │                            │
│                      │ Blockchain + Bonding    │                            │
│                      └───────────┬─────────────┘                            │
│                                  │                                          │
│           ┌──────────────────────┼──────────────────────┐                  │
│           │                      │                      │                  │
│           ▼                      ▼                      ▼                  │
│   ┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│   │ fetch-data    │    │   trade-agent   │    │   trade-agent   │         │
│   │ agent (5 min) │    │  User 1 (fast)  │    │  User 2 (fast)  │   ...   │
│   └───────┬───────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                     │                      │                   │
│           ▼                     └──────────┬───────────┘                   │
│   ┌───────────────┐                        │                               │
│   │    SQLite     │◄───────────────────────┤ (reads user data)             │
│   │  user_data.db │                        │                               │
│   └───────┬───────┘                        │                               │
│           │                                │                               │
│           ▼                                ▼                               │
│   ┌───────────────────────────────────────────────────────────────────┐   │
│   │               ANALYSIS AGENTS (Background, 5 min)                 │   │
│   │                                                                   │   │
│   │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐              │   │
│   │  │ news-agent  │  │ trend-agent  │  │ rules-agent │              │   │
│   │  │             │  │              │  │             │              │   │
│   │  │ • Sentiment │  │ • BC stage   │  │ • User lim. │              │   │
│   │  │ • Catalysts │  │ • Rug risk   │  │ • Rug block │              │   │
│   │  │ • Urgency   │  │ • Trend dir. │  │ • Position$ │              │   │
│   │  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘              │   │
│   │         │                │                 │                      │   │
│   │         ▼                ▼                 ▼                      │   │
│   │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐              │   │
│   │  │news_signals │  │trend_signals │  │rule_evals   │              │   │
│   │  │   .csv      │  │   .csv       │  │   .csv      │              │   │
│   │  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘              │   │
│   │         │                │                 │                      │   │
│   │         └────────────────┼─────────────────┘                      │   │
│   │                          │                                        │   │
│   └──────────────────────────┼────────────────────────────────────────┘   │
│                              │                                             │
│                              ▼ (cached, 60s TTL)                           │
│   ┌───────────────────────────────────────────────────────────────────┐   │
│   │                    FAST TRADING PIPELINE                          │   │
│   │                                                                   │   │
│   │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐          │   │
│   │  │    Price     │   │   Pattern    │   │    Risk      │          │   │
│   │  │   Monitor    │──►│  Detector    │──►│   Guard      │          │   │
│   │  │   (5 sec)    │   │              │   │  (SL/TP)     │          │   │
│   │  └──────────────┘   └──────────────┘   └──────┬───────┘          │   │
│   │                                               │                   │   │
│   │                          ┌────────────────────┴───────────────┐   │   │
│   │                          │                                    │   │   │
│   │                          ▼                                    ▼   │   │
│   │                   ┌─────────────┐                     ┌──────────┐│   │
│   │  Agent Signals    │    Fast     │                     │ Emergency││   │
│   │  (news/trend/     │  Decision   │                     │   Exit   ││   │
│   │   rules)    ─────►│   Engine    │                     │ Handler  ││   │
│   │                   └──────┬──────┘                     └────┬─────┘│   │
│   │                          │                                 │      │   │
│   │                          ▼                                 ▼      │   │
│   │                   ┌─────────────────────────────────────────────┐ │   │
│   │                   │           EXECUTE TRADE                     │ │   │
│   │                   │         via nuahchain-backend               │ │   │
│   │                   └─────────────────────────────────────────────┘ │   │
│   │                                                                   │   │
│   └───────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Why This Architecture?

On pump.fun-style platforms:

| Challenge | Solution |
|-----------|----------|
| Prices change **100%+ in minutes** | Real-time 5-second monitoring |
| Rug pulls happen in **seconds** | Emergency exit (<1 second) |
| Volume spikes signal **immediate opportunities** | Pattern detection |
| News drives **pump catalysts** | Background news analysis |
| Bonding curve stage matters | Trend agent BC tracking |
| Users have **different risk tolerances** | Rules agent per-user limits |

---

## Component Details

### 1. fetch-data-agent (Every 5 minutes)

**Purpose**: Sync user data from nuahchain-backend to local SQLite.

```typescript
// scheduler.ts
// Runs every 5 minutes (changed from 30 for pump.fun)
const intervalMinutes = parseInt(process.env.FETCH_INTERVAL_MINUTES || '5', 10);
```

**Outputs**:
- `user_data.db` SQLite database with:
  - `users` table (profiles)
  - `user_balances` table (token holdings)
  - `user_transactions` table (trade history)
  - `user_portfolios` table (portfolio snapshots)
  - `market_data` table (price history)

---

### 2. news-agent (Every 5 minutes)

**Purpose**: Analyze token sentiment and detect catalysts.

**Prompt** (DeepSeek via OpenRouter):
```
You are a meme coin analyst for pump.fun-style trading.

PUMP.FUN TRADING RULES:
1. MOMENTUM IS KING: High positive momentum = potential pump
2. VOLATILITY IS OPPORTUNITY: High volatility is GOOD for meme coins
3. RISK IS RELATIVE: Risk up to 0.85 acceptable if momentum is strong
4. FOMO DETECTION: Sudden spikes often precede 2-10x moves

CATALYST TYPES:
- pump_detected: Strong buying pressure
- fomo_wave: Social momentum building
- whale_entry: Large buyer detected
- community_hype: Engagement spike

URGENCY LEVELS:
- critical: Act within seconds
- high: Act within 1-2 minutes
- medium: Act within 5-10 minutes
```

**Output**: `news_signals.csv`
```csv
signal_id,timestamp,token_mint,sentiment_score,confidence,catalyst,urgency,summary
NEWS-0001,2025-12-09T10:00:00Z,factory/xxx,0.85,0.78,pump_detected,high,Strong buying...
```

---

### 3. trend-agent (Every 5 minutes)

**Purpose**: Analyze bonding curve stages and rug risk.

**Prompt** (DeepSeek via OpenRouter):
```
You are a meme coin trend analyst for pump.fun-style bonding curve tokens.

BONDING CURVE STAGES:
- "early": < 30% of curve filled, high upside but risky
- "mid": 30-70% filled, moderate risk/reward
- "late": 70-95% filled, approaching graduation
- "graduated": Migrated to DEX, different dynamics

ANALYSIS FACTORS:
1. Momentum: Positive = bullish, Negative = bearish
2. Volatility: High (>0.15) = risky, Moderate = normal
3. Volume: High confirms trend, Low = fake move
4. Whale concentration: >30% = rug risk
```

**Output**: `trend_signals.csv`
```csv
signal_id,timestamp,token_mint,trend_score,stage,rug_risk,volatility_flag,liquidity_flag
TREND-0001,2025-12-09T10:00:00Z,factory/xxx,0.72,early,0.25,high,healthy
```

---

### 4. rules-agent (Every 5 minutes)

**Purpose**: Enforce per-user trading rules and rug protection.

**Prompt** (DeepSeek via OpenRouter):
```
You are a pump.fun risk manager.

RUG PULL INDICATORS (BLOCK if multiple):
- Whale concentration > 40%
- Low liquidity + high volatility
- New token with huge gains
- Risk score > 0.9

POSITION SIZING:
- Aggressive user: Up to 20% per token
- Balanced user: Up to 10% per token
- Conservative user: Up to 5% per token
- For rug_risk > 0.5: Halve position

EMERGENCY OVERRIDES:
- If rug_risk > 0.7: Force allowed=false
- If user owns AND momentum < -0.2: Allow sell
```

**Output**: `rule_evaluations.csv`
```csv
evaluation_id,timestamp,user_id,token_mint,allowed,max_daily_trades,max_position_ndollar
RULE-1-xxx,2025-12-09T10:00:00Z,1,factory/xxx,true,20,2000
```

---

### 5. trade-agent Fast Pipeline (Every 5-15 seconds)

**Purpose**: Real-time trading with integrated agent signals.

#### 5.1 Price Monitor
```python
# Polls prices every 5 seconds
# Maintains 5-minute rolling history
# Calculates real-time momentum/volatility
poll_interval_seconds = 5
```

#### 5.2 Pattern Detector

| Pattern | 1-Min Change | Action |
|---------|--------------|--------|
| `MICRO_PUMP` | +5% to +15% | BUY opportunity |
| `MID_PUMP` | +15% to +30% | Momentum entry |
| `MEGA_PUMP` | +30%+ | FOMO (careful) |
| `DUMP` | -15% to -30% | EXIT |
| `RUG_PULL` | -50%+ | EMERGENCY EXIT |
| `ACCUMULATION` | Volume spike | Early entry |

#### 5.3 Risk Guard (Automated)

| Setting | Default | Description |
|---------|---------|-------------|
| Stop Loss | -10% | Auto-exit |
| Trailing Stop | 8% | Lock profits |
| Take Profit | +25% | Auto-exit |
| Emergency | -30% | Bypass pipeline |

#### 5.4 Fast Decision Engine

**Key Feature**: Integrates agent signals for smarter decisions.

```python
def _make_fast_decision(self, signal, max_amount):
    # Get agent signals (cached, refreshed every 60s)
    news = self.get_news_signal(token)      # From news-agent
    trend = self.get_trend_signal(token)    # From trend-agent
    rules = self.get_rule_evaluation(user, token)  # From rules-agent
    
    confidence = signal.confidence
    
    # Boost on positive news
    if news.sentiment > 0.3:
        confidence += 0.1
    
    # Good entry if early stage
    if trend.stage == "early":
        confidence += 0.05
    
    # Reduce for rug risk
    if trend.rug_risk > 0.5:
        confidence -= trend.rug_risk * 0.3
    
    # Respect user rules
    if not rules.allowed:
        return None  # Blocked
    
    max_position = rules.max_position_ndollar
    
    # Final decision
    if confidence >= 0.55:
        return BUY(amount=max_position * confidence)
```

#### 5.5 Emergency Exit Handler
```python
# Bypasses normal pipeline for speed
# Accepts higher slippage (10%)
# Target execution: <1 second
```

---

## Signal Flow

```
                    EVERY 5 MINUTES
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌─────────┐        ┌───────────┐        ┌───────────┐
│  news   │        │   trend   │        │   rules   │
│  agent  │        │   agent   │        │   agent   │
└────┬────┘        └─────┬─────┘        └─────┬─────┘
     │                   │                    │
     ▼                   ▼                    ▼
┌─────────┐        ┌───────────┐        ┌───────────┐
│ news_   │        │ trend_    │        │ rule_     │
│ signals │        │ signals   │        │ evals     │
│  .csv   │        │  .csv     │        │  .csv     │
└────┬────┘        └─────┬─────┘        └─────┬─────┘
     │                   │                    │
     └───────────────────┼────────────────────┘
                         │
                         ▼ (60-second cache)
              ┌──────────────────────┐
              │   FAST PIPELINE      │
              │   Signal Loader      │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Decision Engine    │
              │                      │
              │ Pattern + News +     │
              │ Trend + Rules =      │
              │    DECISION          │
              └──────────────────────┘
```

---

## Timing Summary

| Component | Frequency | Purpose |
|-----------|-----------|---------|
| fetch-data-agent | 5 min | Sync user data |
| news-agent | 5 min | Token sentiment |
| trend-agent | 5 min | Bonding curve stage |
| rules-agent | 5 min | User permissions |
| Price Monitor | 5 sec | Real-time prices |
| Pattern Detector | 5 sec | Pump/dump detection |
| Decision Cycle | 15 sec | Buy/sell decisions |
| Signal Cache | 60 sec | Agent signal refresh |
| Stop-Loss | Instant | Auto-exit |
| Emergency Exit | <1 sec | Rug protection |

---

## Running the System

### Start All Components

```powershell
# Terminal 1: nuahchain-backend
cd nuahchain-backend
go run .

# Terminal 2: fetch-data-agent
cd fetch-data-agent
npm run start

# Terminal 3: news-agent
cd news-agent
python scheduler.py --interval-minutes 5

# Terminal 4: trend-agent
cd trend-agent
python scheduler.py --interval-minutes 5

# Terminal 5: rules-agent
cd rules-agent
python scheduler.py --interval-minutes 5

# Terminal 6: trade-agent (dry run first!)
cd trade-agent
python main.py --user-ids 1,2,3,4,5 --dry-run

# When ready for live trading:
python main.py --user-ids 1,2,3,4,5
```

---

## Environment Variables

### trade-agent (Fast Pipeline)

```bash
# Required
API_BASE_URL=http://localhost:8080
API_TOKEN=your_jwt_token
SQLITE_PATH=../fetch-data-agent/data/user_data.db
DATA_DIR=../data

# Timing
PRICE_POLL_INTERVAL_SECONDS=5
DECISION_INTERVAL_SECONDS=15

# Risk Management
STOP_LOSS_PERCENT=0.10
TRAILING_STOP_PERCENT=0.08
TAKE_PROFIT_PERCENT=0.25
EMERGENCY_EXIT_THRESHOLD=-0.30

# Pattern Detection
PUMP_THRESHOLD_1M=0.05
DUMP_THRESHOLD_1M=-0.10
RUG_THRESHOLD_1M=-0.50
VOLUME_SPIKE_THRESHOLD=3.0

# Mode
DRY_RUN=true
```

### Analysis Agents

```bash
# All agents
OPENROUTER_API_KEY=your_key

# Per-agent data dirs
NEWS_AGENT_DATA_DIR=../data
TREND_AGENT_DATA_DIR=../data
RULES_AGENT_DATA_DIR=../data

# Intervals (all 5 min for pump.fun)
NEWS_INTERVAL_MINUTES=5
TREND_INTERVAL_MINUTES=5
RULES_INTERVAL_MINUTES=5
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Price poll latency | <100ms |
| Pattern detection | <10ms |
| Decision cycle | <15s |
| Stop-loss trigger | <50ms |
| Emergency exit | <1 second |
| Agent signal load | <50ms |

---

## Testing with Simulation Framework

```powershell
cd testing

# Generate test data
python run_simulation.py --generate-only --coins 100 --users 1000

# Run backtest
python run_simulation.py --backtest

# Full simulation (24 hours)
python run_simulation.py --coins 100 --users 1000 --hours 24
```

---

*Document updated: December 9, 2025*
*System: NUAH Pump.fun Trading Platform*
*Features: Real-time trading, agent integration, automated risk management*
