"""
Test script for rules-agent with dummy data.
Run this before deploying to production to verify the agent works correctly.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from src.config import RulesAgentSettings
from src.pipeline import RulesAgentPipeline


def generate_dummy_data(data_dir: Path) -> None:
    """Generate all dummy data needed for rules-agent."""
    print("📊 Generating dummy data...")
    
    # Generate rules.csv
    rules = [
        {
            "rule_id": "R001",
            "description": "Max risk score threshold",
            "param": "risk_score",
            "value": "0.7",
            "enabled": True,
        },
        {
            "rule_id": "R002",
            "description": "Minimum liquidity requirement",
            "param": "liquidity_score",
            "value": "0.5",
            "enabled": True,
        },
        {
            "rule_id": "R003",
            "description": "Block high volatility tokens",
            "param": "volatility_score",
            "value": "0.8",
            "enabled": True,
        },
    ]
    rules_df = pd.DataFrame(rules)
    rules_df.to_csv(data_dir / "rules.csv", index=False)
    print(f"✅ Generated {len(rules)} rules")
    
    # Generate user_preferences.csv
    prefs = [
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
        {
            "user_id": 303,
            "risk_profile": "conservative",
            "max_trades_per_day": 2,
            "max_position_ndollar": 1000.0,
            "allowed_tokens": "MintBeta456",
            "blocked_tokens": "MintAlpha123|MintGamma789",
            "dry_run": False,
        },
    ]
    prefs_df = pd.DataFrame(prefs)
    prefs_df.to_csv(data_dir / "user_preferences.csv", index=False)
    print(f"✅ Generated {len(prefs)} user preferences")
    
    # Generate token_strategy_catalog.csv
    catalog = [
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
    catalog_df = pd.DataFrame(catalog)
    catalog_df.to_csv(data_dir / "token_strategy_catalog.csv", index=False)
    print(f"✅ Generated {len(catalog)} token catalog entries")


def validate_outputs(data_dir: Path) -> bool:
    """Validate that rules-agent produced correct outputs."""
    print("\n🔍 Validating outputs...")
    
    eval_path = data_dir / "rule_evaluations.csv"
    if not eval_path.exists():
        print("❌ rule_evaluations.csv not found")
        return False
    
    df = pd.read_csv(eval_path)
    if df.empty:
        print("❌ rule_evaluations.csv is empty")
        return False
    
    required_cols = [
        "evaluation_id",
        "timestamp",
        "user_id",
        "token_mint",
        "allowed",
        "max_daily_trades",
        "max_position_ndollar",
        "reason",
        "confidence",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing columns: {missing_cols}")
        return False
    
    # Validate data types
    if not all(isinstance(allowed, bool) or str(allowed).lower() in ["true", "false"] for allowed in df["allowed"]):
        print("❌ 'allowed' must be boolean")
        return False
    
    if not all(0 <= conf <= 1 for conf in df["confidence"]):
        print("❌ confidence out of range (0 to 1)")
        return False
    
    # Check that we have evaluations for all users
    unique_users = df["user_id"].nunique()
    print(f"✅ Found evaluations for {unique_users} users")
    print(f"✅ Total evaluations: {len(df)}")
    print(f"✅ All validations passed")
    return True


def main():
    """Run complete test suite for rules-agent."""
    print("=" * 60)
    print("🧪 Testing Rules Agent")
    print("=" * 60)
    
    # Setup
    data_dir = Path("../data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate dummy data
    generate_dummy_data(data_dir)
    
    # Run agent
    print("\n🚀 Running rules-agent...")
    settings = RulesAgentSettings(
        data_dir=data_dir,
        dry_run=True,
    )
    
    try:
        pipeline = RulesAgentPipeline(settings)
        evaluations = pipeline.run()
        
        if not evaluations:
            print("⚠️  No evaluations generated (this is OK in dry-run mode)")
        else:
            print(f"✅ Generated {len(evaluations)} rule evaluations")
        
        # Validate outputs
        if validate_outputs(data_dir):
            print("\n" + "=" * 60)
            print("✅ Rules Agent Test PASSED")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("❌ Rules Agent Test FAILED")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

