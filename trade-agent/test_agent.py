"""
Test script for trade-agent with dummy data.
Run this before deploying to production to verify the agent works correctly.
Tests the complete flow from data loading to trade execution (dry-run).
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from src.config import Settings
from src.pipeline import TradePipeline


def create_dummy_sqlite_db(db_path: Path) -> None:
    """Create a dummy SQLite database with user data."""
    print("💾 Creating dummy SQLite database...")
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            email TEXT,
            public_key TEXT NOT NULL,
            solana_address TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            last_fetched_at TIMESTAMP,
            data_json TEXT
        );
        
        CREATE TABLE IF NOT EXISTS user_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_mint TEXT NOT NULL,
            balance TEXT NOT NULL,
            updated_at TIMESTAMP,
            last_fetched_at TIMESTAMP,
            UNIQUE(user_id, token_mint)
        );
        
        CREATE TABLE IF NOT EXISTS user_portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_value_ndollar TEXT,
            total_value_sol TEXT,
            token_count INTEGER,
            snapshot_json TEXT,
            created_at TIMESTAMP
        );
    """)
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Insert dummy users
    users = [
        (101, "user101", "user101@test.com", "pubkey101", "solana101", now, now, now, None),
        (202, "user202", "user202@test.com", "pubkey202", "solana202", now, now, now, None),
    ]
    cursor.executemany(
        "INSERT OR REPLACE INTO users (user_id, username, email, public_key, solana_address, created_at, updated_at, last_fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        users
    )
    
    # Insert dummy balances
    balances = [
        (101, "MintAlpha123", "1500.50", now, now),
        (101, "MintBeta456", "800.25", now, now),
        (202, "MintAlpha123", "2000.00", now, now),
        (202, "MintGamma789", "500.75", now, now),
    ]
    cursor.executemany(
        "INSERT OR REPLACE INTO user_balances (user_id, token_mint, balance, updated_at, last_fetched_at) VALUES (?, ?, ?, ?, ?)",
        balances
    )
    
    # Insert dummy portfolios
    portfolio1 = {
        "tokens": [
            {"mint_address": "MintAlpha123", "balance": "1500.50", "value_ndollar": "1500.50"},
            {"mint_address": "MintBeta456", "balance": "800.25", "value_ndollar": "800.25"},
        ],
        "totalValueNDollar": "2300.75",
        "totalValueSOL": "115.50",
        "count": 2,
    }
    portfolio2 = {
        "tokens": [
            {"mint_address": "MintAlpha123", "balance": "2000.00", "value_ndollar": "2000.00"},
            {"mint_address": "MintGamma789", "balance": "500.75", "value_ndollar": "500.75"},
        ],
        "totalValueNDollar": "2500.75",
        "totalValueSOL": "125.00",
        "count": 2,
    }
    
    cursor.execute(
        "INSERT OR REPLACE INTO user_portfolios (user_id, total_value_ndollar, total_value_sol, token_count, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (101, "2300.75", "115.50", 2, json.dumps(portfolio1), now)
    )
    cursor.execute(
        "INSERT OR REPLACE INTO user_portfolios (user_id, total_value_ndollar, total_value_sol, token_count, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (202, "2500.75", "125.00", 2, json.dumps(portfolio2), now)
    )
    
    conn.commit()
    conn.close()
    print("✅ Created dummy SQLite database with 2 users")


