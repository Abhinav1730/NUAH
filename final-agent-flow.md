# NUAH Agent System Flow

## Overview Architecture

The NUAH trading system now supports **two trading modes**:

1. **Standard Mode**: Traditional interval-based trading (30-60 min cycles)
2. **Fast Mode**: Real-time pump.fun-style trading (5-15 second cycles)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           nuahchain-backend (Go)                            │
│  • REST API server on localhost:8080                                        │
│  • PostgreSQL database (users, wallets, tokens)                             │
│  • Blockchain connection for trading                                        │
│  • Bonding curve mechanics                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ HTTP API calls
                                    │ (JWT authenticated)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TRADING MODES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────┐          ┌─────────────────────────────────────┐  │
│   │   STANDARD MODE     │          │         FAST MODE (pump.fun)        │  │
│   │   (30-60 min)       │          │         (5-15 seconds)              │  │
│   ├─────────────────────┤          ├─────────────────────────────────────┤  │
│   │ fetch-data-agent    │          │ Real-Time Price Monitor             │  │
│   │      ↓              │          │      ↓                              │  │
│   │ SQLite snapshots    │          │ Pattern Detector                    │  │
│   │      ↓              │          │      ↓                              │  │
│   │ Analysis agents     │          │ Risk Guard (Stop-Loss/TP)           │  │
│   │      ↓              │          │      ↓                              │  │
│   │ LangGraph pipeline  │          │ Fast Decision Engine                │  │
│   │      ↓              │          │      ↓                              │  │
│   │ Gemini fusion       │          │ Emergency Exit Handler              │  │
│   │      ↓              │          │      ↓                              │  │
│   │ Trade execution     │          │ Instant Trade Execution             │  │
│   └─────────────────────┘          └─────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Fast Mode Architecture (pump.fun Style)

### Why Fast Mode?

On pump.fun-style platforms:
- Prices can change **100%+ in minutes**
- Rug pulls happen in **seconds**
- Volume spikes signal **immediate opportunities**
- Traditional 30-minute cycles **miss everything**

### Fast Mode Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FAST MODE PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. PRICE MONITOR (every 5 seconds)                                         │
│     ├─ Polls prices from nuahchain-backend                                  │
│     ├─ Maintains rolling 5-minute history per token                        │
│     ├─ Calculates real-time: momentum, volatility, volume spikes           │
│     └─ Triggers alerts on significant moves (>5% in 1 min)                 │
│                                                                             │
│  2. PATTERN DETECTOR                                                        │
│     ├─ Identifies patterns in real-time:                                   │
│     │   • MICRO_PUMP:  +5-15% in 1 min    → Potential entry               │
│     │   • MID_PUMP:    +15-30% in 1 min   → Momentum play                 │
│     │   • MEGA_PUMP:   +30%+ in 1 min     → High risk, watch for reversal │
│     │   • FOMO_SPIKE:  +50%+ in 1 min     → DO NOT CHASE!                 │
│     │   • DUMP:        -15% in 1 min      → Exit signal                   │
│     │   • RUG_PULL:    -50%+ in 1 min     → EMERGENCY EXIT!               │
│     │   • DEAD_CAT:    Recovery after dump → Don't buy the dip            │
│     └─ Outputs: pattern, confidence, action, risk_level                    │
│                                                                             │
│  3. RISK GUARD (Automated)                                                  │
│     ├─ Stop Loss:      Auto-exit at -10% (configurable)                    │
│     ├─ Trailing Stop:  Lock profits, trail by 8%                           │
│     ├─ Take Profit:    Auto-exit at +25% (configurable)                    │
│     ├─ Partial Takes:  25% at +15%, +30%, +50%                             │
│     └─ Emergency:      Instant exit at -30% or rug detection               │
│                                                                             │
│  4. FAST DECISION ENGINE                                                    │
│     ├─ Pattern-based rules (no LLM for speed)                              │
│     ├─ Position sizing based on confidence                                 │
│     ├─ Rate limiting per user                                              │
│     └─ Decision time: <100ms                                                │
│                                                                             │
│  5. EMERGENCY EXIT HANDLER                                                  │
│     ├─ Bypasses normal pipeline                                            │
│     ├─ Accepts higher slippage (10%)                                       │
│     ├─ Single retry, short timeout                                         │
│     └─ Target execution: <1 second                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pattern Detection Thresholds

