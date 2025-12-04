"""
Test script for trend-agent with dummy data.
Run this before deploying to production to verify the agent works correctly.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from src.config import TrendAgentSettings
from src.pipeline import TrendAgentPipeline


def generate_dummy_time_series(data_dir: Path) -> None:
    """Generate dummy time-series data for testing."""
    print("📊 Generating dummy time-series data...")
    
    now = datetime.now(timezone.utc)
    tokens = ["MintAlpha123", "MintBeta456", "MintGamma789", "MintDelta012"]
    
    rows = []
    for token in tokens:
        for i in range(20):  # 20 data points per token
            timestamp = (now - timedelta(hours=20-i)).isoformat()
            base_price = 0.5 if "Alpha" in token else 1.0 if "Beta" in token else 0.3
            rows.append({
                "token_mint": token,
                "timestamp": timestamp,
                "open": base_price + (i * 0.02),
                "high": base_price + (i * 0.03),
                "low": base_price + (i * 0.01),
                "close": base_price + (i * 0.025),
                "volume": 5000 + (i * 500),
                "momentum": 0.005 * i,
                "volatility": 0.08 + (i * 0.005),
            })
    
    df = pd.DataFrame(rows)
    csv_path = data_dir / "time_series.csv"
    df.to_csv(csv_path, index=False, mode="a" if csv_path.exists() else "w")
    print(f"✅ Generated {len(rows)} time-series records")


def validate_outputs(data_dir: Path) -> bool:
    """Validate that trend-agent produced correct outputs."""
    print("\n🔍 Validating outputs...")
    
    # Check trend_signals.csv
    trend_path = data_dir / "trend_signals.csv"
    if not trend_path.exists():
        print("❌ trend_signals.csv not found")
        return False
    
    df = pd.read_csv(trend_path)
    if df.empty:
        print("❌ trend_signals.csv is empty")
        return False
    
    required_cols = ["signal_id", "timestamp", "token_mint", "trend_score", "stage", "confidence"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing columns: {missing_cols}")
        return False
    
    # Validate data
    if not all(-1 <= score <= 1 for score in df["trend_score"]):
        print("❌ trend_score out of range (-1 to 1)")
        return False
    
    valid_stages = ["early", "mid", "late"]
    if not all(stage in valid_stages for stage in df["stage"]):
        print(f"❌ Invalid stage values (must be one of: {valid_stages})")
        return False
    
    # Check token_strategy_catalog.csv was updated
    catalog_path = data_dir / "token_strategy_catalog.csv"
    if catalog_path.exists():
        catalog_df = pd.read_csv(catalog_path)
        print(f"✅ Catalog updated with {len(catalog_df)} tokens")
    
    print(f"✅ Found {len(df)} trend signals")
    print(f"✅ All validations passed")
    return True


def main():
    """Run complete test suite for trend-agent."""
    print("=" * 60)
    print("🧪 Testing Trend Agent")
    print("=" * 60)
    
    # Setup
    data_dir = Path("../data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate dummy data
    generate_dummy_time_series(data_dir)
    
    # Run agent
    print("\n🚀 Running trend-agent...")
    settings = TrendAgentSettings(
        data_dir=data_dir,
        dry_run=True,
    )
    
    try:
        pipeline = TrendAgentPipeline(settings)
        signals = pipeline.run()
        
        if not signals:
            print("⚠️  No signals generated (this is OK in dry-run mode)")
        else:
            print(f"✅ Generated {len(signals)} trend signals")
        
        # Validate outputs
        if validate_outputs(data_dir):
            print("\n" + "=" * 60)
            print("✅ Trend Agent Test PASSED")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("❌ Trend Agent Test FAILED")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

