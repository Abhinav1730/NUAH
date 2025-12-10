# Docker Deployment Guide

## 🚀 Quick Start

```bash
# 1. Copy environment file
cp env.example.txt .env

# 2. Edit .env with your API keys
nano .env

# 3. Build and start all services
docker-compose up -d --build

# 4. View logs
docker-compose logs -f

# 5. Access UI
open http://localhost:8000
```

---

## 📦 Services Overview

| Service | Port | Description |
|---------|------|-------------|
| `fetch-data-agent` | - | Syncs data from nuahchain-backend (every 5 min) |
| `news-agent` | - | Analyzes sentiment & catalysts (every 5 min) |
| `trend-agent` | - | Analyzes bonding curves & rug risk (every 5 min) |
| `rules-agent` | - | Evaluates user rules & limits (every 5 min) |
| `trade-agent` | - | Real-time trading (every 5-15 sec) |
| `ui` | 8000 | Dashboard for monitoring trades |

---

## 🔧 Commands

### Start All Services
```bash
docker-compose up -d --build
```

### Start Specific Services
```bash
# Just trading (requires nuahchain-backend running externally)
docker-compose up -d trade-agent ui

# Background agents only
docker-compose up -d news-agent trend-agent rules-agent
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f trade-agent

# Last 100 lines
docker-compose logs --tail=100 trade-agent
```

### Stop Services
```bash
# Stop all
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Rebuild After Code Changes
```bash
docker-compose up -d --build trade-agent
```

---

## 📁 Volume Mounts

| Volume | Purpose |
|--------|---------|
| `shared-data` | SQLite database (`user_data.db`) |
| `agent-signals` | CSV outputs from analysis agents |
| `trade-logs` | Trade execution logs |

### Accessing Volumes
```bash
# List volumes
docker volume ls | grep nuah

# Inspect volume location
docker volume inspect nuah_shared-data

# Backup SQLite database
docker cp nuah-trade-agent:/app/data/user_data.db ./backup.db
```

---

## ⚙️ Environment Variables

### Required
```bash
NUAHCHAIN_API_URL=http://localhost:8080  # Backend URL
NUAHCHAIN_API_TOKEN=your-jwt-token       # Auth token
OPENROUTER_API_KEY=sk-or-v1-xxx          # For DeepSeek LLM
GEMINI_API_KEY=AIza-xxx                  # For scam detection
```

### Trading Config
```bash
TRADING_MODE=fast          # fast or standard
DRY_RUN=true               # true = no real trades
USER_IDS=1,2,3,4,5         # Users to trade for
```

### Risk Management
```bash
STOP_LOSS_PERCENT=0.10     # 10% stop loss
TAKE_PROFIT_PERCENT=0.25   # 25% take profit
EMERGENCY_EXIT_THRESHOLD=-0.30  # -30% emergency exit
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network: nuah-network             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐                                        │
│  │ fetch-data-agent│──────────────────┐                     │
│  │   (Node.js)     │                  │                     │
│  └─────────────────┘                  ▼                     │
│                               ┌───────────────┐             │
│  ┌─────────────────┐          │  shared-data  │             │
│  │   news-agent    │◄────────►│   (volume)    │             │
│  │   (Python)      │          │ user_data.db  │             │
│  └─────────────────┘          └───────┬───────┘             │
│                                       │                     │
│  ┌─────────────────┐                  │                     │
│  │  trend-agent    │◄─────────────────┤                     │
│  │   (Python)      │                  │                     │
│  └─────────────────┘                  │                     │
│           │                           │                     │
│           ▼                           │                     │
│  ┌───────────────────┐                │                     │
│  │   agent-signals   │                │                     │
│  │     (volume)      │                │                     │
│  │ news_signals.csv  │                │                     │
│  │ trend_signals.csv │                │                     │
│  │ rule_evals.csv    │                │                     │
│  └─────────┬─────────┘                │                     │
│            │                          │                     │
│            ▼                          ▼                     │
│  ┌─────────────────────────────────────────────┐           │
│  │              trade-agent                     │           │
│  │              (Python)                        │           │
│  │                                              │           │
│  │  • Real-time price monitor (5 sec)          │           │
│  │  • Pattern detection (pump/dump/rug)        │           │
│  │  • Gemini scam detection                    │           │
│  │  • Stop-loss / Take-profit                  │           │
│  │  • Emergency exit                           │           │
│  └─────────────────────┬───────────────────────┘           │
│                        │                                    │
│                        ▼                                    │
│  ┌─────────────────────────────────────────────┐           │
│  │                   UI                         │           │
│  │               (FastAPI)                      │──► :8000  │
│  │           Dashboard + Charts                 │           │
│  └─────────────────────────────────────────────┘           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                        │
                        │ HTTP API calls
                        ▼
              ┌───────────────────┐
              │ nuahchain-backend │
              │   (Go + Postgres) │
              │     :8080         │
              └───────────────────┘
```

---

## 🐛 Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs trade-agent

# Check if API is reachable
docker exec nuah-trade-agent curl -s http://host.docker.internal:8080/health
```

### Database not found
```bash
# Ensure fetch-data-agent ran first
docker-compose logs fetch-data-agent

# Check if database exists
docker exec nuah-trade-agent ls -la /app/data/
```

### API connection refused
```bash
# If nuahchain-backend is on host machine
# Make sure NUAHCHAIN_API_URL uses host.docker.internal
NUAHCHAIN_API_URL=http://host.docker.internal:8080
```

### Permission issues
```bash
# Fix volume permissions
docker-compose down
docker volume rm nuah_shared-data
docker-compose up -d
```

---

## 🔒 Production Deployment

### 1. Disable Dry Run
```bash
DRY_RUN=false
```

### 2. Use Secrets
```bash
# Use Docker secrets instead of .env
docker secret create gemini_api_key ./gemini_key.txt
```

### 3. Add Monitoring
```yaml
# Add to docker-compose.yml
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
```

### 4. Enable Restart Policies
All services already have `restart: unless-stopped`

### 5. Resource Limits
```yaml
  trade-agent:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'
```

---

## 📊 Health Checks

All containers have health checks configured:

```bash
# Check health status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Output:
# NAMES                    STATUS
# nuah-trade-agent         Up 5 minutes (healthy)
# nuah-news-agent          Up 5 minutes (healthy)
# nuah-ui                  Up 5 minutes (healthy)
```

