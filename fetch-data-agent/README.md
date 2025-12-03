# Fetch Data Agent

Agent to fetch user data from n-dollar-server and store in SQLite database.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

3. Configure environment variables in `.env`:
- `API_BASE_URL`: Base URL of n-dollar-server (default: http://localhost:3000)
- `API_TOKEN`: JWT token for authentication
- `DB_PATH`: Path to SQLite database file (default: ./data/user_data.db)
- `FETCH_INTERVAL_MINUTES`: Fetch interval in minutes (default: 20)
- `BATCH_SIZE`: Number of users to fetch per batch (default: 10)

## Usage

### Development
```bash
npm run dev
```

### Production
```bash
npm run build
npm start
```

### Run fetch immediately
```bash
npm run dev -- --run-now
# or
npm start -- --run-now
```

## How it works

1. **Scheduler**: Runs every 20 minutes (configurable) to fetch user data
2. **API Client**: Fetches data from n-dollar-server API endpoints:
   - `/api/v1/users/data/:userId` - Single user data
   - `/api/v1/users/data/batch` - Batch user data
3. **Data Service**: Stores fetched data in SQLite database
4. **Database**: SQLite file-based database with tables:
   - `users` - User profiles
   - `user_balances` - Token balances
   - `user_transactions` - Transaction history
   - `user_portfolios` - Portfolio snapshots
   - `user_bots` - Bot configurations
   - `market_data` - Token market data

## Database Schema

The SQLite database is automatically created with the following schema:
- Users table with profile information
- Balances table with token balances per user
- Transactions table with transaction history
- Portfolios table with portfolio snapshots
- Bots table with trading bot configurations
- Market data table with token prices and metrics

## Notes

- The agent fetches data for users that are already in the database
- To add new users, you need to manually insert them or fetch them via API
- Active traders (users with active bots) are fetched with priority
- All data is stored with timestamps for tracking freshness



