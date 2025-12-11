# NUAH Trading Dashboard UI

A modern, dark-themed trading dashboard for visualizing P&L and trade analytics from the NUAH multi-agent trading system.

## Features

- **Real-time P&L Display**: See today's total profit/loss at a glance
- **Trade History**: View all trades executed today with detailed information
- **Interactive Graphs**: Line charts showing cumulative P&L over time
- **Analytics Charts**: Pie charts and bar graphs for action/status/token breakdowns
- **Auto-refresh**: Data updates every 30 seconds automatically

## Pages

| Page | URL | Description |
|------|-----|-------------|
| **Dashboard** | `/` | Main overview with P&L hero, stats, and recent trades table |
| **Graph** | `/graph.html` | Line charts showing P&L timeline and hourly breakdown |
| **Charts** | `/chart.html` | Pie charts and bar graphs for detailed analytics |

## Quick Start

### 1. Install Dependencies

```powershell
cd UI
pip install -r requirements.txt
```

### 2. Start the Server

```powershell
python server.py
```

### 3. Open Dashboard

Navigate to: **http://localhost:8501**

## Configuration

The server looks for the SQLite database at:
```
../fetch-data-agent/data/user_data.db
```

To use a different database path, set the environment variable:
```powershell
$env:SQLITE_PATH = "C:\path\to\your\user_data.db"
python server.py
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check and database status |
| `GET /api/daily-summary` | Today's P&L summary and trade stats |
| `GET /api/trades-today` | List of all trades made today |
| `GET /api/pnl-timeline` | P&L data points for graphing |
| `GET /api/token-breakdown` | P&L breakdown by token |
| `GET /api/action-breakdown` | Trade count by action (buy/sell/hold) |
| `GET /api/status-breakdown` | Trade count by status (completed/failed/skipped) |
| `GET /api/user-breakdown` | P&L breakdown by user |

## Technology Stack

- **Backend**: FastAPI + uvicorn
- **Database**: SQLite (reads from trade-agent's `trade_executions` table)
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Charts**: Chart.js 4.x
- **Fonts**: JetBrains Mono (numbers), Sora (text)

## File Structure

```
UI/
├── server.py           # FastAPI backend
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── index.html         # Dashboard page
├── graph.html         # P&L graphs page
├── chart.html         # Analytics charts page
└── static/
    ├── css/
    │   └── style.css  # Shared styles (dark theme)
    └── js/
        └── common.js  # Shared JavaScript utilities
```

## Screenshots

### Dashboard
- Total P&L hero with glowing effect
- Stat cards for trades, success rate, buy/sell counts
- Best/worst trade highlights
- Recent trades table with action badges and confidence bars

### Graph Page
- Cumulative P&L line chart
- Hourly P&L bar chart
- Trade scatter plot showing individual trades

### Charts Page
- Action distribution doughnut chart (Buy/Sell/Hold)
- Status distribution doughnut chart (Completed/Failed/Skipped)
- Token P&L horizontal bar chart
- User P&L horizontal bar chart
- Detailed tables for tokens and users

## Design

The UI uses a dark trading terminal aesthetic:
- **Background**: Deep navy/charcoal (#0a0e14, #161b22)
- **Positive/Profit**: Cyan (#00d4aa)
- **Negative/Loss**: Coral red (#ff6b6b)
- **Neutral**: Gray (#8b949e)
- **Accents**: Subtle gradients and glow effects

## Running with the Full System

Start all agents in separate terminals:

```powershell
# Terminal 1: nuahchain-backend
cd nuahchain-backend
./build/server.exe

# Terminal 2: fetch-data-agent
cd NUAH/fetch-data-agent
npm run dev

# Terminal 3: trade-agent
cd NUAH/trade-agent
python scheduler.py

# Terminal 4: UI Dashboard
cd NUAH/UI
python server.py
```

Then open http://localhost:8501 to see your trading activity.

---

*NUAH Multi-Agent Trading System • Dashboard v1.0*