| Pattern | 1-Min Change | 5-Min Change | Volume | Action | Risk |
|---------|-------------|--------------|--------|--------|------|
| **Micro Pump** | +5% to +15% | Any | 1.5x+ | BUY | Low |
| **Mid Pump** | +15% to +30% | +25%+ | 2x+ | BUY/HOLD | Medium |
| **Mega Pump** | +30% to +50% | +50%+ | 3x+ | HOLD/SELL | High |
| **FOMO Spike** | +50%+ | Any | 5x+ | DO NOT BUY | Extreme |
| **Accumulation** | +1% to +5% | +10%+ | Normal | BUY | Low |
| **Distribution** | -1% to -5% | -10%+ | Normal | SELL | Medium |
| **Dump** | -15% to -30% | Any | 2x+ | SELL | High |
| **Rug Pull** | -50%+ | Any | Any | EMERGENCY EXIT | Critical |
| **Dead Cat Bounce** | +10% after dump | Any | Low | DO NOT BUY | High |

### Risk Management Defaults

| Setting | Default | Description |
|---------|---------|-------------|
| Stop Loss | 10% | Exit if price drops 10% from entry |
| Trailing Stop | 8% | Trail by 8% from highest price |
| Trailing Activation | 5% | Activate trailing after 5% profit |
| Take Profit | 25% | Exit at 25% profit |
| Partial Take 1 | 15% | Take 25% of position at 15% profit |
| Partial Take 2 | 30% | Take 25% of position at 30% profit |
| Partial Take 3 | 50% | Take 25% of position at 50% profit |
| Emergency Exit | -30% | Immediate exit, bypass pipeline |
| Rug Detection | -50% | Instant exit, max slippage 10% |

---

## Standard Mode (Legacy)

For stable coins or longer-term positions:

```
┌──────────────────────────────────────────────────────────────┐
│                 STANDARD MODE PIPELINE                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. fetch-data-agent (every 30 min)                          │
│     └─ Fetches from nuahchain-backend → SQLite               │
│                                                              │
│  2. Analysis Agents (every 35-40 min)                        │
│     ├─ news-agent:  Sentiment analysis                       │
│     ├─ trend-agent: Price trend analysis                     │
│     └─ rules-agent: Trading rules evaluation                 │
│                                                              │
│  3. trade-agent LangGraph Pipeline                           │
│     ├─ load_context: Read all signals                        │
│     ├─ preprocess:   Calculate features                      │
│     ├─ rule_check:   Apply trading rules                     │
│     ├─ sentiment:    Aggregate news sentiment                │
│     ├─ ml_signal:    ML/rule prediction                      │
│     ├─ risk_manager: Apply position limits                   │
│     ├─ decision:     Gemini LLM fusion                       │
│     └─ execution:    Execute or dry-run                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Running the Agent

### Fast Mode (Recommended for pump.fun)

```powershell
cd C:\Users\Abhinav Saxena\Desktop\NUAH\trade-agent

# Fast mode with 5 agent users
python main.py --mode fast --user-ids 1,2,3,4,5

# Fast mode with dry run (testing)
python main.py --mode fast --user-ids 1,2,3,4,5 --dry-run

# Fast mode for 1 hour
python main.py --mode fast --user-ids 1,2,3,4,5 --duration 3600
```

### Standard Mode

```powershell
# Standard mode (single run)
python main.py --mode standard --user-ids 1,2,3,4,5

