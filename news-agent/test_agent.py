"""
Test script for news-agent with dummy data.
Run this before deploying to production to verify the agent works correctly.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict

# Add parent directory to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from src.config import NewsAgentSettings
from src.pipeline import NewsAgentPipeline
from src.data_store import SharedDataStore


def generate_dummy_time_series(data_dir: Path) -> None:
    """Generate dummy time-series data for testing."""
    print("📊 Generating dummy time-series data...")
    
    now = datetime.now(timezone.utc)
    tokens = ["MintAlpha123", "MintBeta456", "MintGamma789"]
    
    rows = []
    for token in tokens:
        for i in range(10):  # 10 data points per token
            timestamp = (now - timedelta(hours=10-i)).isoformat()
            rows.append({
                "token_mint": token,
                "timestamp": timestamp,
                "open": 0.5 + (i * 0.05),
                "high": 0.6 + (i * 0.05),
                "low": 0.4 + (i * 0.05),
                "close": 0.55 + (i * 0.05),
                "volume": 10000 + (i * 1000),
                "momentum": 0.01 * i,
                "volatility": 0.1 + (i * 0.01),
            })
    
    df = pd.DataFrame(rows)
    csv_path = data_dir / "time_series.csv"
    df.to_csv(csv_path, index=False, mode="a" if csv_path.exists() else "w")
    print(f"✅ Generated {len(rows)} time-series records")


def generate_dummy_token_catalog(data_dir: Path) -> None:
    """Generate dummy token catalog data."""
    print("📋 Generating dummy token catalog...")
    
    tokens = [
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
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        {
            "token_mint": "MintBeta456",
            "name": "Beta Token",
            "symbol": "BETA",
            "bonding_curve_phase": "early",
            "risk_score": 0.65,
            "creator_reputation": 0.6,
            "liquidity_score": 0.6,
            "volatility_score": 0.7,
            "whale_concentration": 0.4,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        {
            "token_mint": "MintGamma789",
            "name": "Gamma Token",
            "symbol": "GAMMA",
            "bonding_curve_phase": "late",
            "risk_score": 0.35,
            "creator_reputation": 0.9,
            "liquidity_score": 0.85,
            "volatility_score": 0.4,
            "whale_concentration": 0.2,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
    ]
    
    df = pd.DataFrame(tokens)
    csv_path = data_dir / "token_strategy_catalog.csv"
    df.to_csv(csv_path, index=False, mode="a" if csv_path.exists() else "w")
    print(f"✅ Generated {len(tokens)} token catalog entries")


def validate_outputs(data_dir: Path) -> bool:
    """Validate that news-agent produced correct outputs."""
    print("\n🔍 Validating outputs...")
    
    news_path = data_dir / "news_signals.csv"
    if not news_path.exists():
        print("❌ news_signals.csv not found")
        return False
    
    df = pd.read_csv(news_path)
    if df.empty:
        print("❌ news_signals.csv is empty")
        return False
    
    required_cols = ["signal_id", "timestamp", "token_mint", "headline", "sentiment_score", "confidence"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing columns: {missing_cols}")
        return False
    
    # Validate data types
    if not all(-1 <= score <= 1 for score in df["sentiment_score"]):
        print("❌ sentiment_score out of range (-1 to 1)")
        return False
    
    if not all(0 <= conf <= 1 for conf in df["confidence"]):
        print("❌ confidence out of range (0 to 1)")
        return False
    
    print(f"✅ Found {len(df)} news signals")
    print(f"✅ All validations passed")
    return True


def main():
    """Run complete test suite for news-agent."""
    print("=" * 60)
    print("🧪 Testing News Agent")
    print("=" * 60)
    
    # Setup
    data_dir = Path("../data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate dummy data
    generate_dummy_time_series(data_dir)
    generate_dummy_token_catalog(data_dir)
    
    # Run agent
    print("\n🚀 Running news-agent...")
    settings = NewsAgentSettings(
        data_dir=data_dir,
        dry_run=True,  # Use dry-run for testing
    )
    
    try:
        pipeline = NewsAgentPipeline(settings)
        signals = pipeline.run()
        
        if not signals:
            print("⚠️  No signals generated (this is OK in dry-run mode)")
        else:
            print(f"✅ Generated {len(signals)} news signals")
        
        # Validate outputs
        if validate_outputs(data_dir):
            print("\n" + "=" * 60)
            print("✅ News Agent Test PASSED")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("❌ News Agent Test FAILED")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

