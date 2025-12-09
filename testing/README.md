# NUAH Trading Agent Testing Framework

A comprehensive testing suite for evaluating the NUAH trading agent's performance with simulated market data.

## 🎯 Overview

This testing framework simulates a pump.fun-style trading environment to test the agent's ability to:
- Detect price movement patterns (pumps, dumps, organic growth)
- Make profitable trading decisions
- Manage risk appropriately
- Execute trades at the right times

## 📁 Directory Structure

```
testing/
├── config.py                 # Central configuration
├── requirements.txt          # Python dependencies
├── run_simulation.py         # Main orchestrator script
├── fast_mode_test.py         # Fast pipeline testing (NEW)
├── live_simulation.py        # Continuous live simulation (NEW)
├── README.md                 # This file
│
├── database/                 # Database utilities
│   ├── connection.py         # PostgreSQL connection manager
│   └── seed_postgres.py      # Database seeding functions
│
├── generators/               # Test data generators
│   ├── coin_generator.py     # Creates 100 dummy meme coins
│   ├── user_generator.py     # Creates 1000 test users
│   ├── price_simulator.py    # Simulates price movements
│   └── signal_generator.py   # Generates agent signals (NEW)
│
├── agent_test/               # Agent testing utilities
│   ├── test_harness.py       # Test harness for agent
│   ├── backtester.py         # Historical backtesting
│   └── metrics.py            # Performance metrics
│
├── data/                     # Generated test data (auto-created)
│   ├── generated_coins.json
│   ├── generated_users.json
│   ├── price_histories.json
│   ├── time_series.csv
│   ├── news_signals.csv      # From signal_generator
│   ├── trend_signals.csv     # From signal_generator
│   └── rule_evaluations.csv  # From signal_generator
│
├── reports/                  # Test reports (auto-created)
│   └── simulation_results_*.json
│
└── logs/                     # Simulation logs (auto-created)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd testing
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the `testing/` directory:

```env
# PostgreSQL (nuahchain-backend database)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=serverdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# API (optional, for real agent testing)
API_BASE_URL=http://localhost:8080
```

### 3. Run Full Simulation

```bash
# Run complete simulation (generates data + runs tests)
python run_simulation.py

# Generate data only (100 coins, 1000 users, 24h prices)
python run_simulation.py --generate-only

# Run tests on existing data
python run_simulation.py --test-only

# Run backtest simulation
python run_simulation.py --backtest

# Custom configuration
python run_simulation.py --coins 50 --users 500 --hours 48
```

## 🪙 Test Data Generation

### Coins (100 by default)

Each coin is generated with:
- **Name & Symbol**: Meme coin style (DOGE, PEPE, SHIB variants)
- **Initial Price**: $0.0001 - $0.01
- **Total Supply**: 1M - 1T tokens
- **Volatility Profile**: stable, moderate, volatile, extreme
- **Bonding Curve**: linear, exponential, or sigmoid

### Users (1000 by default)

Each user includes:
- **Email & Username**: Unique identifiers
- **Wallet Address**: Auto-generated Cosmos address
- **Risk Profile**: conservative (30%), moderate (50%), aggressive (20%)
- **Initial Balance**: $100 - $10,000 in NUAH
- **Trading Preferences**: max position, daily trade limits

### Agent Users

Users 1-5 are designated as "agent-managed" users. The trading agent makes decisions for these users while the others serve as market participants.

## 📈 Price Simulation

The price simulator generates realistic pump.fun-style price movements with **fast timeframes**:

| Pattern | Price Change | Duration | Probability |
|---------|-------------|----------|-------------|
| **FOMO Spike** | +50% to +200% | 5-10 min | 10% |
| Micro Pump | +10% to +30% | 5-15 min | 20% |
| Mid Pump | +30% to +100% | 15-45 min | 15% |
| Mega Pump | +100% to +500% | 30 min - 2h | 5% |
| Organic Growth | +5% to +20% | 2-6 hours | 12% |
| Sideways | -8% to +8% | 1-4 hours | 13% |
| Dump | -20% to -50% | 5-20 min | 15% |
| **Rug Pull** | -80% to -95% | **1-5 min** | 5% |
| **Dead Cat Bounce** | +40% then -30% | 10-30 min | 5% |

> ⚡ **Note**: Price updates every 1 minute to capture fast pump.fun-style movements!

## 🧪 Testing Modes

### 1. Full Simulation (Batch Mode)
Tests the complete pipeline with batch data:
```bash
python run_simulation.py --test-only
python run_simulation.py --test-only --real-agent  # Use actual agent
```

### 2. Fast Pipeline Test (NEW)
Tests the real-time fast trading pipeline specifically:
```bash
# Simulated test (quick)
python fast_mode_test.py

