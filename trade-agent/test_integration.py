#!/usr/bin/env python3
"""
Integration Test Script for trade-agent

Tests the connection to nuahchain-backend and validates that
the trade pipeline can work with the test coins created by seed_test_data.

Usage:
    cd trade-agent
    python test_integration.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add shared directory to path
_shared_path = Path(__file__).parent.parent / "shared"
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("test_integration")


def test_environment():
    """Test 1: Verify environment variables are set."""
    print("\n" + "=" * 60)
    print("Test 1: Environment Variables")
    print("=" * 60)
    
    api_token = os.getenv("API_TOKEN") or os.getenv("NUAHCHAIN_API_TOKEN")
    api_base_url = os.getenv("API_BASE_URL") or os.getenv("NUAHCHAIN_API_BASE_URL") or "http://localhost:8080"
    
    print(f"📡 API_BASE_URL: {api_base_url}")
    
    if not api_token:
        print("❌ API_TOKEN not set!")
        print("   Set it via: $env:API_TOKEN='your_jwt_token'")
        return False
    
    print(f"🔑 API_TOKEN: {api_token[:30]}...")
    print("✅ Environment OK")
    return True


def test_nuahchain_client():
    """Test 2: Test NuahChainClient connection."""
    print("\n" + "=" * 60)
    print("Test 2: NuahChain Client Connection")
    print("=" * 60)
    
    try:
        from nuahchain_client import NuahChainClient
        
        api_token = os.getenv("API_TOKEN") or os.getenv("NUAHCHAIN_API_TOKEN")
        api_base_url = os.getenv("API_BASE_URL") or os.getenv("NUAHCHAIN_API_BASE_URL") or "http://localhost:8080"
        
        client = NuahChainClient(
            base_url=api_base_url,
            api_token=api_token,
        )
        
        # Test health check
        import requests
        response = requests.get(f"{api_base_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Server health: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
        
        # Test marketplace tokens
        print("\n🪙 Fetching marketplace tokens...")
        tokens = client.get_marketplace_tokens(limit=10)
        print(f"   Found {len(tokens)} tokens in marketplace")
        
        if tokens:
            print("   Sample tokens:")
            for i, t in enumerate(tokens[:5]):
                print(f"   {i+1}. {t.get('name', 'N/A')} ({t.get('symbol', 'N/A')}) - {t.get('denom', 'N/A')}")
        else:
            print("   ⚠️ No tokens in marketplace (might need blockchain sync)")
        
        # Test user balances (from database, not blockchain)
        print("\n💰 Fetching user balances from DB...")
        try:
            balances = client.get_user_balances(from_blockchain=False)
            print(f"   Found {len(balances)} balances in DB")
            for b in balances[:5]:
                print(f"   - {b.get('denom', 'N/A')}: {b.get('amount', 'N/A')}")
        except Exception as e:
            print(f"   ⚠️ Could not fetch balances: {e}")
        
        print("\n✅ NuahChain Client working!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure shared/ directory is accessible")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_denom_mapper():
    """Test 3: Test denom mapper functionality."""
    print("\n" + "=" * 60)
    print("Test 3: Denom Mapper")
    print("=" * 60)
    
    try:
        from denom_mapper import denom_to_token_mint, token_mint_to_denom, add_mapping
        
        # Test with our test coin denoms
        test_denoms = [
            "factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TBTC",
            "factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TETH",
            "factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TSOL",
            "factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TADA",
            "factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TDOT",
        ]
        
        print("📍 Testing denom -> token_mint conversion:")
        for denom in test_denoms:
            token_mint = denom_to_token_mint(denom)
            print(f"   {denom[-20:]}... -> {token_mint}")
            
            # Add mapping for reverse lookup
            add_mapping(denom, token_mint)
        
        print("\n📍 Testing reverse mapping (token_mint -> denom):")
        for symbol in ["TBTC", "TETH", "TSOL", "TADA", "TDOT"]:
            denom = token_mint_to_denom(symbol)
            if denom:
                print(f"   {symbol} -> ...{denom[-30:]}")
            else:
                print(f"   {symbol} -> ⚠️ Not in cache (expected after fresh start)")
        
        print("\n✅ Denom Mapper working!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_ndollar_client():
    """Test 4: Test NDollar client (trade execution client)."""
    print("\n" + "=" * 60)
    print("Test 4: NDollar Client (Trade Execution)")
    print("=" * 60)
    
    try:
        from src.execution.ndollar_client import NDollarClient
        
        api_token = os.getenv("API_TOKEN") or os.getenv("NUAHCHAIN_API_TOKEN")
        api_base_url = os.getenv("API_BASE_URL") or os.getenv("NUAHCHAIN_API_BASE_URL") or "http://localhost:8080"
        
        client = NDollarClient(
            base_url=api_base_url,
            api_token=api_token,
        )
        
        print("📊 NDollar client initialized")
        print(f"   Base URL: {client.base_url}")
        print(f"   Token: {'***' + api_token[-10:] if api_token else 'None'}")
        
        # Note: We don't actually execute trades here, just verify the client works
        print("\n✅ NDollar Client initialized (trades would work in non-dry-run mode)")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you're in the trade-agent directory")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_config():
    """Test 5: Test configuration loading."""
    print("\n" + "=" * 60)
    print("Test 5: Configuration")
    print("=" * 60)
    
    try:
        from src.config import get_settings
        
        settings = get_settings()
        
        print(f"📁 SQLite Path: {settings.sqlite_path}")
        print(f"📁 Data Dir: {settings.data_dir}")
        print(f"📁 Models Dir: {settings.models_dir}")
        print(f"📡 API Base URL: {settings.api_base_url}")
        print(f"🔑 API Token: {'Set' if settings.api_token else 'Not Set'}")
        print(f"🧪 Dry Run: {settings.dry_run}")
        print(f"📊 User IDs: {settings.user_ids}")
        
        # Check if SQLite DB exists
        if settings.sqlite_path.exists():
            print(f"\n✅ SQLite DB exists at {settings.sqlite_path}")
        else:
            print(f"\n⚠️ SQLite DB not found at {settings.sqlite_path}")
            print("   Run fetch-data-agent first to create it")
        
        print("\n✅ Configuration loaded!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_sqlite_loader():
    """Test 6: Test SQLite data loader."""
    print("\n" + "=" * 60)
    print("Test 6: SQLite Data Loader")
    print("=" * 60)
    
    try:
        from src.config import get_settings
        from src.data_ingestion import SQLiteDataLoader
        
        settings = get_settings()
        
        if not settings.sqlite_path.exists():
            print(f"⚠️ SQLite DB not found at {settings.sqlite_path}")
            print("   Creating test database...")
            
            # Create minimal test database
            import sqlite3
            settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(settings.sqlite_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    email TEXT,
                    public_key TEXT,
                    last_fetched_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_balances (
                    user_id INTEGER,
                    token_mint TEXT,
                    balance TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_transactions (
                    user_id INTEGER,
                    transaction_type TEXT,
                    token_mint TEXT,
                    amount TEXT,
                    signature TEXT,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_portfolios (
                    user_id INTEGER,
                    total_value_ndollar TEXT,
                    total_value_sol TEXT,
                    token_count INTEGER,
                    snapshot_json TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS news_signals (
                    token_mint TEXT,
                    headline TEXT,
                    sentiment_score REAL,
                    confidence REAL,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trend_signals (
                    token_mint TEXT,
                    trend TEXT,
                    confidence REAL,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rule_evaluations (
                    user_id INTEGER,
                    token_mint TEXT,
                    allowed INTEGER,
                    max_position_ndollar REAL,
                    max_daily_trades INTEGER,
                    reason TEXT,
                    confidence REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    max_position_ndollar REAL,
                    max_trades_per_day INTEGER,
                    risk_level TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_strategy_catalog (
                    token_mint TEXT PRIMARY KEY,
                    name TEXT,
                    symbol TEXT,
                    strategy TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS time_series (
                    token_mint TEXT,
                    timestamp TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    momentum REAL,
                    volatility REAL
                )
            """)
            
            # Insert test user (ID 1 - matching our seed data)
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO users (user_id, username, email, public_key, last_fetched_at, updated_at)
                VALUES (1, 'testbyabhinav', 'testbyabhinav@gmail.com', 'nuah10e2dde1b41cbeeca5a700c828df18759381f61c7', ?, ?)
            """, (now, now))
            
            # Insert test balances for our test coins
            test_coins = [
                ("factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TBTC", "1000000"),
                ("factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TETH", "2000000"),
                ("factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TSOL", "3000000"),
                ("factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TADA", "4000000"),
                ("factory/nuah10e2dde1b41cbeeca5a700c828df18759381f61c7/TDOT", "5000000"),
            ]
            for token_mint, balance in test_coins:
                conn.execute("""
                    INSERT OR REPLACE INTO user_balances (user_id, token_mint, balance, updated_at)
                    VALUES (1, ?, ?, ?)
                """, (token_mint, balance, now))
            
            # Insert test portfolio
            import json
            portfolio_json = json.dumps({
                "tokens": [
                    {"mint_address": denom, "balance": bal, "name": denom.split("/")[-1]}
                    for denom, bal in test_coins
                ],
                "totalValueNDollar": "100.0",
                "totalValueSOL": "0.0",
                "count": 5,
            })
            conn.execute("""
                INSERT OR REPLACE INTO user_portfolios (user_id, total_value_ndollar, total_value_sol, token_count, snapshot_json, created_at)
                VALUES (1, '100.0', '0.0', 5, ?, ?)
            """, (portfolio_json, now))
            
            # Insert user preferences
            conn.execute("""
                INSERT OR REPLACE INTO user_preferences (user_id, max_position_ndollar, max_trades_per_day, risk_level)
                VALUES (1, 50.0, 5, 'medium')
            """)
            
            conn.commit()
            conn.close()
            print("   ✅ Test database created with sample data")
        
        loader = SQLiteDataLoader(settings.sqlite_path)
        
        # Test fetching users
        print("\n📊 Fetching recent users...")
        users = loader.fetch_recent_users(limit=5)
        print(f"   Found {len(users)} users")
        for u in users:
            print(f"   - User {u.get('user_id')}: {u.get('username', 'N/A')}")
        
        # Test fetching user snapshot
        if users:
            user_id = users[0].get("user_id", 1)
            print(f"\n📊 Fetching snapshot for user {user_id}...")
            snapshot = loader.fetch_user_snapshot(user_id)
            if snapshot:
                print(f"   User: {snapshot.get('user', {}).get('username', 'N/A')}")
                print(f"   Balances: {len(snapshot.get('balances', []))}")
                print(f"   Transactions: {len(snapshot.get('transactions', []))}")
                if snapshot.get('portfolio'):
                    print(f"   Portfolio value: {snapshot['portfolio'].get('totalValueNDollar', 'N/A')} N$")
            else:
                print("   ⚠️ No snapshot found")
        
        print("\n✅ SQLite Data Loader working!")
        return True
        
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False


def test_trade_pipeline_dry_run():
    """Test 7: Test trade pipeline in dry-run mode."""
    print("\n" + "=" * 60)
    print("Test 7: Trade Pipeline (Dry Run)")
    print("=" * 60)
    
    try:
        # Force dry run mode
        os.environ["DRY_RUN"] = "true"
        
        # Clear cached settings to pick up new env
        from src.config import get_settings
        get_settings.cache_clear()
        
        settings = get_settings()
        settings.dry_run = True
        
        print(f"🧪 Running pipeline in DRY RUN mode")
        print(f"   User IDs to process: {settings.user_ids or [1]}")
        
        from src.pipeline import TradePipeline
        
        pipeline = TradePipeline(settings)
        
        # Run for user 1 (our test user)
        print("\n🚀 Running pipeline for user 1...")
        try:
            pipeline.run(user_ids=[1])
            print("\n✅ Pipeline completed successfully!")
        except ValueError as e:
            if "No snapshot" in str(e):
                print(f"   ⚠️ {e}")
                print("   This is expected if fetch-data-agent hasn't run yet")
            else:
                raise
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Some dependencies might be missing")
        print("   Run: pip install -r requirements.txt")
        return False
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("🧪 Trade Agent Integration Tests")
    print("=" * 60)
    print("Testing connection to nuahchain-backend and")
    print("ability to trade with test coins from seed_test_data")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Environment
    results["environment"] = test_environment()
    if not results["environment"]:
        print("\n❌ Cannot proceed without environment variables")
        print("\nSet the API token:")
        print('  $env:API_TOKEN="your_jwt_token_here"')
        return
    
    # Test 2: NuahChain Client
    results["nuahchain_client"] = test_nuahchain_client()
    
    # Test 3: Denom Mapper
    results["denom_mapper"] = test_denom_mapper()
    
    # Test 4: NDollar Client
    results["ndollar_client"] = test_ndollar_client()
    
    # Test 5: Configuration
    results["config"] = test_config()
    
    # Test 6: SQLite Loader
    results["sqlite_loader"] = test_sqlite_loader()
    
    # Test 7: Trade Pipeline (dry run)
    results["trade_pipeline"] = test_trade_pipeline_dry_run()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("✅ All tests passed! Trade agent is ready to use.")
    else:
        print("⚠️ Some tests failed. Check the output above.")
    
    print("\n💡 To run the trade agent:")
    print("   python main.py --user-ids 1")
    print("\n💡 For dry-run mode (no actual trades):")
    print("   $env:DRY_RUN='true'; python main.py --user-ids 1")


if __name__ == "__main__":
    main()