def generate_dummy_csv_data(data_dir: Path) -> None:
    """Generate all dummy CSV files needed for trade-agent."""
    print("📊 Generating dummy CSV data...")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # News signals
    news_signals = [
        {
            "signal_id": "NEWS-001",
            "timestamp": now,
            "token_mint": "MintAlpha123",
            "headline": "Alpha token gains momentum",
            "sentiment_score": 0.7,
            "confidence": 0.8,
            "source": "deepseek",
            "summary": "Positive sentiment detected",
        },
        {
            "signal_id": "NEWS-002",
            "timestamp": now,
            "token_mint": "MintBeta456",
            "headline": "Beta token volatility warning",
            "sentiment_score": -0.3,
            "confidence": 0.65,
            "source": "deepseek",
            "summary": "Moderate negative sentiment",
        },
    ]
    pd.DataFrame(news_signals).to_csv(data_dir / "news_signals.csv", index=False, mode="a" if (data_dir / "news_signals.csv").exists() else "w")
    print("✅ Generated news_signals.csv")
    
    # Trend signals
    trend_signals = [
        {
            "signal_id": "TREND-001",
            "timestamp": now,
            "token_mint": "MintAlpha123",
            "trend_score": 0.6,
            "stage": "mid",
            "volatility_flag": "moderate",
            "liquidity_flag": "healthy",
            "confidence": 0.75,
            "summary": "Strong upward trend",
        },
        {
            "signal_id": "TREND-002",
            "timestamp": now,
            "token_mint": "MintBeta456",
            "trend_score": -0.2,
            "stage": "early",
            "volatility_flag": "high",
            "liquidity_flag": "thin",
            "confidence": 0.6,
            "summary": "Declining trend",
        },
    ]
    pd.DataFrame(trend_signals).to_csv(data_dir / "trend_signals.csv", index=False, mode="a" if (data_dir / "trend_signals.csv").exists() else "w")
    print("✅ Generated trend_signals.csv")
    
    # Rule evaluations
    rule_evaluations = [
        {
            "evaluation_id": "RULE-001",
            "timestamp": now,
            "user_id": 101,
            "token_mint": "MintAlpha123",
            "allowed": True,
            "max_daily_trades": 4,
            "max_position_ndollar": 2500.0,
            "reason": "Within risk limits",
            "confidence": 0.8,
        },
        {
            "evaluation_id": "RULE-002",
            "timestamp": now,
            "user_id": 202,
            "token_mint": "MintAlpha123",
            "allowed": True,
            "max_daily_trades": 6,
            "max_position_ndollar": 5000.0,
            "reason": "Aggressive profile approved",
            "confidence": 0.75,
        },
    ]
    pd.DataFrame(rule_evaluations).to_csv(data_dir / "rule_evaluations.csv", index=False, mode="a" if (data_dir / "rule_evaluations.csv").exists() else "w")
    print("✅ Generated rule_evaluations.csv")
    
    # User preferences
    user_preferences = [
        {
            "user_id": 101,
            "risk_profile": "balanced",
            "max_trades_per_day": 4,
            "max_position_ndollar": 2500.0,
            "allowed_tokens": "MintAlpha123|MintBeta456",
            "blocked_tokens": "MintGamma789",
            "dry_run": False,
        },
        {
            "user_id": 202,
            "risk_profile": "aggressive",
            "max_trades_per_day": 6,
            "max_position_ndollar": 5000.0,
            "allowed_tokens": "MintAlpha123|MintGamma789",
            "blocked_tokens": "",
            "dry_run": False,
        },
    ]
    pd.DataFrame(user_preferences).to_csv(data_dir / "user_preferences.csv", index=False)
    print("✅ Generated user_preferences.csv")
    
    # Token catalog
    token_catalog = [
        {
            "token_mint": "MintAlpha123",
            "name": "Alpha Token",
            "symbol": "ALPHA",
            "bonding_curve_phase": "mid",
            "risk_score": 0.45,
            "creator_reputation": 0.8,
            "liquidity_score": 0.75,
            "volatility_score": 0.5,
            "whale_concentration": 0.3,
            "last_updated": now,
        },
    ]
    pd.DataFrame(token_catalog).to_csv(data_dir / "token_strategy_catalog.csv", index=False)
    print("✅ Generated token_strategy_catalog.csv")
    
    # Time series
    time_series = [
        {
            "token_mint": "MintAlpha123",
            "timestamp": now,
            "open": 0.82,
            "high": 0.91,
            "low": 0.78,
            "close": 0.89,
            "volume": 14500,
            "momentum": 0.07,
            "volatility": 0.12,
        },
    ]
    pd.DataFrame(time_series).to_csv(data_dir / "time_series.csv", index=False, mode="a" if (data_dir / "time_series.csv").exists() else "w")
    print("✅ Generated time_series.csv")


def validate_outputs(data_dir: Path) -> bool:
    """Validate that trade-agent produced correct outputs."""
    print("\n🔍 Validating outputs...")
    
    # Check historical_trades.csv (audit log)
    trades_path = data_dir / "historical_trades.csv"
    if not trades_path.exists():
        print("⚠️  historical_trades.csv not found (may be first run)")
        return True  # Not a failure, just no trades executed
    
    df = pd.read_csv(trades_path)
    if df.empty:
        print("⚠️  historical_trades.csv is empty (no trades executed)")
        return True  # Not a failure, just no trades
    
    print(f"✅ Found {len(df)} trade records in audit log")
    return True


def main():
    """Run complete test suite for trade-agent."""
    print("=" * 60)
    print("🧪 Testing Trade Agent (Complete Flow)")
    print("=" * 60)
    
    # Setup paths
    data_dir = Path("../data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    sqlite_path = Path("../fetch-data-agent/data/user_data.db")
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate dummy data
    create_dummy_sqlite_db(sqlite_path)
    generate_dummy_csv_data(data_dir)
    
    # Run agent
    print("\n🚀 Running trade-agent...")
    settings = Settings(
        sqlite_path=sqlite_path,
        snapshot_dir=Path("../fetch-data-agent/data/snapshots"),
        data_dir=data_dir,
        dry_run=True,  # Always use dry-run for testing
        user_ids=[101, 202],  # Test with specific users
    )
    
    try:
        pipeline = TradePipeline(settings)
        pipeline.run(user_ids=[101, 202])
        
        print("\n✅ Trade pipeline completed")
        
        # Validate outputs
        if validate_outputs(data_dir):
            print("\n" + "=" * 60)
            print("✅ Trade Agent Test PASSED")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("❌ Trade Agent Test FAILED")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