# 5-minute test
python fast_mode_test.py --duration 300

# Live pipeline test (requires trade-agent running)
python fast_mode_test.py --live --duration 60
```

### 3. Live Simulation (NEW)
Runs a continuous simulation with real-time price updates:
```bash
# 1-hour simulation with 60s price updates
python live_simulation.py --hours 1

# Real-time mode (5s price updates like pump.fun)
python live_simulation.py --hours 1 --realtime

# 24-hour simulation
python live_simulation.py --hours 24 --price-interval 60
```

### 4. Backtester
Replays historical prices to evaluate strategy:
```bash
python run_simulation.py --backtest
```

### 5. Signal Generator (NEW)
Generate agent signals without running actual agents:
```bash
# Generate all signals (news, trend, rules)
python generators/signal_generator.py
```

### 6. Performance Metrics
Calculated metrics include:
- **Win Rate**: Percentage of profitable trades
- **Total P&L**: Net profit/loss
- **Sharpe Ratio**: Risk-adjusted returns
- **Maximum Drawdown**: Largest portfolio decline
- **Profit Factor**: Gross profit / Gross loss

## 📊 Sample Output

```
================================================================================
📊 PERFORMANCE METRICS REPORT
   Overall Grade: B+
================================================================================

💰 Profitability:
   Total P&L:         $1,234.56
   Total Return:      12.35%
   Gross Profit:      $2,100.00
   Gross Loss:        $865.44
   Profit Factor:     2.43

📈 Trade Statistics:
   Total Trades:      47
   Winning Trades:    28
   Losing Trades:     19
   Win Rate:          59.6%

⚡ Risk Metrics:
   Sharpe Ratio:      1.523
   Max Drawdown:      $450.00 (4.5%)
================================================================================
```

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Number of test entities
coins.total_coins = 100
users.total_users = 1000
users.agent_user_ids = [1, 2, 3, 4, 5]

# Price simulation
price_sim.simulation_duration_hours = 24
price_sim.time_interval_minutes = 5

# Agent settings
agent_test.confidence_threshold = 0.7
agent_test.max_trades_per_day = 5
```

## 🗄️ Database Integration

The framework can seed data directly into the nuahchain-backend PostgreSQL database, which is then fetched by the `fetch-data-agent` for a realistic end-to-end test.

**Data Flow:**
```
Testing Framework → PostgreSQL → fetch-data-agent → SQLite → trade-agent
```

To run without database (file-only mode):
```bash
python run_simulation.py --no-database
```

## 📝 Notes

1. **First Run**: The first simulation creates all test data from scratch
2. **Subsequent Runs**: Use `--test-only` to reuse existing data
3. **Database Setup**: Ensure PostgreSQL is running before database mode
4. **Agent Testing**: The real agent requires proper environment setup

## 🐛 Troubleshooting

**"Database connection error"**
- Check PostgreSQL is running
- Verify credentials in `.env`
- Use `--no-database` for file-only mode

**"No price data available"**
- Run `--generate-only` first to create data
- Check `data/` directory for JSON files

**"Agent timeout"**
- The real agent may need additional setup
- Use simulated mode (default) for testing the framework