# Standard mode with scheduler
python scheduler.py --interval-minutes 30
```

### Environment Variables

```bash
# Required
API_BASE_URL=http://localhost:8080
API_TOKEN=your_jwt_token

# Fast Mode Tuning
PRICE_POLL_INTERVAL_SECONDS=5
DECISION_INTERVAL_SECONDS=15
STOP_LOSS_PERCENT=0.10
TRAILING_STOP_PERCENT=0.08
TAKE_PROFIT_PERCENT=0.25

# Mode Selection
TRADING_MODE=fast  # or 'standard'
FAST_MODE_ENABLED=true
DRY_RUN=true
```

---

## Data Flow Comparison

### Standard Mode

```
nuahchain-backend → fetch-data-agent (30m) → SQLite → trade-agent (40m) → Execute
                                                  ↑
                              news/trend/rules agents write signals
```

### Fast Mode

```
nuahchain-backend ←→ Price Monitor (5s) → Pattern Detector → Risk Guard → Execute
                                                                    ↓
                                                          Emergency Exit (if needed)
```

---

## Key Differences

| Aspect | Standard Mode | Fast Mode |
|--------|--------------|-----------|
| **Cycle Time** | 30-60 minutes | 5-15 seconds |
| **Data Source** | SQLite snapshots | Live API polling |
| **Decision Logic** | ML + LLM fusion | Pattern rules |
| **Risk Management** | Manual rules | Automated stop-loss |
| **Exit Speed** | Full pipeline | Instant (bypass) |
| **Best For** | Stable coins | Meme coins, pump.fun |

---

## File Structure

```
trade-agent/
├── main.py                      # Entry point (supports both modes)
├── scheduler.py                 # Standard mode scheduler
├── src/
│   ├── config.py               # Configuration (both modes)
│   ├── pipeline/
│   │   ├── trade_pipeline.py   # Standard LangGraph pipeline
│   │   └── fast_pipeline.py    # Fast mode pipeline
│   ├── realtime/               # Fast mode components
│   │   ├── price_monitor.py    # Real-time price tracking
│   │   ├── pattern_detector.py # Pump/dump detection
│   │   ├── risk_guard.py       # Automated stop-loss
│   │   └── emergency_exit.py   # Fast-path exits
│   ├── models/
│   │   ├── ml_predictor.py     # ML predictions
│   │   ├── rule_evaluator.py   # Rule-based decisions
│   │   └── feature_engineer.py # Feature extraction
│   └── execution/
│       └── ndollar_client.py   # Trade execution
```

---

## Testing

### Test with Simulation Framework

```powershell
cd C:\Users\Abhinav Saxena\Desktop\NUAH\testing

# Generate test data (100 coins, 1000 users)
python run_simulation.py --generate-only

# Run backtest with fast mode patterns
python run_simulation.py --backtest

# Full simulation
python run_simulation.py --coins 100 --users 1000 --hours 24
```

### Test Fast Mode with Dry Run

```powershell
cd C:\Users\Abhinav Saxena\Desktop\NUAH\trade-agent

# 5-minute test run
python main.py --mode fast --user-ids 1,2,3,4,5 --dry-run --duration 300
```

---

## Performance Targets

| Metric | Target | Measured |
|--------|--------|----------|
| Price poll latency | <100ms | - |
| Pattern detection | <10ms | - |
| Stop-loss trigger | <50ms | - |
| Emergency exit | <1 second | - |
| Full decision cycle | <15 seconds | - |

---

## Monitoring

The fast pipeline logs:
- Every pattern detected
- All stop-loss/take-profit triggers
- Emergency exit executions
- Decision statistics

Check logs at:
```
trade-agent/logs/
```

---

*Document updated: December 9, 2025*
*System: NUAH Multi-Agent Trading Platform v2.0*
*Features: Fast mode (pump.fun), automated risk management, pattern detection*
